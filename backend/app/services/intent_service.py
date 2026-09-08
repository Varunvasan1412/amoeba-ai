import re
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.models.semantic_metadata import SemanticMetadata
from app.services.onboarding import discover_tables
from app.models.client_config import ClientConfig
from app.services.module_resolver import resolve_module_for_table
from app.tools.dates import strip_date_phrases

# Intent keywords - REORDERED: Update/Delete/Create before Read to avoid collisions with words like "list"
INTENT_MAP = {
    "update": ["update", "change", "edit", "modify", "patch", "set"],
    "delete": ["delete", "remove", "destroy", "drop", "terminate"],
    "create": ["add", "create", "new", "insert", "post", "make"],
    "navigate": ["navigate", "go to", "open", "take me to", "goto"],
    "read": ["list", "view", "get", "fetch", "display", "show", "search"]
}

NON_ENTITY_WORDS = {
    # Conversational fillers & request framing
    "no", "yes", "i", "just", "want", "need", "give", "can", "you", "please", "would", 
    "like", "to", "see", "know", "tell", "me", "the", "a", "an", "of", "in", "for", 
    "at", "from", "on", "by", "with", "about", "what", "which", "is", "are", "was", "were",
    "hey", "hi", "hello", "now", "so", "then", "also", "only", "there", "here",
    # SQL aggregations & metrics (NEVER match these to table names like master_country!)
    "total", "count", "sum", "average", "avg", "min", "max", "number", "qty", "quantity", 
    "amount", "value", "rate", "cost", "price", "figure", "figures", "how", "many", "much",
    # Generic entity placeholders
    "table", "tables", "record", "records", "data", "row", "rows", "entries", "entry", "item", "items"
}

def normalize_entity_name(name: Optional[str]) -> str:
    """Removes common prefixes/suffixes and singularizes basic plurals."""
    if not name:
        return ""
    name = name.lower().strip()
    
    # 1. Remove common prefixes (Schema + Module prefixes)
    prefixes = [
        "mst_", "tbl_", "ref_", "sys_", "api_", 
        "marketing_", "sales_", "purchase_", "inventory_", "accounting_", 
        "account_", "hr_", "payroll_", "production_", "mrp_", "crm_", 
        "support_", "admin_", "stock_", "logistics_"
    ]
    for p in prefixes:
        if name.startswith(p):
            name = name[len(p):]
            break
            
    # 2. Remove common suffixes (ERP specific) - underscore-separated
    suffixes = ["_header", "_head", "_details", "_detail", "_det", "_table", "_master", "_mst"]
    for s in suffixes:
        if name.endswith(s):
            name = name[:-len(s)]
            break

    # 2b. Remove common suffixes (ERP specific) - space-separated (for labels like "Enquiry Header")
    space_suffixes = [" header", " head", " details", " detail", " det", " table", " master", " mst", " list"]
    for s in space_suffixes:
        if name.endswith(s):
            name = name[:-len(s)]
            break

    # 3. Simple singularization (basic)
    if name.endswith("ies"):
        name = name[:-3] + "y"
    elif name.endswith("s") and not name.endswith("ss"):
        name = name[:-1]

    # 4. Common Business Term Normalization (ERP context)
    # We do this AFTER singularization so "inquiries" -> "inquiry" -> "enquiry"
    # and "soles" -> "sole" -> "sale"
    name = name.replace("inquiry", "enquiry")
    name = name.replace("sole", "sale")
    name = name.replace("ledger", "report")
        
    return name

