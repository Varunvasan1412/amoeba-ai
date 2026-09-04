from __future__ import annotations
from typing import List, Optional, Tuple, Any
from app.models.navigation import NavigationItem
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

# Global Cache (Optional, but let's stick to DB for strictly fresh multi-tenant data)
# We can still keep a small cache for static system defaults if needed.

async def load_client_sitemap(session: AsyncSession, client_id: int) -> List[dict]:
    """
    Loads all discovered and mapped routes for a specific client from the DB.
    """
    statement = select(NavigationItem).where(NavigationItem.client_id == client_id)
    result = await session.execute(statement)
    items = result.scalars().all()
    
    return [
        {
            "label": item.label,
            "path": item.path,
            "module": item.module,
            "is_custom": not item.is_discovered # Manual mappings are 'custom'
        } for item in items
    ]

def _infer_parents_from_path(path: str) -> List[str]:
    """
    Extracts explicit parents from URL path if 'parents' key is missing.
    Example: .../transaction/invoice -> ['Transaction', 'Invoice']
    Example: .../transaction/invoice_completed -> ['Transaction', 'Invoice', 'Completed']
    """
    # Normalize path separators
    path = path.replace("\\", "/")
    parts = path.split('/')
    
    # Filter out common prefixes or empty strings
    ignored = {'localhost', 'http:', 'https:', 'varun_sterling', 'sterling_company', 'application', 'controllers'}
    
    parents = []
    for p in parts:
        clean = p.strip()
        if not clean or clean.lower() in ignored or clean.isdigit():
            continue
            
        # HANDLE UNDERSCORES IN FILENAMES (CRITICAL FIX)
        # e.g., "jobcard_pending" -> ["Jobcard", "Pending"]
        if "_" in clean:
            sub_parts = clean.split("_")
            for sp in sub_parts:
                if sp and not sp.isdigit():
                    parents.append(sp.capitalize())
        else:
            parents.append(clean.capitalize())
    
    # The last element is usually the file/page itself, but in the context of "parents", 
    # we usually want the hierarchy leading UP to it. 
    # However, for display logic "Transaction -> Invoice -> Completed", including the file name as a parent 
    # helps if the label is generic like "Completed".
    # For now, let's keep all segments as potential context.
    
    return parents

