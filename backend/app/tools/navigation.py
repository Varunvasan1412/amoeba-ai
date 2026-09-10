from __future__ import annotations
import re
from typing import List, Optional, Tuple, Any
from urllib.parse import urlparse
from app.models.navigation import NavigationItem
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

# Global Cache (Optional, but let's stick to DB for strictly fresh multi-tenant data)
# We can still keep a small cache for static system defaults if needed.

def _normalize_route_path(path: str) -> str:
    """
    Normalizes URLs to clean root-relative paths.
    Strips hostnames and local development directory prefixes (e.g. /newlook/, /varun_sterling/, /htdocs/).
    """
    if not path:
        return "/"
    p = path.replace("\\", "/").strip()
    if "://" in p:
        try:
            p = urlparse(p).path
        except:
            pass
    # Strip local development folder prefixes
    p = re.sub(r"^/(?:newlook|varun_sterling|sterling_company|application|htdocs|www)/", "/", p, flags=re.IGNORECASE)
    if not p.startswith("/"):
        p = "/" + p
    return p

def _stem_token(token: str) -> str:
    """Universal singularization for English nouns."""
    t = token.lower().strip()
    if len(t) <= 3:
        return t
    if t.endswith("ies") and len(t) > 4:
        return t[:-3] + "y"
    if t.endswith("ses") or t.endswith("xes") or t.endswith("shes") or t.endswith("ches"):
        return t[:-2]
    if t.endswith("s") and not t.endswith("ss"):
        return t[:-1]
    return t

def _infer_parents_from_path(path: str, module: Optional[str] = None) -> List[str]:
    """
    Extracts explicit parents from URL path if 'parents' key is missing.
    Example: .../transaction/invoice -> ['Transaction', 'Invoice']
    Example: .../transaction/invoice_completed -> ['Transaction', 'Invoice', 'Completed']
    """
    norm_path = _normalize_route_path(path)
    parts = norm_path.split('/')
    
    # Filter out common prefixes or empty strings
    ignored = {
        'localhost', 'http:', 'https:', 'varun_sterling', 'sterling_company', 
        'application', 'controllers', 'newlook', 'ahattrickz', 'htdocs', 'www'
    }
    
    parents = []
    if module and module.strip():
        parents.append(module.strip().capitalize())
        
    for p in parts:
        clean = p.strip()
        if not clean or clean.lower() in ignored or clean.isdigit():
            continue
        if module and clean.lower() == module.lower():
            continue
            
        # HANDLE UNDERSCORES IN FILENAMES (CRITICAL FIX)
        # e.g., "jobcard_pending" -> ["Jobcard", "Pending"]
        if "_" in clean:
            sub_parts = clean.split("_")
            for sp in sub_parts:
                if sp and not sp.isdigit() and sp.lower() not in ignored:
                    parents.append(sp.capitalize())
        else:
            parents.append(clean.capitalize())
            
    # Deduplicate while preserving order
    deduped = []
    for p in parents:
        if p not in deduped:
            deduped.append(p)
    return deduped