async def resolve_crud_intent(query: str, client_id: int, session: AsyncSession, history: list = None, mode: str = "assistant") -> dict:
    """
    Analyzes user intent and resolves the target entity (database table) if applicable.
    Returns: {"intent": "read|create|update|delete|inquiry|navigate|unknown", "entity": "table_name_or_none", "url": "path_or_none"}
    Accepts optional history for context-aware pronoun resolution (e.g., "take me there").
    'mode' determines if we treat "how to" as an inquiry (Assistant) or an action (Operations).
    """
    query_lower = query.lower().strip()

    # --- CONTEXT-AWARE DISAMBIGUATION GUARD ---
    # If the AI just asked a disambiguation question, do not intercept as CRUD
    if history:
        last_ai_msg = [m for m in history if (m.get("role") if isinstance(m, dict) else getattr(m, "role", "user")) in ["ai", "assistant"]]
        if last_ai_msg:
            last_ai_content = last_ai_msg[-1].get("content", "") if isinstance(last_ai_msg[-1], dict) else getattr(last_ai_msg[-1], "content", "")
            if "Which" in last_ai_content and "would you like" in last_ai_content:
                if "tab" not in last_ai_content.lower() and any(kw in last_ai_content.lower() for kw in ["page", "route", "destination", "link"]):
                    print("🛡️ [INTENT] User is answering a navigation disambiguation prompt. Forcing navigation intent.")
                    return {"intent": "navigate", "url": None, "entity": None}

    # --- INQUIRY DETECTION ---
    # Patterns that are PURE inquiries (always guide, never act)
    pure_inquiry_patterns = [r"explain", r"meaning\s+of", r"can\s+you\s+tell", r"tell\s+me\s+about", r"what\s+is", r"\?$"]
    # Patterns that are context-dependent (Guide in Assistant, Act in Operations)
    context_inquiry_patterns = [r"how\s+(to|do|can)", r"where\s+is"]
    
    is_pure_inquiry = any(re.search(p, query_lower) for p in pure_inquiry_patterns)
    is_context_inquiry = any(re.search(p, query_lower) for p in context_inquiry_patterns)
    
    # 1. Resolve Intent via Keywords FIRST (before inquiry check)
    detected_intent = None
    for intent, keywords in INTENT_MAP.items():
        for kw in keywords:
            if re.search(rf"\b{kw}\b", query_lower):
                detected_intent = intent
                break
        if detected_intent:
            break
    
    # Also detect aggregation-style data queries as implicit "read"
    aggregation_patterns = [r"\bhow\s+many\b", r"\btotal\b", r"\bcount\b", r"\bnumber\s+of\b", r"\bsum\s+of\b", r"\baverage\b"]
    is_data_query = any(re.search(p, query_lower) for p in aggregation_patterns)
    if is_data_query and not detected_intent:
        detected_intent = "read"
    
    # Priority 1: Pure inquiries — BUT only if no CRUD/data intent was detected
    if is_pure_inquiry and not detected_intent:
        return {"intent": "inquiry", "status": "resolved"}
        
    # Priority 2: Assistant mode always resolves context inquiries as 'inquiry'
    if mode == "assistant" and is_context_inquiry:
        return {"intent": "inquiry", "status": "resolved"}
        
    # Priority 3: Operations Mode Action Logic
    # If "where is" is asked in operations and bypassed FastPath, it means they are looking for a record, not a page.
    if mode == "operations" and re.search(r"where\s+is", query_lower):
        detected_intent = "read"
    
    if not detected_intent:
        # If still no intent but it was a context inquiry, last resort is inquiry
        if is_context_inquiry:
            return {"intent": "inquiry", "status": "resolved"}
        return None 

    # 3. Resolve Entity
    client_config = await session.get(ClientConfig, client_id)
    if not client_config:
        return {"intent": detected_intent, "entity": None, "status": "error_no_client"}
        
    try:
        # Pre-fetch tables ONCE (cached via TTL in discover_tables)
        all_tables = discover_tables(client_config.db_connection_url)
        # Get semantic metadata and navigation items
        from app.models.navigation import NavigationItem
        nav_stmt = select(NavigationItem).where(NavigationItem.client_id == client_id)
        nav_res = await session.execute(nav_stmt)
        all_navs = nav_res.scalars().all()
        
        # De-duplicate navs
        seen_nav_keys = set()
        unique_navs = []
        for n in all_navs:
            key = (n.label.strip(), n.path.strip())
            if key not in seen_nav_keys:
                seen_nav_keys.add(key)
                unique_navs.append(n)

        # Normalize the query for entity search
        entity_query = query_lower
        for kw in INTENT_MAP[detected_intent]:
            entity_query = re.sub(rf"\b{kw}\b", "", entity_query).strip()
        
        # --- STRIP DATE PHRASES ---
        entity_query = strip_date_phrases(entity_query)
        
        norm_query = normalize_entity_name(entity_query)
        print(f"DEBUG [INTENT] entity_query='{entity_query}' norm_query='{norm_query}' intent='{detected_intent}'")

        # --- PRONOUN RESOLUTION ---
        pronouns = ["there", "it", "that", "this", "item", "items", "record", "records", "them", "these", "one", "ones"]
        is_pronoun = any(re.search(rf"\b{p}\b", norm_query) for p in pronouns)
        
        last_mentioned_url = None
        last_mentioned_label = None
        
        if is_pronoun and history:
            # Look back through history for the last AI-mentioned URL or navigation label
            # We skip the very last message if it's the current user message (optional, role check handles it)
            for msg in reversed(history):
                content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
                role = msg.get("role", "") if isinstance(msg, dict) else getattr(msg, "role", "user")
                
                if role == "ai" or role == "assistant":
                    # 1. Check for explicit paths/URLs in AI response
                    path_match = re.search(r"(/[\w/-]+)", content)
                    if path_match:
                        last_mentioned_url = path_match.group(1).strip()
                        # If the AI mentioned a label nearby, try to catch it
                        break
                    # 2. Check for navigation labels mentioned by AI
                    for nav in unique_navs:
                        if nav.label.lower() in content.lower():
                            last_mentioned_url = nav.path
                            last_mentioned_label = nav.label
                            break
                    if last_mentioned_url:
                        break

        # 4. Entity Strategy Selection
        detected_entity = None
        detected_url = last_mentioned_url
        detected_label = last_mentioned_label
        detected_module = None

        # Check if the query is essentially just a pronoun reference (e.g., "that", "that table", "me that")
        noise_for_pronoun = {"me", "the", "a", "an", "table", "record", "item", "one", "ones", "details", "list", "show", "get", "fetch", "view"}
        words_in_query = norm_query.split()
        clean_words = [w for w in words_in_query if w not in noise_for_pronoun and w not in pronouns]
        has_pronoun = any(p in words_in_query for p in pronouns)
        
        if has_pronoun and not clean_words:
             print("🎯 [INTENT] Pure pronoun query detected -> forcing context resolution")
             return {
                 "intent": detected_intent,
                 "entity": None,
                 "use_context": True,
                 "status": "resolved"
             }

        # --- IMPROVED QUERY CLEANING (Handle Module + Entity) ---
        words = norm_query.split()
        reduced_query = " ".join(words[1:]) if len(words) > 1 else norm_query
        candidate_queries = [norm_query]
        if reduced_query != norm_query:
            candidate_queries.append(reduced_query)

        # Add clean query without fillers and SQL aggregation keywords (e.g. "total sales count" -> "sales")
        clean_words = [w for w in words if w not in NON_ENTITY_WORDS]
        if clean_words:
            clean_query = " ".join(clean_words)
            if clean_query not in candidate_queries:
                candidate_queries.insert(0, clean_query) # Prioritize clean query!

        # =========================================================================
        # STRATEGY 0A: Codebase Semantic Mapping Match (HIGHEST PRIORITY)
        # Ground truth extracted directly from actual PHP/MVC controllers, views, tabs, and database queries.
        # =========================================================================
        if not detected_entity:
            from app.models.semantic_mapping import SemanticMapping
            sm_stmt = select(SemanticMapping).where(SemanticMapping.client_id == client_id)
            sm_res = await session.execute(sm_stmt)
            sm_all = sm_res.scalars().all()
            
            clean_q = norm_query.replace("_", " ").lower()
            q_toks = set(re.findall(r'[a-zA-Z0-9]+', clean_q)) - NON_ENTITY_WORDS
            
            # --- TAB DISAMBIGUATION CHECK ---
            # If the user asks for a general entity or screen that has multiple tabs/stages
            # (e.g. "grn inspection", "quotations", "invoices") and did NOT specify a discriminating tab:
            # We do not guess arbitrarily. We ask the user which tab they want to view!
            TAB_DISCRIMINATORS = {
                "pending", "completed", "complete", "active", "inactive", "converted", 
                "open", "closed", "approved", "rejected", "cancelled", "draft", "tax"
            }
            has_tab_discriminator = any(td in clean_q.split() for td in TAB_DISCRIMINATORS)
            
            if not has_tab_discriminator and sm_all:
                # Group mappings by explicit tab_group
                tab_groups: Dict[str, List[SemanticMapping]] = {}
                for sm in sm_all:
                    grp = getattr(sm, "tab_group", None)
                    if grp:
                        tab_groups.setdefault(grp, []).append(sm)
                
                matched_group = None
                matched_tabs = []
                for grp, grp_sms in tab_groups.items():
                    grp_lower = grp.lower()
                    grp_toks = set(re.findall(r'[a-zA-Z0-9]+', grp_lower))
                    if grp_lower in clean_q or clean_q in grp_lower or len(q_toks.intersection(grp_toks)) >= 2:
                        # Deduplicate tabs by distinct view/table/filter to avoid showing aliases
                        views_map = {}
                        for s in grp_sms:
                            view_key = (s.database_table, s.default_filter or "")
                            clean_lbl = s.ui_label.strip()
                            if view_key not in views_map:
                                views_map[view_key] = clean_lbl
                            else:
                                existing = views_map[view_key]
                                if "list" in existing.lower() and "list" not in clean_lbl.lower():
                                    views_map[view_key] = clean_lbl

                        unique_tabs = list(views_map.values())
                        # Natural tab order: Pending/Draft first, Completed/Closed second
                        unique_tabs.sort(key=lambda t: 0 if any(k in t.lower() for k in ["pending", "draft", "new", "create"]) else (1 if any(k in t.lower() for k in ["complete", "closed", "approved"]) else 2))
                        if len(unique_tabs) >= 2:
                            matched_group = grp
                            matched_tabs = unique_tabs
                            break
                            
                # Fallback: Auto-detect tab groups if tab_group wasn't explicitly populated
                if not matched_group:
                    candidate_tabs = []
                    seen_labels = set()
                    for sm in sm_all:
                        lbl_clean = sm.ui_label.lower().strip()
                        toks = set(re.findall(r'[a-zA-Z0-9]+', lbl_clean)) - {"list", "view", "details"}
                        if q_toks.intersection(toks):
                            if any(td in lbl_clean for td in TAB_DISCRIMINATORS):
                                if sm.ui_label.strip() not in seen_labels:
                                    seen_labels.add(sm.ui_label.strip())
                                    candidate_tabs.append(sm.ui_label.strip())
                    
                    if len(candidate_tabs) >= 2:
                        matched_group = simple_title_case(clean_q.replace("show", "").replace("list", "").replace("me", "").replace("the", "").strip()) or "this screen"
                        matched_tabs = candidate_tabs
                
                if matched_group and matched_tabs:
                    print(f"🔀 [INTENT] Tab Disambiguation Triggered for group '{matched_group}' with tabs: {matched_tabs}")
                    return {
                        "intent": "tab_disambiguation",
                        "screen": matched_group,
                        "tabs": [
                            {
                                "label": tab_label # Clean UI displayed name, NEVER table name!
                            }
                            for tab_label in matched_tabs
                        ],
                        "entity": None,
                        "url": None
                    }

            best_sm = None
            best_sm_score = 0
            for sm in sm_all:
                sm_label_norm = normalize_entity_name(sm.ui_label.lower().strip())
                sm_label_clean = sm.ui_label.lower().strip()
                
                # Direct exact or substring match
                if sm_label_norm == norm_query or sm_label_clean == clean_q:
                    score = 40 + len(sm_label_clean)
                elif sm_label_clean in clean_q or clean_q in sm_label_clean:
                    score = 25 + len(sm_label_clean)
                else:
                    sm_toks = set(re.findall(r'[a-zA-Z0-9]+', sm_label_clean)) - {"list", "view", "details"}
                    overlap = q_toks.intersection(sm_toks)
                    score = len(overlap) * 8 if overlap else 0
                
                # Tab distinction bonus: if both query and label specify pending or completed, boost score
                if ("pending" in clean_q and "pending" in sm_label_clean) or ("completed" in clean_q and "completed" in sm_label_clean):
                    score += 20
                elif ("pending" in clean_q and "completed" in sm_label_clean) or ("completed" in clean_q and "pending" in sm_label_clean):
                    score -= 30 # Penalize opposite tab
                    
                if score > best_sm_score and score >= 8:
                    best_sm_score = score
                    best_sm = sm
                    
            if best_sm:
                detected_entity = best_sm.database_table
                detected_label = best_sm.ui_label
                detected_module = await resolve_module_for_table(detected_entity, client_id, session)
                print(f"🎯 [INTENT] Codebase Semantic Mapping Match (TOP PRIORITY): '{best_sm.ui_label}' -> {best_sm.database_table} (Score: {best_sm_score})")

        # STRATEGY -1: Direct Navigation Label Match
        # This allows "Create Sales Enquiry" to match NavigationItem.label exactly
        if not detected_entity:
            for q in candidate_queries:
                for nav in unique_navs:
                    if not nav.table_name: continue
                    nav_label_norm = normalize_entity_name(nav.label)
                    if q == nav_label_norm:
                        detected_entity = nav.table_name
                        detected_url = nav.path
                        detected_label = nav.label
                        detected_module = nav.module
                        print(f"🎯 [INTENT] Direct Nav Label Match: '{nav.label}' -> {detected_entity} (Module: {detected_module})")
                        break
                if detected_entity: break

        # STRATEGY -1B: Partial Navigation Match (Word Overlap)
        # Handles cases like "Show Enquiry" matching "Marketing Enquiry"
        # Also handles compound labels like "Followuplist" matching "followup"
        if not detected_entity:
            noise_words = {
                "detail", "details", "list", "head", "header", "master", "table", "form", 
                "create", "view", "mst", "show", "get", "fetch", "all", "of", "in", "on", 
                "at", "which", "that", "are", "were", "was", "is", "created", "made", "done"
            }
            best_nav_match = None
            best_nav_score = 0
            
            for q in candidate_queries:
                q_words = set(q.replace("_", " ").split()) - noise_words
                if not q_words:
                    continue
                    
                for nav in unique_navs:
                    if not nav.table_name: continue
                    nav_label_norm = normalize_entity_name(nav.label)
                    nav_words = set(nav_label_norm.replace("_", " ").split()) - noise_words
                    
                    # Count matches: exact word match OR prefix/substring match
                    matched = 0
                    for qw in q_words:
                        for nw in nav_words:
                            if qw == nw or nw.startswith(qw) or qw.startswith(nw):
                                matched += 1
                                break
                    
                    if matched == 0:
                        continue
                    
                    # Score: fraction of Navigation Label words matched (not query length)
                    score = matched / len(nav_words) if len(nav_words) > 0 else 0
                    
                    # Must match at least one meaningful word, and score must be >= 50%
                    if score > best_nav_score and score >= 0.5:
                        best_nav_score = score
                        best_nav_match = nav
                        
            if best_nav_match:
                detected_entity = best_nav_match.table_name
                detected_url = best_nav_match.path
                detected_label = best_nav_match.label
                detected_module = best_nav_match.module
                print(f"🎯 [INTENT] Word-Overlap Nav Match: '{best_nav_match.label}' -> {detected_entity} (Score: {best_nav_score:.2f}, Module: {detected_module})")
            else:
                print(f"❌ [INTENT] Strategy -1B (word overlap) failed for candidates: {candidate_queries}")

        # Strategy 0: Semantic Metadata Match
        if not detected_entity:
            print(f"DEBUG [INTENT] Starting Strategy 0 (Semantic Metadata)")
            sem_stmt = select(SemanticMetadata).where(
                SemanticMetadata.client_id == client_id,
                (SemanticMetadata.column_name == None) | (SemanticMetadata.column_name == "")
            )
            sem_result = await session.execute(sem_stmt)
            sem_all = sem_result.scalars().all()
            print(f"DEBUG [INTENT] Strategy 0: Found {len(sem_all)} semantic entries")
            for sem in sem_all:
                sem_norm = normalize_entity_name(sem.label.lower().strip()) if sem.label else ""
                print(f"DEBUG [INTENT] Strategy 0: label='{sem.label}' sem_norm='{sem_norm}' table='{sem.table_name}' match={sem_norm == norm_query}")
                if sem_norm == norm_query:
                    detected_entity = sem.table_name
                    detected_module = await resolve_module_for_table(detected_entity, client_id, session)
                    print(f"🎯 [INTENT] Semantic label exact match: '{sem.label}' -> {sem.table_name} (Module: {detected_module})")
                    break
                if sem.synonyms:
                    for syn in sem.synonyms:
                        if normalize_entity_name(syn.lower().strip()) == norm_query:
                            detected_entity = sem.table_name
                            detected_module = await resolve_module_for_table(detected_entity, client_id, session)
                            print(f"🎯 [INTENT] Semantic synonym match: '{syn}' -> {sem.table_name} (Module: {detected_module})")
                            break
                    if detected_entity:
                        break

        # Strategy 1: Table Names
        if not detected_entity:
             for t in all_tables:
                 if normalize_entity_name(t["name"]) == norm_query:
                     detected_entity = t["name"]
                     detected_module = await resolve_module_for_table(detected_entity, client_id, session)
                     break

        # Strategy 2: Legacy Match Nav (Table-bound)
        if not detected_entity:
            for nav in unique_navs:
                if normalize_entity_name(nav.label) == norm_query or normalize_entity_name(nav.module) == norm_query:
                    # IMPORTANT: If it's a CRUD intent (not navigate), and nav has no table, skip exact match
                    # unless it's the ONLY thing we found. But here we want to fallback to fuzzy if no table.
                    if detected_intent != "navigate" and not nav.table_name:
                        continue
                    detected_entity = nav.table_name or nav.label
                    detected_url = nav.path
                    detected_label = nav.label
                    detected_module = nav.module or await resolve_module_for_table(detected_entity, client_id, session)
                    break
        
        # Strategy 3: Substring Nav
        if not detected_entity:
            for nav in unique_navs:
                nav_norm = normalize_entity_name(nav.label)
                if nav_norm in norm_query or nav.path.lower() in norm_query:
                    if detected_intent != "navigate" and not nav.table_name:
                        continue
                    detected_entity = nav.table_name or nav.label
                    detected_url = nav.path
                    detected_label = nav.label
                    detected_module = nav.module or await resolve_module_for_table(detected_entity, client_id, session)
                    break

        # Strategy 4: Fallback to Raw Tables (Partial)
        if not detected_entity:
             for t in all_tables:
                 t_norm = normalize_entity_name(t["name"])
                 if t_norm and t_norm in norm_query:
                     detected_entity = t["name"]
                     detected_module = await resolve_module_for_table(detected_entity, client_id, session)
                     break
                     
        # Strategy 5: Fuzzy Matching (Typo Tolerance / Phrase search inside query)
        if not detected_entity and len(norm_query) >= 3:
            import difflib
            best_ratio = 0.0
            best_table = None
            
            # Since the user query might be a full sentence (e.g. "show me stock where > 10"),
            # standard difflib over the whole sentence fails. We will check if the table name 
            # closely matches any sub-phrase of the query.

            query_words = norm_query.split()
            
            # Check Semantic Metadata first
            sem_result = await session.execute(sem_stmt)
            for sem in sem_result.scalars().all():
                sem_norm = normalize_entity_name(sem.label.lower().strip()) if sem.label else ""
                if sem_norm:
                    sem_words = sem_norm.split()
                    sz = len(sem_words)
                    for i in range(len(query_words) - sz + 1):
                        sub_phrase = " ".join(query_words[i:i+sz])
                        if sub_phrase in NON_ENTITY_WORDS or len(sub_phrase) < 4:
                            continue
                        ratio = difflib.SequenceMatcher(None, sub_phrase, sem_norm).ratio()
                        min_ratio = 0.88 if len(sub_phrase) < 6 else 0.80
                        if ratio > best_ratio and ratio >= min_ratio:
                            best_ratio = ratio
                            best_table = sem.table_name
            
            # Check Raw Tables
            for t in all_tables:
                t_norm = normalize_entity_name(t["name"])
                if t_norm:
                    t_words = t_norm.split()
                    sz = len(t_words)
                    # Create moving window of same length
                    for i in range(len(query_words) - sz + 1):
                        sub_phrase = " ".join(query_words[i:i+sz])
                        if sub_phrase in NON_ENTITY_WORDS or len(sub_phrase) < 4:
                            continue
                        ratio = difflib.SequenceMatcher(None, sub_phrase, t_norm).ratio()
                        min_ratio = 0.88 if len(sub_phrase) < 6 else 0.80
                        if ratio > best_ratio and ratio >= min_ratio:
                            best_ratio = ratio
                            best_table = t["name"]
                    
            if best_ratio >= 0.80 and best_table:
                detected_entity = best_table
                detected_module = await resolve_module_for_table(detected_entity, client_id, session)
                print(f"🎯 [INTENT] Fuzzy subphrase match found: '{norm_query}' -> {best_table} (ratio: {best_ratio:.2f})")
                     
        if detected_entity:
            print(f"MODULE_RESOLVED: {detected_module} for {detected_entity}")
            return {
                "intent": detected_intent,
                "entity": detected_entity,
                "url": detected_url,
                "label": detected_label,
                "module": detected_module,
                "status": "resolved"
            }
        
        print(f"DEBUG [INTENT] UNRESOLVED: entity_query='{entity_query}' norm_query='{norm_query}'")
        return {
            "intent": detected_intent,
            "entity": entity_query,
            "status": "unresolved_entity"
        }
            
    except Exception as e:
        print(f"⚠️ CRUD Intent Resolution Error: {e}")
        import traceback
        traceback.print_exc()
        return {"intent": detected_intent, "entity": None, "status": "error"}