async def fast_lookup_route(query: str, session: AsyncSession, client_id: int) -> Tuple[Optional[str], Optional[List[dict]]]:
    """
    Deterministic In-Memory Lookup for Navigation Fast-Path (Tenant-Aware).
    """
    routes = await load_client_sitemap(session, client_id)
    query_tokens = set(query.lower().strip().split())
    
    processed_routes = []
    for r in routes:
        r_mod = r.copy()
        if "parents" not in r_mod:
            r_mod["parents"] = _infer_parents_from_path(r_mod["path"])
        processed_routes.append(r_mod)

    # ---------------------------------------------------------
    # 1. EXACT LABEL MATCH (Highest Priority)
    # ---------------------------------------------------------
    exact_matches = []
    for r in processed_routes:
        if r["label"].lower() == query.lower().strip():
            exact_matches.append(r)
    
    # Priority A: If there is an EXACT match that is CUSTOM, return it immediately
    custom_exact = [r for r in exact_matches if r.get("is_custom")]
    if len(custom_exact) == 1:
        print(f"🎯 [Navigation] Prioritizing Custom Route: {custom_exact[0]['path']}")
        return custom_exact[0]["path"], None

    if len(exact_matches) == 1:
        return exact_matches[0]["path"], None # Single match
        
    if len(exact_matches) > 1:
        # Deep ambiguity (Same label, different path) -> Return FULL objects
        
        # Deduplicate identical paths (e.g. same menu item in different nav trees)
        unique_matches = []
        seen_paths = set()
        for m in sorted(exact_matches, key=lambda x: x.get("is_custom", False), reverse=True):
            if m["path"] not in seen_paths:
                unique_matches.append(m)
                seen_paths.add(m["path"])
                
        if len(unique_matches) == 1:
             return unique_matches[0]["path"], None
             
        print(f"⚖️ [Navigation] Found {len(unique_matches)} unique candidates for '{query}'")
        return None, unique_matches

    # ---------------------------------------------------------
    # 2. TOKEN-BASED COMPOUND MATCH (Order-Independent)
    #    Score = (Matched Label Tokens) + (Matched Parent Tokens)
    # ---------------------------------------------------------
    scored_candidates = []
    
    for r in processed_routes:
        label_tokens = set(r["label"].lower().split())
        parent_tokens = set(p.lower() for p in r["parents"])
        
        # We want to match ALL query tokens against the union of (Label + Parents)
        doc_tokens = label_tokens.union(parent_tokens)
        
        # Check if ALL query tokens are present in the doc_tokens
        if query_tokens.issubset(doc_tokens):
            label_overlap = len(query_tokens.intersection(label_tokens))
            score = 100 + label_overlap
            scored_candidates.append((score, r))

    # 3. SEMANTIC VECTOR MATCH (pgvector fallback for fastpath)
    if not scored_candidates:
        try:
            import os
            if os.getenv("OPENAI_API_KEY"):
                from langchain_openai import OpenAIEmbeddings
                from sqlmodel import select
                from app.models.navigation import NavigationItem
                
                embedder = OpenAIEmbeddings(model="text-embedding-3-small")
                query_vector = await embedder.aembed_query(query)
                
                # Fetch top 5 vector matches
                stmt = select(NavigationItem).where(
                    NavigationItem.client_id == client_id,
                    NavigationItem.embedding != None
                ).order_by(NavigationItem.embedding.cosine_distance(query_vector)).limit(5)
                
                vec_res = await session.execute(stmt)
                vec_items = vec_res.scalars().all()
                
                if vec_items:
                    # Convert to the expected ambiguous_list format
                    ambig_list = []
                    for item in vec_items:
                        ambig_list.append({
                            "label": item.label,
                            "path": item.path,
                            "module": item.module,
                            "is_custom": not item.is_discovered,
                            "parents": [item.module] if item.module else []
                        })
                    print(f"🎯 [FastPath Vector Search] Found {len(ambig_list)} semantic matches for '{query}'")
                    return None, ambig_list
        except Exception as e:
            print(f"⚠️ [FastPath Vector Search] Failed: {e}")

    # Sort by score desc
    scored_candidates.sort(key=lambda x: x[0], reverse=True)
    
    # Filter top tier
    if scored_candidates:
        best_score = scored_candidates[0][0]
        best_matches = [item[1] for item in scored_candidates if item[0] == best_score]
        
        if len(best_matches) == 1:
            return best_matches[0]["path"], None
        else:
            unique_best = []
            seen_paths = set()
            for m in best_matches:
                if m["path"] not in seen_paths:
                    unique_best.append(m)
                    seen_paths.add(m["path"])
            
            if len(unique_best) == 1:
                return unique_best[0]["path"], None
            return None, unique_best

    # 4. SUBSTRING/FUZZY FALLBACK
    substring_matches = []
    for r in processed_routes:
        if query.lower() in r["label"].lower():
            substring_matches.append(r)
            
    if len(substring_matches) == 1:
        return substring_matches[0]["path"], None
    if len(substring_matches) > 1:
        unique_sub = []
        seen_paths = set()
        for m in substring_matches:
            if m["path"] not in seen_paths:
                unique_sub.append(m)
                seen_paths.add(m["path"])
        
        if len(unique_sub) == 1:
             return unique_sub[0]["path"], None
        return None, unique_sub
        
    # 5. DIFFLIB FUZZY MATCH (Final Fallback)
    import difflib
    all_labels = [r["label"] for r in processed_routes]
    # We use a lower cutoff (0.5) to catch spaced words like "pre welding list" vs "preweldinglist"
    fuzzy_results = difflib.get_close_matches(query.lower(), [l.lower() for l in all_labels], n=5, cutoff=0.5)
    
    if fuzzy_results:
        fuzzy_matches = []
        seen_paths = set()
        for fuzzy_label in fuzzy_results:
            for r in processed_routes:
                if r["label"].lower() == fuzzy_label:
                    if r["path"] not in seen_paths:
                        fuzzy_matches.append(r)
                        seen_paths.add(r["path"])
        
        if len(fuzzy_matches) == 1:
            return fuzzy_matches[0]["path"], None
        if len(fuzzy_matches) > 1:
            return None, fuzzy_matches
            
    return None, None