async def load_client_sitemap(session: AsyncSession, client_id: int) -> List[dict]:
    """
    Loads all discovered and mapped routes for a specific client from the DB.
    Deduplicates phantom folder duplicates and prioritizes official ERP menu items.
    """
    statement = select(NavigationItem).where(NavigationItem.client_id == client_id)
    result = await session.execute(statement)
    items = result.scalars().all()
    
    # Sort items so that custom routes and routes with an official module come first
    sorted_items = sorted(
        items,
        key=lambda it: (not it.is_discovered, bool(it.module), len(it.path or "")),
        reverse=True
    )
    
    routes = []
    seen_keys = set()
    for item in sorted_items:
        raw_path = (item.path or "").strip()
        
        # 1. Skip internal view template files, demos, AJAX endpoints, and backup files
        path_lower = raw_path.lower()
        if any(bad in path_lower for bad in ['/views/', '/templates/', '.php', '.blade', '.twig', '/app/views/', '.html', '/bs5/', '/backup/', 'totalsalesjson', '/test/']):
            continue

        # Skip internal backend AJAX/controller helper endpoints that are not UI navigation pages
        last_segment = path_lower.split('/')[-1]
        if (last_segment.startswith(('get', 'search', 'save', 'delete', 'update', 'fetch', 'ajax', 'geocode', 'reverse', 'create', 'add')) or
            last_segment.endswith(('save', 'delete', 'update', 'byid', 'bybrand', 'details', 'detail', 'map', 'print', 'pdf', 'action', 'stage', 'json', '_json', '_ajax', '_data')) or
            any(k in last_segment for k in ['convertsave', 'productrate', 'glassprice', 'deliveryaction', 'jobcard_stage', 'pending_delivery_stage', '_json', '_ajax'])):
            if not last_segment.endswith(('list', 'page', 'screen', 'index', 'view')):
                continue

        norm_path = _normalize_route_path(raw_path)
        
        # 2. Strip trailing numeric ID segments (e.g. /inventory/grn_complete/1 -> /inventory/grn_complete)
        # to collapse duplicate parameterized tab links into their canonical parent route
        canonical_path = re.sub(r'/\d+$', '', norm_path)
        if not canonical_path.startswith('/'):
            canonical_path = '/' + canonical_path
            
        # 3. Clean up label if it starts with client/company name
        clean_label = item.label or ""
        clean_label = re.sub(r'^(?:newlook|varun_sterling|sterling_company)[\s\-:]+', '', clean_label, flags=re.IGNORECASE).strip()
        if not clean_label:
            clean_label = item.label
            
        # 4. Infer clean module if module was set to client name or is empty
        module_val = item.module
        if not module_val or module_val.lower() in {'newlook', 'varun_sterling', 'sterling_company', 'app', 'default'}:
            url_parts = [p for p in canonical_path.split('/') if p]
            module_val = url_parts[0].capitalize() if url_parts else None

        key = (clean_label.lower().strip(), canonical_path.lower())
        if key in seen_keys:
            continue
        seen_keys.add(key)
        
        routes.append({
            "label": clean_label,
            "path": canonical_path,
            "module": module_val,
            "is_custom": not item.is_discovered,
            "parents": _infer_parents_from_path(canonical_path, module_val)
        })
        
    # 5. Enrich with Codebase Semantic Mappings
    try:
        from app.models.semantic_mapping import SemanticMapping
        sm_stmt = select(SemanticMapping).where(SemanticMapping.client_id == client_id)
        sm_result = await session.execute(sm_stmt)
        for sm in sm_result.scalars().all():
            if not sm.ui_label or not sm.source_file:
                continue
            m = re.search(r'([a-zA-Z0-9_]+)\.php::(?:([a-zA-Z0-9_]+)/)?([a-zA-Z0-9_]+)', sm.source_file)
            if m:
                ctrl_p = m.group(1).lower()
                act_p = (m.group(3) or m.group(2) or "").lower()
                if act_p in ['construct', '__construct', 'get_instance']:
                    continue
                r_path = f"/{ctrl_p}/{act_p}" if act_p not in ['index', 'main'] else f"/{ctrl_p}"
                clean_lbl = sm.ui_label.strip()
                k = (clean_lbl.lower(), r_path.lower())
                if k not in seen_keys:
                    seen_keys.add(k)
                    routes.append({
                        "label": clean_lbl,
                        "path": r_path,
                        "module": ctrl_p.capitalize(),
                        "is_custom": True,
                        "parents": _infer_parents_from_path(r_path, ctrl_p.capitalize())
                    })
    except Exception as e:
        print(f"⚠️ [Navigation] Error enriching routes from SemanticMapping: {e}")
        
    return routes

