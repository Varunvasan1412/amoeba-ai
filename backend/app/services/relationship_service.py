
from typing import Dict, Any, List, Optional
import asyncio
from app.services.schema_discovery_v2 import discover_full_schema
from app.models.client_config import ClientConfig
from app.models.allowed_relationship import AllowedRelationship
from app.models.approved_join_path import ApprovedJoinPath
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

# In-memory Cache: {client_id: {table: {related_table: {local, remote}}}}
# Simple Dict for production-ready, dependency-free implementation.
_RELATIONSHIP_CACHE = {}

def _calculate_risk(method: str, parent: str, child: str) -> tuple[str, float]:
    """
    Returns (risk_level, confidence_score)
    """
    # 1. Circular / Self-Reference
    if parent == child:
        return "circular", 0.0

    # 2. Heuristic
    if method == "heuristic":
        return "heuristic", 0.6
        
    # 3. Explicit FK (Safe)
    if method == "explicit":
        # Check for High Cardinality (heuristic check based on naming?)
        # For now, explicit is safe.
        return "safe", 1.0

    return "heuristic", 0.5 

async def get_relationship_graph(session: AsyncSession, client_id: int) -> Dict[str, Dict[str, Dict[str, str]]]:
    """
    Returns the Relationship Graph for a client from ENABLED database records.
    """
    if client_id in _RELATIONSHIP_CACHE:
        return _RELATIONSHIP_CACHE[client_id]

    # Build FINAL Bidirectional Graph from ALL Enabled DB Records
    from sqlmodel import select
    stmt = select(AllowedRelationship).where(
        AllowedRelationship.client_id == client_id,
        AllowedRelationship.is_enabled == True,
        AllowedRelationship.is_restricted == False
    )
    all_db_rels = (await session.execute(stmt)).scalars().all()
    
    builder_graph = {}
    
    # Initialize all possible tables as nodes
    all_tables = set()
    for r in all_db_rels:
        all_tables.add(r.parent_table)
        all_tables.add(r.child_table)
    
    for t in all_tables:
        builder_graph[t] = {}

    for rel in all_db_rels:
        # Add Forward: Child -> Parent (Natural Join Path)
        builder_graph[rel.child_table][rel.parent_table] = {
            "local_column": rel.child_column,
            "remote_column": rel.parent_column,
            "direction": "forward",
            "method": rel.risk_level,
            "selected_columns": rel.selected_columns or []
        }
        # Add Reverse: Parent -> Child (Discovery Path)
        builder_graph[rel.parent_table][rel.child_table] = {
            "local_column": rel.parent_column,
            "remote_column": rel.child_column,
            "direction": "reverse",
            "method": rel.risk_level,
            "selected_columns": rel.selected_columns or []
        }

    print(f"DEBUG: Graph built from DB. Enabled Bidirectional Joins: {sum(len(v) for v in builder_graph.values())}")
    
    _RELATIONSHIP_CACHE[client_id] = builder_graph
    return builder_graph

