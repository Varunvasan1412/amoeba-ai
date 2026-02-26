
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
    Returns the Relationship Graph for a client.
    Format:
    {
      "sales": {
         "customers": {"local_column": "customer_id", "remote_column": "id"}
      }
    }
    """
    if client_id in _RELATIONSHIP_CACHE:
        return _RELATIONSHIP_CACHE[client_id]

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
        return {}

    # 3. Build Graph
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
            
            # Forward Link
            graph[table_name][referred_table] = {
                "local_column": local_col,
                "remote_column": remote_col,
                "direction": "forward",
                "method": "explicit"
            }
            # Reverse Link
            graph[referred_table][table_name] = {
                "local_column": remote_col,
                "remote_column": local_col,
                "direction": "reverse",
                "method": "explicit"
            }

    # 3b. Heuristic (Semantic) Discovery
    print(f"DEBUG: Starting Heuristic Discovery for Client {client_id}")
    for table_name, data in schema_data.items():
        columns = data.get("columns", [])
        # Lowercase columns for matching
        lower_cols = [c.lower() for c in columns]
        
        for col in columns:
            l_col = col.lower()
            if (l_col.endswith("_id") or l_col.endswith("id")) and l_col != "id":
                # Possible relationship
                # Try to extract base name: country_id -> country, countryId -> country
                base_name = l_col[:-3] if l_col.endswith("_id") else l_col[:-2]
                
                # Potential candidate tables (normalized to lowercase for matching)
                candidates = [base_name, f"master_{base_name}", f"marketing_{base_name}"]
                
                for candidate in candidates:
                    # Case-insensitive table search
                    matched_table = None
                    for actual_table in schema_data.keys():
                        if actual_table.lower() == candidate:
                            matched_table = actual_table
                            break
                            
                    if matched_table and matched_table != table_name:
                        # Ensure candidate has an 'id' column (case-insensitive)
                        cand_cols = [c.lower() for c in schema_data[matched_table]["columns"]]
                        if "id" in cand_cols:
                            # Found Heuristic Relationship
                            if matched_table not in graph[table_name]:
                                print(f"DEBUG: ✅ Linked {table_name}.{col} -> {matched_table}.id (Heuristic)")
                                graph[table_name][matched_table] = {
                                    "local_column": col,
                                    "remote_column": "id",
                                    "direction": "forward",
                                    "method": "heuristic"
                                }
                                # Reverse link: Parent -> Child
                                if table_name not in graph[matched_table]:
                                    graph[matched_table][table_name] = {
                                        "local_column": "id",
                                        "remote_column": col,
                                        "direction": "reverse",
                                        "method": "heuristic"
                                    }
                            break 

    # 4. Sync with Governance Layer (AllowedRelationship) of the Database
    # We will iterate through the raw graph and check/update the DB.
    # Only ENABLED relationships will be added to the final builder_graph.

    from sqlmodel import select
    # AllowedRelationship imported at top level now

    # Fetch existing rules
    stmt = select(AllowedRelationship).where(AllowedRelationship.client_id == client_id)
    existing_rels = (await session.execute(stmt)).scalars().all()
    # Map (parent, child) -> rel object
    rel_map = {(r.parent_table, r.child_table): r for r in existing_rels}
    
    # ---------------------------------------------------------
    # GOVERNANCE MODE LOGIC (Phase 2.18)
    # ---------------------------------------------------------
    mode = client_config.governance_mode or "guided"
    print(f"DEBUG: Applying Governance Mode: {mode.upper()}")
    
    def determine_default_status(parent: str, child: str, method: str) -> bool:
        """
        Returns True if relationship should be ENABLED by default.
        """
        # Global Rule: Never auto-enable system tables or PII (simplified check)
        if "password" in child or "secret" in child: return False
        
        if mode == "strict":
            return False # Default Deny
            
        if mode == "simple":
            return True # Auto-enable everything (except global blocks)
            
        if mode == "guided":
            # Enable "safe" links (explicit FKs are usually safe)
            # Heuristics are safer if they match exact patterns
            if method == "explicit": return True
            if method == "heuristic": return True # For now, allow heuristic too in guided
            return False
            
        return False # Fallback

    builder_graph = {}
    new_rels_to_add = []
    
    # Helper to init builder graph nodes
    for t in graph.keys():
        builder_graph[t] = {}

    # Iterate raw graph
    processed_pairs = set()

    for table_a, relations in graph.items():
        for table_b, meta in relations.items():
            if meta["direction"] == "forward":
                child = table_a
                parent = table_b
                local_col_name = meta["local_column"] # FK on child
                remote_col_name = meta["remote_column"] # PK on parent
            else:
                parent = table_a
                child = table_b
                local_col_name = meta["remote_column"] # FK on child
                remote_col_name = meta["local_column"] # PK on parent
            
            method = meta.get("method", "heuristic")

            pair_key = (parent, child)
            if pair_key in processed_pairs:
                continue
            processed_pairs.add(pair_key)

            # Check DB
            allowed_rel = rel_map.get(pair_key)
            
            if not allowed_rel:
                # New Discovery! Apply Mode Logic.
                is_auto_enabled = determine_default_status(parent, child, method)
                risk_level, confidence = _calculate_risk(method, parent, child)

                print(f"DEBUG: New Relationship: {parent}->{child} ({method}). Mode={mode}, Enabled={is_auto_enabled}, Risk={risk_level}")
                
                new_rel = AllowedRelationship(
                    client_id=client_id,
                    parent_table=parent,
                    parent_column=remote_col_name,
                    child_table=child,
                    child_column=local_col_name,
                    is_enabled=is_auto_enabled, 
                    is_restricted=False,
                    risk_level=risk_level,
                    confidence_score=confidence
                )
                new_rels_to_add.append(new_rel)
                # Cache it locally so we don't re-add
                rel_map[pair_key] = new_rel 
                is_enabled = is_auto_enabled
            else:
                # Existing rule: Respect DB unless forced override (not implementing force override yet)
                # In Strict/Guided, user manual toggle prevails.
                is_enabled = allowed_rel.is_enabled and not allowed_rel.is_restricted

            # Add to Builder Graph if Enabled
            if is_enabled:
                # Add Forward Link (table_a -> table_b)
                if table_b in graph.get(table_a, {}):
                    builder_graph[table_a][table_b] = graph[table_a][table_b]
                
                # Check B -> A in raw graph
                if table_a in graph.get(table_b, {}):
                    builder_graph[table_b][table_a] = graph[table_b][table_a]
    
    # Bulk Insert New Rels
    if new_rels_to_add:
        session.add_all(new_rels_to_add)
        await session.commit()
        print(f"DEBUG: Persisted {len(new_rels_to_add)} new relationships.")

    print(f"DEBUG: Discovery Complete. Raw Joins: {sum(len(v) for v in graph.values())}. Licensed Joins: {sum(len(v) for v in builder_graph.values())}")
    
    _RELATIONSHIP_CACHE[client_id] = builder_graph
    return builder_graph

async def bulk_update_relationships(session: AsyncSession, client_id: int, action: str) -> dict:
    """
    Bulk update relationship statuses based on action.
    actions: 'enable_safe', 'disable_heuristic', 'reset_defaults'
    """
    from sqlmodel import select
    stmt = select(AllowedRelationship).where(AllowedRelationship.client_id == client_id)
    rels = (await session.execute(stmt)).scalars().all()
    
    count = 0
    for rel in rels:
        if action == "enable_safe":
            if rel.risk_level == "safe":
                rel.is_enabled = True
                count += 1
        elif action == "disable_heuristic":
            if rel.risk_level == "heuristic":
                rel.is_enabled = False
                count += 1
        # Add more actions as needed
        
        session.add(rel)
    
    await session.commit()
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

async def validate_join_path(session: AsyncSession, client_id: int, graph: Dict[str, Any], base_table: str, joins: List[str]) -> List[Dict[str, Any]]:
    """
    Validates a linear join path: Base -> Join1 -> Join2 ...
    Returns a list of join details [ {from_table, to_table, local_column, remote_column} ]
    Ensures path is either fully enabled OR explicitly approved.
    """
    if not joins:
        return []

    # 1. Path Signature construction
    path_tables = [base_table] + joins
    path_signature = "->".join(path_tables)

    # 2. Check for Path Approval Override
    from sqlmodel import select
    stmt = select(ApprovedJoinPath).where(
        ApprovedJoinPath.client_id == client_id,
        ApprovedJoinPath.path_signature == path_signature,
        ApprovedJoinPath.is_enabled == True
    )
    approved_path = (await session.execute(stmt)).scalars().first()
    is_path_approved = approved_path is not None

    validated_steps = []
    current_table = base_table
    visited = {base_table}

    if len(joins) > 10: # Safety Cap
         raise HTTPException(status_code=400, detail=f"Join path too long (Max 10). Simplify your report.")

    for target_table in joins:
        if target_table in visited:
            raise HTTPException(status_code=400, detail=f"Circular or redundant join detected: {target_table}")
        
        # Determine Relationship (Enabled or definitions from DB if path approved)
        rel_meta = None
        
        # A. Check Enabled Graph
        if current_table in graph and target_table in graph[current_table]:
            rel_meta = graph[current_table][target_table]
        
        # B. If not in graph, but path approved, fetch definition from DB
        elif is_path_approved:
            # We need to find the definition. 
            # We assume it exists in AllowedRelationship but is disabled.
            # We need to query AllowedRelationship for (current, target)
            stmt = select(AllowedRelationship).where(
                AllowedRelationship.client_id == client_id,
                AllowedRelationship.parent_table == target_table, # Parent is target in standard FK view? 
                AllowedRelationship.child_table == current_table 
                # Note: AllowedRelationship stores Parent->Child.
                # In graph, we normalize forward/reverse.
                # Here we need to find *data* to join.
                # Use helper or extensive search? 
                # Simplest: Fetch any relationship between these two.
            )
            # Actually, let's try both directions
            stmt = select(AllowedRelationship).where(
                AllowedRelationship.client_id == client_id,
                ((AllowedRelationship.parent_table == current_table) & (AllowedRelationship.child_table == target_table)) |
                ((AllowedRelationship.parent_table == target_table) & (AllowedRelationship.child_table == current_table))
            )
            db_rel = (await session.execute(stmt)).scalars().first()
            
            if db_rel:
                # Construct meta on fly
                if db_rel.parent_table == target_table:
                     # Join Current(Child) -> Target(Parent)
                     rel_meta = {
                         "local_column": db_rel.child_column,
                         "remote_column": db_rel.parent_column,
                         "direction": "forward" # Arbitrary, effectively we enable it
                     }
                else:
                     # Join Current(Parent) -> Target(Child)
                     rel_meta = {
                         "local_column": db_rel.parent_column,
                         "remote_column": db_rel.child_column,
                         "direction": "reverse"
                     }

        if not rel_meta:
             if is_path_approved:
                  raise HTTPException(status_code=500, detail=f"Approved path contains missing relationship definition: {current_table}->{target_table}")
             else:
                  raise HTTPException(status_code=400, detail=f"No enabled foreign key found between '{current_table}' and '{target_table}'. Path not approved.")
        
        validated_steps.append({
            "from_table": current_table,
            "to_table": target_table,
            "local_column": rel_meta["local_column"],
            "remote_column": rel_meta["remote_column"]
        })
        
        visited.add(target_table)
        current_table = target_table 

    return validated_steps

async def get_all_relationships(session: AsyncSession, client_id: int) -> List[AllowedRelationship]:
    """
    Returns ALL relationships (enabled or disabled) for Admin UI.
    First ensures discovery is run to populate the DB.
    """
    # Force discovery run to sync DB
    await get_relationship_graph(session, client_id)
    
    from sqlmodel import select
    stmt = select(AllowedRelationship).where(AllowedRelationship.client_id == client_id)
    return (await session.execute(stmt)).scalars().all()