async def fast_lookup_route(query: str, session: AsyncSession, client_id: int) -> Tuple[Optional[str], Optional[List[dict]]]:
    """
    Deterministic In-Memory Lookup for Navigation Fast-Path (Tenant-Aware).
    """
    routes = await load_client_sitemap(session, client_id)
    query_tokens = set(query.lower().strip().split())
    
    is_export_requested = bool(re.search(r"\b(print|pdf|export|download|xlsx|excel|csv)\b", query.lower()))
    
    processed_routes = routes
    if not is_export_requested:
        filtered_routes = []
        for r in routes:
            r_path = r["path"].lower()
            r_label = r["label"].lower()
            # Ignore print/pdf document sub-actions for general page navigation commands
            if any(bad in r_path or bad in r_label for bad in ["/print", "print_", "_print", "print", "_pdf", "pdf_", "/pdf"]):
                continue
            filtered_routes.append(r)
        if filtered_routes:
            processed_routes = filtered_routes

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
        for m in sorted(exact_matches, key=lambda x: (x.get("is_custom", False), bool(x.get("module"))), reverse=True):
            norm_p = _normalize_route_path(m["path"])
            if norm_p not in seen_paths:
                unique_matches.append(m)
                seen_paths.add(norm_p)
                
        if len(unique_matches) == 1:
             return unique_matches[0]["path"], None
             
        print(f"⚖️ [Navigation] Found {len(unique_matches)} unique candidates for '{query}'")
        return None, unique_matches

    # ---------------------------------------------------------
    # 2. TOKEN-BASED COMPOUND MATCH (Order-Independent)
    #    Score = (Matched Label Tokens) + (Matched Parent Tokens)
    # ---------------------------------------------------------
    scored_candidates = []
    stopwords = {"list", "page", "screen", "table", "view", "menu", "details", "the", "a", "an", "all", "of"}
    core_query_tokens = query_tokens - stopwords
    match_tokens = core_query_tokens if core_query_tokens else query_tokens
    
    ALIAS_MAP = {
        "challan": "delivery",
        "dc": "delivery",
        "po": "purchase",
        "grn": "inventory",
        "history": "list",
        "log": "list",
        "logs": "list",
        "record": "list",
        "records": "list",
        "entries": "list",
        "quote": "quotation",
        "bill": "invoice",
        "bills": "invoice"
    }
    stemmed_match_tokens = {_stem_token(ALIAS_MAP.get(t, t)) for t in match_tokens}
    stemmed_query_tokens = {_stem_token(ALIAS_MAP.get(t, t)) for t in query_tokens}
    
    for r in processed_routes:
        label_tokens = set(r["label"].lower().split())
        parent_tokens = set(p.lower() for p in r["parents"])
        
        # We want to match ALL core query tokens against the union of (Label + Parents)
        doc_tokens = label_tokens.union(parent_tokens)
        stemmed_doc_tokens = {_stem_token(t) for t in doc_tokens}
        
        # Check if ALL core query tokens are present in doc_tokens (exact or singularized)
        if match_tokens.issubset(doc_tokens) or stemmed_match_tokens.issubset(stemmed_doc_tokens):
            stemmed_label_tokens = {_stem_token(t) for t in label_tokens}
            stemmed_core_label = stemmed_label_tokens - {_stem_token(s) for s in stopwords}
            stemmed_core_query = stemmed_match_tokens

            label_overlap = len(stemmed_query_tokens.intersection(stemmed_label_tokens))
            
            # Universal Specificity & Precision Scoring:
            # Penalize routes with extra discriminating label tokens that were NOT requested in the query
            unmatched_label_tokens = stemmed_core_label - stemmed_query_tokens
            extra_token_penalty = len(unmatched_label_tokens) * 25
            
            # Penalize unmatched parent tokens to avoid matching deeper sub-pages
            stemmed_parent_tokens = {_stem_token(t) for t in parent_tokens}
            stemmed_core_parents = stemmed_parent_tokens - {_stem_token(s) for s in stopwords}
            unmatched_parent_tokens = stemmed_core_parents - stemmed_query_tokens
            extra_parent_penalty = len(unmatched_parent_tokens) * 15
            
            # Heavily penalize internal action endpoints unless explicitly requested
            INTERNAL_ACTION_WORDS = {"save", "delete", "remove", "update", "insert", "create", "add", "edit", "json", "ajax", "data", "fetch", "get", "search", "export", "import", "upload", "download", "print", "pdf", "excel", "csv", "entry", "salary", "stage", "action", "process", "submit", "approve", "reject", "convert", "generate", "calculate", "compute", "validate", "check", "byid", "bybrand", "bydate", "byname", "bypass", "detail", "details"}
            internal_action_penalty = 0
            for t in doc_tokens:
                if t in INTERNAL_ACTION_WORDS and t not in query_tokens:
                    internal_action_penalty += 200
            
            # Exact core match bonus: if clean label tokens exactly match clean query tokens
            exact_core_bonus = 50 if (stemmed_core_label and stemmed_core_label == stemmed_core_query) else 0
            
            # Primary List Route Bonus: give strong priority to canonical main list pages (e.g. /quotation/quotationlist, /sales/sales_list)
            r_path_low = r["path"].lower()
            r_lbl_low = r["label"].lower()
            primary_list_bonus = 100 if (r_path_low.endswith("list") or r_lbl_low.endswith("list") or r_path_low.endswith("_list")) else 0

            score = 100 + (label_overlap * 10) + exact_core_bonus + primary_list_bonus - extra_token_penalty - extra_parent_penalty - internal_action_penalty
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
                
                # Fetch vector matches with strict confidence threshold (cosine_distance < 0.28)
                dist_col = NavigationItem.embedding.cosine_distance(query_vector)
                stmt = select(NavigationItem, dist_col).where(
                    NavigationItem.client_id == client_id,
                    NavigationItem.embedding != None,
                    dist_col < 0.28
                ).order_by(dist_col).limit(5)
                
                vec_res = await session.execute(stmt)
                vec_rows = vec_res.all()
                
                if vec_rows:
                    # Convert to the expected ambiguous_list format and clean/deduplicate
                    unique_vec = []
                    seen_paths = set()
                    
                    for item, dist_val in vec_rows:
                        raw_path = (item.path or "").strip()
                        # Reject internal view template files, demos, and backup files
                        if any(bad in raw_path.lower() for bad in ['/views/', '/templates/', '.php', '.blade', '.twig', '/app/views/', '.html', '/bs5/', '/backup/', 'totalsalesjson', '/test/']):
                            continue
                        norm_path = _normalize_route_path(raw_path)
                        canonical_path = re.sub(r'/\d+$', '', norm_path)
                        if not canonical_path.startswith('/'):
                            canonical_path = '/' + canonical_path
                            
                        clean_label = item.label or ""
                        clean_label = re.sub(r'^(?:newlook|varun_sterling|sterling_company)[\s\-:]+', '', clean_label, flags=re.IGNORECASE).strip()
                        if not clean_label:
                            clean_label = item.label
                            
                        module_val = item.module
                        if not module_val or module_val.lower() in {'newlook', 'varun_sterling', 'sterling_company', 'app', 'default'}:
                            url_parts = [p for p in canonical_path.split('/') if p]
                            module_val = url_parts[0].capitalize() if url_parts else None

                        # Discard candidates that share ZERO tokens with query tokens unless distance is ultra-close (< 0.16)
                        lbl_tokens = set(re.findall(r'[a-zA-Z0-9]+', clean_label.lower())) - stopwords
                        path_tokens = set(re.findall(r'[a-zA-Z0-9]+', canonical_path.lower())) - stopwords
                        has_overlap = bool(lbl_tokens.intersection(stemmed_query_tokens) or path_tokens.intersection(stemmed_query_tokens))
                        if not has_overlap and dist_val > 0.16:
                            continue

                        if canonical_path not in seen_paths:
                            # Apply distance penalty to endpoints with internal actions (e.g. save, edit) if not requested
                            HTTP_ACTIONS = {"save", "delete", "remove", "update", "insert", "create", "add", "edit", "json", "ajax", "submit", "approve", "reject", "validate", "byid"}
                            path_lbl_tokens = set(re.findall(r'[a-zA-Z0-9]+', canonical_path.lower())).union(set(re.findall(r'[a-zA-Z0-9]+', clean_label.lower())))
                            if any(t in HTTP_ACTIONS for t in path_lbl_tokens) and not any(t in HTTP_ACTIONS for t in query_tokens):
                                dist_val += 0.15
                                
                            unique_vec.append({
                                "label": clean_label,
                                "path": canonical_path,
                                "module": module_val,
                                "is_custom": not item.is_discovered,
                                "parents": _infer_parents_from_path(canonical_path, module_val),
                                "dist": dist_val
                            })
                            seen_paths.add(canonical_path)
                            
                    # Re-sort unique_vec by the adjusted distance
                    unique_vec.sort(key=lambda x: x["dist"])
                            
                    print(f"🎯 [FastPath Vector Search] Found {len(unique_vec)} unique semantic matches for '{query}'")
                    
                    if len(unique_vec) == 1:
                        return unique_vec[0]["path"], None
                    elif len(unique_vec) > 1:
                        # If top candidate is significantly closer than candidate 2, pick clear winner
                        if unique_vec[0]["dist"] < 0.18 and (unique_vec[1]["dist"] - unique_vec[0]["dist"]) >= 0.04:
                            return unique_vec[0]["path"], None
                        return None, unique_vec
        except Exception as e:
            print(f"⚠️ [FastPath Vector Search] Failed: {e}")

    # Sort by score desc
    scored_candidates.sort(key=lambda x: x[0], reverse=True)
    
    # Filter top tier
    if scored_candidates:
        best_score = scored_candidates[0][0]
        best_matches = [item[1] for item in scored_candidates if item[0] == best_score]
        
        # Prefer custom mappings, then routes with official module, then longer clean path
        best_matches.sort(key=lambda x: (x.get("is_custom", False), bool(x.get("module"))), reverse=True)
        
        unique_best = []
        seen_paths = set()
        for m in best_matches:
            norm_p = _normalize_route_path(m["path"])
            if norm_p not in seen_paths:
                unique_best.append(m)
                seen_paths.add(norm_p)
        
        if len(unique_best) == 1:
            return unique_best[0]["path"], None
        return None, unique_best

    # 4. SUBSTRING/FUZZY FALLBACK
    substring_matches = []
    for r in processed_routes:
        if query.lower() in r["label"].lower():
            substring_matches.append(r)
            
    substring_matches.sort(key=lambda x: (x.get("is_custom", False), bool(x.get("module"))), reverse=True)
    if len(substring_matches) == 1:
        return substring_matches[0]["path"], None
    if len(substring_matches) > 1:
        unique_sub = []
        seen_paths = set()
        for m in substring_matches:
            norm_p = _normalize_route_path(m["path"])
            if norm_p not in seen_paths:
                unique_sub.append(m)
                seen_paths.add(norm_p)
        
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
            for r in sorted(processed_routes, key=lambda x: (x.get("is_custom", False), bool(x.get("module"))), reverse=True):
                if r["label"].lower() == fuzzy_label:
                    norm_p = _normalize_route_path(r["path"])
                    if norm_p not in seen_paths:
                        fuzzy_matches.append(r)
                        seen_paths.add(norm_p)
        
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
            
        # Check if this path + label already exists for this client
        better_label = label.strip() if label and len(label.strip()) >= 4 and not any(c in label for c in ['/', '\\', '.php', '.html']) else None
        if not better_label:
            module = infer_module_from_path(path)
            entity = infer_entity_keyword(path, label)
            better_label = generate_friendly_label(module, entity)

        statement = select(NavigationItem).where(
            NavigationItem.client_id == client_id,
            NavigationItem.path == path,
            NavigationItem.label == better_label
        )
        result = await session.execute(statement)
        existing = result.scalars().first()
        
        # 🧠 INTELLIGENCE ENGINE: Auto-Map Logic
        if not existing or existing.module is None or existing.table_name is None or existing.embedding is None:
            module = infer_module_from_path(path)
            entity = infer_entity_keyword(path, label)
            matched_table = match_entity_to_table(entity, db_tables)
            
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
    """Matches entity keyword against actual DB tables with support for common CRM/ERP suffixes.
    Uses scored matching to prefer the best match over greedy first-match.
    """
    if not db_tables: return None
    
    entity = entity.lower().strip()
    
    # HARDCODED OVERRIDE: Map 'voucher' to 'expence_details'
    if entity in ['voucher', 'payment_voucher', 'payment voucher', 'bank_payment_voucher']:
        if 'expence_details' in db_tables:
            return 'expence_details'
            
    # HARDCODED OVERRIDE: Map 'parts setting' to 'product' table instead of 'product_parts_setting'
    if entity in ['parts setting', 'product parts setting', 'product parts', 'parts_setting', 'partssetting']:
        if 'product' in db_tables:
            return 'product'
            
    # 1. Exact match
    if entity in db_tables:
        return entity
        
    # 2. Suffix matches — comprehensive ERP/CRM suffixes
    for suffix in [
        "_header", "_head", "_detail", "_details", "_det",
        "_master", "_mst", "_tran", "_ms",
        "_items", "_item", "_lines", "_line",
        "_log", "_history", "_hist",
    ]:
        candidate = f"{entity}{suffix}"
        if candidate in db_tables:
            return candidate
    
    # 3. Prefix matches — common DB prefixes
    for prefix in ["mst_", "tbl_", "ref_", "sys_", "trn_"]:
        candidate = f"{prefix}{entity}"
        if candidate in db_tables:
            return candidate
        # Also try prefix + entity + suffix
        for suffix in ["_header", "_head", "_master", "_mst", "_detail"]:
            candidate = f"{prefix}{entity}{suffix}"
            if candidate in db_tables:
                return candidate
    
    # 4. Scored contains match (prefer shortest containing match to avoid false positives)
    containing = []
    for t in db_tables:
        if entity in t:
            # Score: shorter table names are better (more specific match)
            # Also prefer tables where entity is a larger portion of the name
            specificity = len(entity) / max(len(t), 1)
            containing.append((specificity, t))
    
    if containing:
        containing.sort(key=lambda x: x[0], reverse=True)
        return containing[0][1]
        
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