async def lookup_external_route(query: str, session: AsyncSession, client_id: int) -> str:
    """
    Tenant-Aware fallback search for a route using pgvector and semantic search.
    """
    import os
    import json
    from app.models.navigation import NavigationItem
    
    query = query.lower().strip()
    
    # 1. Exact Name/Label Match (Fastest)
    routes = await load_client_sitemap(session, client_id)
    for route in routes:
        if route["label"].lower() == query:
            return json.dumps([route])
            
    # 2. Vector Semantic Search (pgvector)
    vector_matches = []
    embedder = None
    if os.getenv("OPENAI_API_KEY"):
        try:
            from langchain_openai import OpenAIEmbeddings
            embedder = OpenAIEmbeddings(model="text-embedding-3-small")
            query_vector = await embedder.aembed_query(query)
            
            # Perform pgvector cosine distance search
            # Order by smallest distance (closest match)
            stmt = select(NavigationItem).where(
                NavigationItem.client_id == client_id,
                NavigationItem.embedding != None
            ).order_by(NavigationItem.embedding.cosine_distance(query_vector)).limit(5)
            
            vec_res = await session.execute(stmt)
            vec_items = vec_res.scalars().all()
            
            for item in vec_items:
                vector_matches.append({
                    "label": item.label,
                    "path": item.path,
                    "module": item.module,
                    "is_custom": not item.is_discovered
                })
                
            if vector_matches:
                print(f"🎯 [Vector Search] Found {len(vector_matches)} semantic matches for '{query}'")
                return json.dumps(vector_matches)
                
        except Exception as e:
            print(f"⚠️ [Vector Search] Failed: {e}. Falling back to fuzzy matching.")

    # 3. Scored Matching / Fuzzy Match (Fallback)
    scored_matches = []
    query_parts = set(query.split())
    
    for route in routes:
        label = route["label"].lower()
        label_parts = set(label.split())
        
        score = 0
        
        # A. Containment (High Score)
        if query in label: score += 50
        if label in query: score += 50
        
        # B. Exact Word Overlap
        intersection = query_parts.intersection(label_parts)
        score += len(intersection) * 10
        
        if score > 0:
            scored_matches.append({"route": route, "score": score})

    import difflib
    all_labels = [r["label"] for r in routes]
    fuzzy_results = difflib.get_close_matches(query, all_labels, n=3, cutoff=0.6)
    
    for fuzzy_label in fuzzy_results:
        found = False
        for sm in scored_matches:
            if sm["route"]["label"] == fuzzy_label:
                found = True
                break
        if not found:
             for r in routes:
                 if r["label"] == fuzzy_label:
                     scored_matches.append({"route": r, "score": 5}) 
    
    # Sort by Score DESC
    scored_matches.sort(key=lambda x: x["score"], reverse=True)
    final_matches = [m["route"] for m in scored_matches[:10]]
    
    if not final_matches:
        return "No route found."
        
    return json.dumps(final_matches)

async def add_external_route(label: str, path: str, session: AsyncSession, client_id: int, keywords: List[str] = []) -> str:
    """Adds a new manual route to the DB for a client."""
    # Logic: Check if exact path exists, if so update label. 
    # But usually admin uses the RouteMap UI for this.
    statement = select(NavigationItem).where(
        NavigationItem.client_id == client_id,
        NavigationItem.path == path
    )
    result = await session.execute(statement)
    item = result.scalars().first()
    
    if item:
        item.label = label
        action = "Updated"
    else:
        new_item = NavigationItem(
            label=label,
            path=path,
            client_id=client_id,
            is_discovered=False # Manually added
        )
        session.add(new_item)
        action = "Added"
        
    await session.commit()
    return f"{action} route '{label}' pointing to {path}"