async def discover_and_sync_relationships(session: AsyncSession, client_id: int) -> List[AllowedRelationship]:
    """
    Runs schema discovery and syncs results to the database.
    """
    # 1. Fetch Client DB Connection
    client_config = await session.get(ClientConfig, client_id)
    if not client_config:
        raise HTTPException(status_code=404, detail="Client not found")

    sync_url = client_config.db_connection_url.replace("+asyncpg", "")
    
    # 2. Run Discovery (Extract FKs)
    loop = asyncio.get_event_loop()
    try:
        schema_data = await loop.run_in_executor(None, discover_full_schema, sync_url)
    except Exception as e:
        print(f"Relationship Discovery Failed for Client {client_id}: {e}")
        return []

    # 3. Build Raw Discovery Graph
    graph = {}
    for table_name in schema_data.keys():
        graph[table_name] = {}

    # 3a. Explicit FK Discovery
    for table_name, data in schema_data.items():
        fks = data.get("foreign_keys", [])
        for fk in fks:
            referred_table = fk["referred_table"]
            if not fk["constrained_columns"] or not fk["referred_columns"] or referred_table not in schema_data:
                continue
            local_col = fk["constrained_columns"][0]
            remote_col = fk["referred_columns"][0]
            graph[table_name][referred_table] = {"local_column": local_col, "remote_column": remote_col, "direction": "forward", "method": "explicit"}
            graph[referred_table][table_name] = {"local_column": remote_col, "remote_column": local_col, "direction": "reverse", "method": "explicit"}

    # 3b. Heuristic Discovery
    for table_name, data in schema_data.items():
        columns = data.get("columns", [])
        for col in columns:
            l_col = col.lower()
            if (l_col.endswith("_id") or l_col.endswith("id")) and l_col != "id":
                base_name = l_col[:-3] if l_col.endswith("_id") else l_col[:-2]
                candidates = [
                    base_name, f"{base_name}s", f"{base_name}es", 
                    f"master_{base_name}", f"{base_name}_master", f"{base_name}_m"
                ]
                for candidate in candidates:
                    matched_table = next((t for t in schema_data.keys() if t.lower() == candidate), None)
                    if matched_table and matched_table != table_name:
                        cand_cols = [c.lower() for c in schema_data[matched_table]["columns"]]
                        if "id" in cand_cols:
                            if matched_table not in graph[table_name]:
                                graph[table_name][matched_table] = {"local_column": col, "remote_column": "id", "direction": "forward", "method": "heuristic"}
                                if table_name not in graph[matched_table]:
                                    graph[matched_table][table_name] = {"local_column": "id", "remote_column": col, "direction": "reverse", "method": "heuristic"}
                            break 

    # 4. Sync Discovery to DB
    from sqlmodel import select
    stmt = select(AllowedRelationship).where(AllowedRelationship.client_id == client_id)
    all_db_rels = (await session.execute(stmt)).scalars().all()
    db_rel_map = {(r.parent_table.lower(), r.child_table.lower()): r for r in all_db_rels}
    
    new_rels_to_add = []
    mode = client_config.governance_mode or "guided"
    
    def determine_default_status(parent: str, child: str, method: str) -> bool:
        if "password" in child or "secret" in child: return False
        if mode == "strict": return False
        return True

    for table_a, relations in graph.items():
        for table_b, meta in relations.items():
            if meta["direction"] == "forward":
                child, parent = table_a, table_b
                local_col, remote_col = meta["local_column"], meta["remote_column"]
            else:
                parent, child = table_a, table_b
                remote_col, local_col = meta["local_column"], meta["remote_column"]
            
            pair_key = (parent.lower(), child.lower())
            if pair_key not in db_rel_map:
                risk_level, confidence = _calculate_risk(meta.get("method", "heuristic"), parent, child)
                is_auto_enabled = determine_default_status(parent, child, meta.get("method", "heuristic"))
                
                new_rel = AllowedRelationship(
                    client_id=client_id,
                    parent_table=parent,
                    parent_column=remote_col,
                    child_table=child,
                    child_column=local_col,
                    is_enabled=is_auto_enabled,
                    risk_level=risk_level,
                    confidence_score=confidence
                )
                new_rels_to_add.append(new_rel)
                db_rel_map[pair_key] = new_rel

    if new_rels_to_add:
        session.add_all(new_rels_to_add)
        await session.commit()
    
    clear_relationship_cache(client_id)
    return await get_all_relationships(session, client_id)

async def bulk_update_relationships(session: AsyncSession, client_id: int, action: str) -> dict:
    """
    Bulk update relationship statuses based on action.
    """
    from sqlmodel import select
    stmt = select(AllowedRelationship).where(AllowedRelationship.client_id == client_id)
    rels = (await session.execute(stmt)).scalars().all()
    
    count = 0
    for rel in rels:
        if action == "auto_unlock_safe":
            # Enable all standard Foreign Keys (risk_level: safe)
            if rel.risk_level == "safe":
                rel.is_enabled = True
                count += 1
        elif action == "auto_unlock_heuristics":
            # Enable naming-based matches (risk_level: heuristic)
            if rel.risk_level == "heuristic" and rel.confidence_score >= 0.5:
                rel.is_enabled = True
                count += 1
        elif action == "enable_all":
            # Maximum freedom mode
            rel.is_enabled = True
            count += 1
        elif action == "disable_all":
            # Reset to zero
            rel.is_enabled = False
            count += 1
        elif action == "purge_all":
            # Permanently delete from DB
            await session.delete(rel)
            count += 1
        
        if action != "purge_all":
            session.add(rel)
    
    await session.commit()

    if action == "refresh_discovery":
        # Clear cache and re-run discovery
        clear_relationship_cache(client_id)
        new_rels = await discover_and_sync_relationships(session, client_id)
        return {"status": "success", "updated_count": len(new_rels), "message": "Discovery refreshed"}

    clear_relationship_cache(client_id)
    return {"status": "success", "updated_count": count}

async def approve_join_path(session: AsyncSession, client_id: int, path_signature: str, user_id: str) -> dict:
    """
    Approves a join path. Upsert logic.
    """
    from sqlmodel import select
    stmt = select(ApprovedJoinPath).where(
        ApprovedJoinPath.client_id == client_id,
        ApprovedJoinPath.path_signature == path_signature
    )
    existing = (await session.execute(stmt)).scalars().first()
    
    if existing:
        existing.is_enabled = True
        existing.approved_by = user_id
        session.add(existing)
    else:
        new_path = ApprovedJoinPath(
            client_id=client_id,
            path_signature=path_signature,
            is_enabled=True,
            approved_by=user_id
        )
        session.add(new_path)
    
    await session.commit()
    return {"status": "success", "path": path_signature}