async def batch_learn_routes(new_routes: List[dict], session: AsyncSession, client_id: int) -> str:
    """
    Bulk adds discovered routes to the database for a specific client.
    Enriches them with Module, Table Name, and Descriptive Labels using the Intelligence Engine.
    Also generates pgvector embeddings for Semantic Vector Search.
    """
    from app.models.client_config import ClientConfig
    from app.services.onboarding import discover_tables
    import os
    
    # 0. Fetch Client Config to get DB URL for table discovery
    client_stmt = select(ClientConfig).where(ClientConfig.id == client_id)
    client_res = await session.execute(client_stmt)
    client_config = client_res.scalars().first()
    
    db_tables = []
    if client_config:
        try:
            tables_raw = discover_tables(client_config.db_connection_url)
            db_tables = [t["name"].lower() for t in tables_raw]
        except Exception as e:
            print(f"⚠️ [AUTO MAP] Could not discover tables for client {client_id}: {e}")

    # Initialize OpenAI Embedder (for Vector Search)
    embedder = None
    if os.getenv("OPENAI_API_KEY"):
        try:
            from langchain_openai import OpenAIEmbeddings
            embedder = OpenAIEmbeddings(model="text-embedding-3-small")
        except Exception as e:
            print(f"⚠️ [EMBEDDINGS] Could not initialize OpenAI Embedder: {e}")

    count = 0
    for item in new_routes:
        label = item.get("label", "").strip()
        path = item.get("path", "").strip()
        
        if not label or not path or len(label) < 2: 
            continue
        if "javascript:" in path or path == "#" or "void(0)" in path:
            continue
            
        # Normalization: Strip host if full URL provided
        if "://" in path:
            try:
                from urllib.parse import urlparse
                path = urlparse(path).path
            except:
                pass
            
        # Check if this path already exists for this client
        statement = select(NavigationItem).where(
            NavigationItem.client_id == client_id,
            NavigationItem.path == path
        )
        result = await session.execute(statement)
        existing = result.scalars().first()
        
        # 🧠 INTELLIGENCE ENGINE: Auto-Map Logic
        if not existing or existing.module is None or existing.table_name is None or existing.embedding is None:
            module = infer_module_from_path(path)
            entity = infer_entity_keyword(path, label)
            matched_table = match_entity_to_table(entity, db_tables)
            better_label = generate_friendly_label(module, entity)
            
            # Generate Vector Embedding for Semantic Search
            embedding_vector = None
            if embedder:
                search_text = f"Route: {better_label}. Module: {module or ''}. Path: {path}"
                try:
                    embedding_vector = await embedder.aembed_query(search_text)
                except Exception as e:
                    print(f"⚠️ [EMBEDDINGS] Error generating vector for {path}: {e}")
            
            print(f"🧠 [AUTO MAP] path={path} → module={module}, table={matched_table}, label={better_label}, vectorized={bool(embedding_vector)}")

            if existing:
                # Only update if current data is missing (don't override manual config)
                if existing.module is None: existing.module = module
                if existing.table_name is None: existing.table_name = matched_table
                if existing.embedding is None and embedding_vector: existing.embedding = embedding_vector
                # Update label if it's too short or contains technical chars
                if len(existing.label) < 5 or "_" in existing.label:
                    existing.label = better_label
            else:
                new_item = NavigationItem(
                    label=better_label,
                    path=path,
                    module=module,
                    table_name=matched_table,
                    client_id=client_id,
                    is_discovered=True,
                    embedding=embedding_vector
                )
                session.add(new_item)
                count += 1
            
    await session.commit()
    return f"Learned {count} new routes for Client {client_id} (Enriched via Intelligence Engine & pgvector)."

# --- INTELLIGENCE ENGINE HELPERS ---

def infer_module_from_path(path: str) -> Optional[str]:
    """Extracts module from path (e.g., /sales/enquiry/create -> Sales)."""
    parts = [p for p in path.split('/') if p]
    ignored = {
        "create", "edit", "list", "view", "index", "delete", "update", 
        "new", "save", "search", "application", "controllers", "aspx", "php", "html",
        "demopower04", "home", "app"
    }
    for p in parts:
        clean = p.lower().split('.')[0] # remove extension
        if clean not in ignored and not clean.isdigit():
            return clean.capitalize()
    return None

def infer_entity_keyword(path: str, label: str) -> str:
    """Extracts entity keyword from path or label."""
    # 1. Try path (last meaningful segment)
    parts = [p for p in path.split('/') if p]
    ignored = {"create", "edit", "list", "view", "index", "delete", "update", "new", "save", "search"}
    
    entity = None
    for p in reversed(parts):
        clean = p.lower().split('.')[0]
        if clean not in ignored and not clean.isdigit():
            entity = clean
            break
            
    if not entity:
        # 2. Fallback to label
        entity = label.lower().replace("create", "").replace("new", "").replace("list", "").replace("_", " ").strip()
        
    return entity

def match_entity_to_table(entity: str, db_tables: List[str]) -> Optional[str]:
    """Matches entity keyword against actual DB tables with support for common CRM/ERP suffixes."""
    if not db_tables: return None
    
    entity = entity.lower().strip()
    
    # 1. Exact match
    if entity in db_tables:
        return entity
        
    # 2. Suffix matches (_detail, _master, _header, _head, _ms, _tran)
    # Common in ERP/CRM systems
    for suffix in ["_detail", "_master", "_header", "_head", "_tran", "_ms"]:
        if f"{entity}{suffix}" in db_tables:
            return f"{entity}{suffix}"
            
    # 3. Contains match (Fallback)
    for t in db_tables:
        if entity in t:
            return t
            
    return None

def generate_friendly_label(module: Optional[str], entity: str) -> str:
    """Generates a premium, friendly label (e.g., Sales Enquiry)."""
    # Clean entity
    display_entity = entity.replace("_", " ").title()
    
    # Basic Singularization
    if display_entity.endswith("ies"):
        display_entity = display_entity[:-3] + "y"
    elif display_entity.endswith("s") and not display_entity.endswith("ss"):
        display_entity = display_entity[:-1]
        
    if module:
        # Avoid redundancy (e.g., "Sales Sales Order" -> "Sales Order")
        if module.lower() in display_entity.lower():
            return display_entity
        return f"{module} {display_entity}"
        
    return display_entity