async def get_approved_paths(session: AsyncSession, client_id: int) -> List[ApprovedJoinPath]:
    """
    Returns all approved paths for a client.
    """
    from sqlmodel import select
    stmt = select(ApprovedJoinPath).where(ApprovedJoinPath.client_id == client_id)
    return (await session.execute(stmt)).scalars().all()

# Helper to clear cache (e.g. for debugging)
def clear_relationship_cache(client_id: Optional[int] = None):
    global _RELATIONSHIP_CACHE
    if client_id:
        if client_id in _RELATIONSHIP_CACHE:
            del _RELATIONSHIP_CACHE[client_id]
    else:
        _RELATIONSHIP_CACHE = {}

async def validate_join_path(session: AsyncSession, client_id: int, graph: Dict[str, Any], base_table: str, joins: List[Any]) -> List[Dict[str, Any]]:
    """
    Validates a join path. Now supports both linear (List[str]) and branched (List[Dict]) joins.
    Branched format: [ {"table": "customers", "parent": "sales"}, {"table": "products", "parent": "sales"} ]
    Returns a list of join details [ {from_table, to_table, local_column, remote_column} ]
    """
    if not joins:
        return []

    validated_steps = []
    visited = {base_table.lower()}
    
    # Normalize joins to branched format if they are linear strings
    normalized_joins = []
    current_linear_parent = base_table
    for j in joins:
        if isinstance(j, str):
            normalized_joins.append({"table": j, "parent": current_linear_parent})
            current_linear_parent = j
        else:
            normalized_joins.append(j)

    if len(normalized_joins) > 15: # Increased cap for branched joins
         raise HTTPException(status_code=400, detail=f"Too many joins (Max 15).")

    for join_def in normalized_joins:
        target_table = join_def["table"]
        parent_table = join_def.get("parent", base_table)
        
        if target_table.lower() in visited:
            # We allow multiple paths to the same table if needed? 
            # Standard SQL might need aliases. For simplicity, we block for now unless parent is different.
            continue
            
        if parent_table.lower() not in visited:
             raise HTTPException(status_code=400, detail=f"Invalid join: parent table '{parent_table}' must be connected before '{target_table}'.")

        # Determine Relationship
        rel_meta = None
        
        # Check Graph (Case Insensitive)
        # The graph keys are actual table names from DB. 
        # We need to find the correct casing.
        actual_parent = next((t for t in graph.keys() if t.lower() == parent_table.lower()), None)
        actual_target = next((t for t in graph.keys() if t.lower() == target_table.lower()), None)

        if actual_parent and actual_target and actual_target in graph[actual_parent]:
            rel_meta = graph[actual_parent][actual_target]
        else:
            # Check DB for disabled but existing relationship (for path approval logic)
            stmt = select(AllowedRelationship).where(
                AllowedRelationship.client_id == client_id,
                ((AllowedRelationship.parent_table.ilike(parent_table)) & (AllowedRelationship.child_table.ilike(target_table))) |
                ((AllowedRelationship.parent_table.ilike(target_table)) & (AllowedRelationship.child_table.ilike(parent_table)))
            )
            db_rel = (await session.execute(stmt)).scalars().first()
            
            if db_rel is not None:
                if db_rel.parent_table.lower() == actual_target.lower():
                     rel_meta = {"local_column": db_rel.child_column, "remote_column": db_rel.parent_column}
                else:
                     rel_meta = {"local_column": db_rel.parent_column, "remote_column": db_rel.child_column}

        if not rel_meta:
             raise HTTPException(status_code=400, detail=f"No relationship found between '{parent_table}' and '{target_table}'.")
        
        validated_steps.append({
            "from_table": parent_table,
            "to_table": target_table,
            "local_column": rel_meta["local_column"],
            "remote_column": rel_meta["remote_column"],
            "payload_columns": rel_meta.get("selected_columns", [])
        })
        
        visited.add(target_table.lower())

    return validated_steps

async def get_all_relationships(session: AsyncSession, client_id: int, sync: bool = False) -> List[AllowedRelationship]:
    """
    Returns ALL relationships (enabled or disabled) for Admin UI.
    Optionally triggers discovery.
    """
    if sync:
        await discover_and_sync_relationships(session, client_id)
    
    from sqlmodel import select
    stmt = select(AllowedRelationship).where(AllowedRelationship.client_id == client_id)
    return (await session.execute(stmt)).scalars().all()
