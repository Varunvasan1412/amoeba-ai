import os
import re
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.models.semantic_metadata import SemanticMetadata
from app.models.semantic_mapping import SemanticMapping
from app.services.onboarding import discover_tables
from app.models.client_config import ClientConfig
from app.services.module_resolver import resolve_module_for_table
from app.tools.dates import strip_date_phrases

def simple_title_case(s: str) -> str:
    """Converts 'user-profile' or 'user_profile' to 'User Profile'"""
    if not s:
        return ""
    s = os.path.splitext(s)[0]
    s = s.replace("_", " ").replace("-", " ")
    s = re.sub(r'\[.*?\]', 'Detail', s)
    return s.title().strip()

TAB_DISCRIMINATORS = {
    "pending", "completed", "complete", "active", "inactive", "converted", 
    "open", "closed", "approved", "rejected", "cancelled", "draft", "tax",
    "report", "reports", "history", "log", "logs", "attendance", "summary"
}

# Internal controller actions that should never appear as user-facing tab choices
INTERNAL_ACTION_WORDS = {
    "save", "delete", "remove", "update", "insert", "create", "add", "edit",
    "json", "ajax", "data", "fetch", "get", "search", "export", "import",
    "upload", "download", "print", "pdf", "excel", "csv", "entry",
    "salary", "stage", "action", "process", "submit", "approve", "reject",
    "convert", "generate", "calculate", "compute", "validate", "check",
    "byid", "bybrand", "bydate", "byname", "bypass", "detail", "details"
}

def _is_ui_facing_label(label: str) -> bool:
    """Filter out internal controller action labels from tab disambiguation."""
    if not label:
        return False
    lbl_lower = label.lower().strip()
    lbl_words = set(re.findall(r'[a-zA-Z0-9]+', lbl_lower))
    # Any label containing internal action words is not user-facing
    if lbl_words.intersection(INTERNAL_ACTION_WORDS):
        return False
    return True

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
    # Generic entity placeholders & noise words
    "table", "tables", "record", "records", "data", "row", "rows", "entries", "entry", "item", "items",
    "list", "lists", "page", "pages", "screen", "screens", "view", "views", "menu", "menus", "tab", "tabs"
}

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
    aggregation_patterns = [
        r"\bhow\s+many\b", r"\btotal\b", r"\bcount\b", r"\bnumber\s+of\b", r"\bsum\s+of\b", r"\baverage\b",
        r"\btable(s)?\b", r"\bcolumn(s)?\b", r"\brecord(s)?\b", r"\brow(s)?\b", r"\bdata\b"
    ]
    is_data_query = any(re.search(p, query_lower) for p in aggregation_patterns)
    if is_data_query:
        if not detected_intent or detected_intent == "navigate":
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
            stemmed_q_toks = {_stem_token(t) for t in q_toks}
            
            # --- TAB DISAMBIGUATION CHECK ---
            # If the user asks for a general entity or screen that has multiple tabs/stages
            # (e.g. "grn inspection", "quotations", "invoices", "delivery challan") and did NOT specify a discriminating tab:
            # We do not guess arbitrarily. We ask the user which tab they want to view!
            has_tab_discriminator = any(td in clean_q.split() for td in TAB_DISCRIMINATORS)
            
            if not has_tab_discriminator and sm_all:
                # Group mappings by explicit tab_group
                tab_groups: Dict[str, List[Any]] = {}
                for sm in sm_all:
                    grp = getattr(sm, "tab_group", None)
                    if grp and _is_ui_facing_label(sm.ui_label):
                        tab_groups.setdefault(grp, []).append(sm)
                
                # DEBUG: Log tab groups that contain tokens related to the query
                print(f"🔍 [TAB_DEBUG] clean_q='{clean_q}', stemmed_q_toks={stemmed_q_toks}")
                print(f"🔍 [TAB_DEBUG] Total tab_groups: {len(tab_groups)}, keys (first 10): {list(tab_groups.keys())[:10]}")
                
                matched_group = None
                matched_tabs = []
                for grp, grp_sms in tab_groups.items():
                    grp_lower = grp.lower().strip()
                    grp_core_toks = set(re.findall(r'[a-zA-Z0-9]+', grp_lower)) - NON_ENTITY_WORDS
                    stemmed_grp_toks = {_stem_token(t) for t in grp_core_toks}
                    
                    # Universal Tab Group Match with Stemming (e.g. "invoice" matches group "Invoices")
                    is_group_match = False
                    if grp_lower in clean_q or _stem_token(grp_lower) in clean_q:
                        is_group_match = True
                    elif stemmed_grp_toks and (stemmed_grp_toks.issubset(stemmed_q_toks) or stemmed_q_toks.issubset(stemmed_grp_toks)):
                        is_group_match = True
                    
                    # DEBUG: Log any group that has "invoice" in its tokens
                    if any("invoic" in t for t in stemmed_grp_toks) or any("invoic" in t for t in stemmed_q_toks):
                        print(f"🔍 [TAB_DEBUG] Checking group '{grp}': stemmed_grp_toks={stemmed_grp_toks}, is_match={is_group_match}, members={[s.ui_label for s in grp_sms]}")
                        
                    if is_group_match:
                        # Deduplicate tabs: prefer labels with tab discriminators, collapse aliases
                        views_map = {}
                        for s in grp_sms:
                            view_key = (s.database_table, s.default_filter or "")
                            clean_lbl = s.ui_label.strip()
                            if view_key not in views_map:
                                views_map[view_key] = clean_lbl
                            else:
                                existing = views_map[view_key]
                                # Prefer labels WITH a tab discriminator over generic ones
                                existing_has_disc = any(td in existing.lower() for td in TAB_DISCRIMINATORS)
                                new_has_disc = any(td in clean_lbl.lower() for td in TAB_DISCRIMINATORS)
                                if new_has_disc and not existing_has_disc:
                                    views_map[view_key] = clean_lbl
                                elif "list" in existing.lower() and "list" not in clean_lbl.lower():
                                    views_map[view_key] = clean_lbl

                        unique_tabs = list(views_map.values())
                        # Natural tab order: Pending/Draft first, Completed/Closed second
                        unique_tabs.sort(key=lambda t: 0 if any(k in t.lower() for k in ["pending", "draft", "new", "create"]) else (1 if any(k in t.lower() for k in ["complete", "closed", "approved"]) else 2))
                        
                        print(f"🔍 [TAB_DEBUG] Group '{grp}' matched! views_map keys={list(views_map.keys())}, unique_tabs={unique_tabs}")
                        
                        if len(unique_tabs) >= 2:
                            # CRITICAL: If the query already specifically requests one of these tabs
                            # (e.g. "report" in "list the payroll report", or "history" in "payroll history"),
                            # do NOT trigger tab disambiguation—resolve directly to that tab!
                            is_tab_specified = False
                            for tab_lbl in unique_tabs:
                                tab_tokens = set(re.findall(r'[a-zA-Z0-9]+', tab_lbl.lower().strip())) - NON_ENTITY_WORDS
                                stemmed_tab_tokens = {_stem_token(t) for t in tab_tokens} - stemmed_grp_toks
                                if stemmed_tab_tokens and stemmed_tab_tokens.intersection(stemmed_q_toks):
                                    is_tab_specified = True
                                    print(f"🔍 [TAB_DEBUG] Tab '{tab_lbl}' specified by user query (tokens={stemmed_tab_tokens}, overlap={stemmed_tab_tokens.intersection(stemmed_q_toks)})")
                                    break
                            if not is_tab_specified:
                                matched_group = grp
                                matched_tabs = unique_tabs
                                break
                        else:
                            print(f"🔍 [TAB_DEBUG] Group '{grp}': only {len(unique_tabs)} unique tab(s), need >= 2")
                            
                # Fallback: Auto-detect tab groups if tab_group wasn't explicitly populated
                if not matched_group:
                    print(f"🔍 [TAB_DEBUG] No tab_group match found, trying fallback auto-detection...")
                    
                    # Strategy A: Find labels with discriminator words in them
                    candidate_tabs = []
                    seen_labels = set()
                    for sm in sm_all:
                        if not _is_ui_facing_label(sm.ui_label):
                            continue
                        lbl_clean = sm.ui_label.lower().strip()
                        base_tokens = set(re.findall(r'[a-zA-Z0-9]+', lbl_clean)) - TAB_DISCRIMINATORS - NON_ENTITY_WORDS
                        stemmed_base = {_stem_token(t) for t in base_tokens}
                        if stemmed_base and (stemmed_base.issubset(stemmed_q_toks) or stemmed_q_toks.issubset(stemmed_base)):
                            if any(td in lbl_clean for td in TAB_DISCRIMINATORS):
                                if sm.ui_label.strip() not in seen_labels:
                                    seen_labels.add(sm.ui_label.strip())
                                    candidate_tabs.append(sm.ui_label.strip())
                    
                    # If we found 1 discriminator tab (e.g. "Completed Invoice List"), also look for its base/pending counterpart
                    if len(candidate_tabs) == 1:
                        for sm in sm_all:
                            if not _is_ui_facing_label(sm.ui_label):
                                continue
                            lbl_clean = sm.ui_label.lower().strip()
                            base_tokens = set(re.findall(r'[a-zA-Z0-9]+', lbl_clean)) - NON_ENTITY_WORDS
                            stemmed_base = {_stem_token(t) for t in base_tokens}
                            if stemmed_base and (stemmed_base == stemmed_q_toks):
                                if not any(td in lbl_clean for td in TAB_DISCRIMINATORS):
                                    clean_lbl = sm.ui_label.strip()
                                    if clean_lbl not in seen_labels:
                                        # Prefer "Invoice List" over bare "Invoice"
                                        if "list" in clean_lbl.lower() or not any("list" in c.lower() for c in candidate_tabs):
                                            seen_labels.add(clean_lbl)
                                            candidate_tabs.append(clean_lbl)
                                            break

                    print(f"🔍 [TAB_DEBUG] Fallback Strategy A candidate_tabs: {candidate_tabs}")
                    
                    if len(candidate_tabs) >= 2:
                        filtered_cand = []
                        seen_cand_keys = set()
                        for c in candidate_tabs:
                            c_words = [w for w in c.lower().split() if w in TAB_DISCRIMINATORS]
                            c_key = tuple(sorted(c_words)) if c_words else c.lower()
                            if c_key not in seen_cand_keys:
                                seen_cand_keys.add(c_key)
                                filtered_cand.append(c)
                                
                        is_cand_specified = any(td in stemmed_q_toks for td in TAB_DISCRIMINATORS)
                        if not is_cand_specified and len(filtered_cand) >= 2:
                            filtered_cand.sort(key=lambda t: 1 if any(k in t.lower() for k in ["complete", "closed", "approved"]) else 0)
                            matched_group = simple_title_case(clean_q.replace("show", "").replace("list", "").replace("me", "").replace("the", "").strip()) or "this screen"
                            matched_tabs = filtered_cand
                    
                    # Strategy B: If Strategy A didn't find enough candidates, look for
                    # distinct views of the same entity by grouping by (table, filter)
                    if not matched_group:
                        print(f"🔍 [TAB_DEBUG] Trying fallback Strategy B (distinct view detection)...")
                        entity_views = {}  # key=(table, filter) -> best label
                        for sm in sm_all:
                            if not _is_ui_facing_label(sm.ui_label):
                                continue
                            lbl_clean = sm.ui_label.lower().strip()
                            lbl_tokens = set(re.findall(r'[a-zA-Z0-9]+', lbl_clean)) - NON_ENTITY_WORDS
                            stemmed_lbl = {_stem_token(t) for t in lbl_tokens}
                            # Check if this label is related to the user's query entity
                            if not stemmed_q_toks or not stemmed_lbl:
                                continue
                            if not (stemmed_q_toks.issubset(stemmed_lbl)):
                                continue
                            
                            view_key = (sm.database_table, sm.default_filter or "")
                            clean_lbl = sm.ui_label.strip()
                            if view_key not in entity_views:
                                entity_views[view_key] = clean_lbl
                            else:
                                existing = entity_views[view_key]
                                existing_has_disc = any(td in existing.lower() for td in TAB_DISCRIMINATORS)
                                new_has_disc = any(td in clean_lbl.lower() for td in TAB_DISCRIMINATORS)
                                if new_has_disc and not existing_has_disc:
                                    entity_views[view_key] = clean_lbl
                                elif not existing_has_disc and len(clean_lbl) < len(existing):
                                    entity_views[view_key] = clean_lbl
                        
                        print(f"🔍 [TAB_DEBUG] Strategy B found {len(entity_views)} distinct views: {list(entity_views.values())[:10]}")
                        
                        if len(entity_views) >= 2:
                            # We have multiple distinct views — present them as tab choices
                            distinct_tabs = list(entity_views.values())
                            # Sort: Pending first, Completed second, others last
                            distinct_tabs.sort(key=lambda t: 0 if any(k in t.lower() for k in ["pending", "draft", "new", "list"]) and not any(k in t.lower() for k in ["complete", "closed", "approved"]) else 1)
                            
                            is_cand_specified = any(td in stemmed_q_toks for td in TAB_DISCRIMINATORS)
                            if not is_cand_specified:
                                matched_group = simple_title_case(clean_q.replace("show", "").replace("list", "").replace("me", "").replace("the", "").strip()) or "this screen"
                                matched_tabs = distinct_tabs[:6]  # Cap at 6 choices
                
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
                sm_core_toks = set(re.findall(r'[a-zA-Z0-9]+', sm_label_clean)) - NON_ENTITY_WORDS
                
                # Direct exact or substring match
                if sm_label_norm == norm_query or sm_label_clean == clean_q:
                    score = 40 + len(sm_label_clean)
                elif sm_label_clean in clean_q or clean_q in sm_label_clean:
                    score = 25 + len(sm_label_clean)
                else:
                    overlap = q_toks.intersection(sm_core_toks)
                    score = len(overlap) * 8 if overlap else 0
                
                # Precision Penalty: Penalize extra distinguishing tokens not requested in query
                unmatched_sm_tokens = sm_core_toks - q_toks
                score -= len(unmatched_sm_tokens) * 10
                
                # Tab distinction bonus: if both query and label specify pending or completed, boost score
                if ("pending" in clean_q and "pending" in sm_label_clean) or ("completed" in clean_q and "completed" in sm_label_clean):
                    score += 20
                elif ("pending" in clean_q and "completed" in sm_label_clean) or ("completed" in clean_q and "pending" in sm_label_clean):
                    score -= 30 # Penalize opposite tab
                    
                # Report vs History/Logs/Attendance discriminator
                if "report" in clean_q and "report" in sm_label_clean:
                    score += 25
                elif "report" in clean_q and any(k in sm_label_clean for k in ["history", "log", "attendance", "loglist", "logs"]):
                    score -= 35
                elif any(k in clean_q for k in ["history", "log", "attendance", "logs"]) and any(k in sm_label_clean for k in ["history", "log", "attendance", "logs"]):
                    score += 25
                elif any(k in clean_q for k in ["history", "log", "attendance", "logs"]) and "report" in sm_label_clean:
                    score -= 35

                if score > best_sm_score and score >= 8:
                    best_sm_score = score
                    best_sm = sm
                    
            if best_sm:
                detected_entity = best_sm.database_table
                detected_label = best_sm.ui_label
                detected_module = await resolve_module_for_table(detected_entity, client_id, session)
                print(f"🎯 [INTENT] Codebase Semantic Mapping Match (TOP PRIORITY): '{best_sm.ui_label}' -> {best_sm.database_table} (Score: {best_sm_score})")

        # =========================================================================
        # STRATEGY 0B: Report vs Menu / Data Disambiguation Check
        # When user query contains "report" (e.g. "show me the total sales report"),
        # check if it refers to a screen/menu that has both a data table and a page.
        # Ask user whether they want to view the data table, open the page, or export.
        # IF the user explicitly said "list", "show", "get", "view", etc., do NOT interrupt
        # with disambiguation—proceed directly to retrieve the report table data!
        # =========================================================================
        has_report_kw = bool(re.search(r"\breport(s)?\b", query_lower))
        is_explicit_view = bool(re.search(r"\b(view|table|grid|records|list|show|fetch|get|display|rows|data)\b", query_lower)) or any(clean_q.startswith(v) for v in ["view", "list", "show", "get", "fetch", "display"])
        is_explicit_open = bool(re.search(r"\b(open|go\s+to|navigate|take\s+me)\b", query_lower))
        is_explicit_download = bool(re.search(r"\b(download|export|xlsx|excel|csv)\b", query_lower))

        if has_report_kw and not is_explicit_view and not is_explicit_open and not is_explicit_download:
            target_ui_label = best_sm.ui_label if best_sm else None
            target_table = best_sm.database_table if best_sm else None
            
            # Check navigation items for matching route/page (best scoring match)
            matching_nav = None
            best_nav_score = 0
            for nav in unique_navs:
                nav_clean = nav.label.lower().strip()
                nav_path = nav.path.lower().strip()
                score = 0
                if target_ui_label and target_ui_label.lower() == nav_clean:
                    score = 100
                elif target_ui_label and target_ui_label.lower() in nav_clean:
                    score = 85
                elif nav_clean in clean_q or clean_q in nav_clean:
                    score = 70
                elif all(w in nav_clean for w in q_toks if w not in NON_ENTITY_WORDS):
                    score = 60
                elif "report" in nav_clean and any(w in nav_clean for w in q_toks if w not in NON_ENTITY_WORDS):
                    score = 40
                elif any(w in nav_path for w in q_toks if w not in NON_ENTITY_WORDS):
                    score = 30
                
                if score > best_nav_score and score >= 20:
                    best_nav_score = score
                    matching_nav = nav
                    
            if not target_ui_label and matching_nav:
                target_ui_label = matching_nav.label
                target_table = matching_nav.table_name or (best_sm.database_table if best_sm else None)
                
            if target_ui_label:
                disp_title = target_ui_label
                if "report" not in disp_title.lower():
                    disp_title = f"{disp_title} Report"
                    
                opts = [{"label": f"View {disp_title}"}]
                nav_url = matching_nav.path if matching_nav else None
                if nav_url:
                    opts.append({"label": f"Open {disp_title} Page"})
                opts.append({"label": "Download Report Document"})
                
                print(f"🔀 [INTENT] Report Disambiguation Triggered for '{disp_title}' (URL: {nav_url})")
                return {
                    "intent": "report_disambiguation",
                    "entity": disp_title,
                    "table": target_table,
                    "url": nav_url,
                    "options": opts
                }

        # =========================================================================
        # STRATEGY 0C: Dynamic Sibling Screen Disambiguation
        # When a query asks for a general bare root concept (e.g. "show me the grn", "quotation", "salary")
        # without specifying a qualifying sub-type/stage (like "list", "inspection", "completed", "approval"),
        # and the ERP has multiple distinct screens sharing that root concept:
        # Prompt the user to clarify which screen they want rather than guessing.
        # =========================================================================
        qualifiers = TAB_DISCRIMINATORS | {"list", "report", "create", "view", "edit", "add", "history", "approval", "inspection"}
        has_qualifier = any(q in clean_q.split() for q in qualifiers)
        
        if not detected_entity and len(clean_words) == 1 and not has_qualifier:
            root_term = clean_words[0].lower()
            if len(root_term) >= 3 and root_term not in NON_ENTITY_WORDS:
                sibling_screens = []
                seen_screen_paths = set()
                for nav in unique_navs:
                    nav_clean = nav.label.lower().strip()
                    nav_toks = set(re.findall(r'[a-zA-Z0-9]+', nav_clean)) - NON_ENTITY_WORDS
                    if root_term in nav_toks or root_term in nav_clean:
                        norm_p = nav.path.strip().lower() if nav.path else ""
                        if norm_p not in seen_screen_paths:
                            seen_screen_paths.add(norm_p)
                            sibling_screens.append(nav)
                
                if len(sibling_screens) >= 2:
                    module_name = sibling_screens[0].module or "the menu"
                    disp_root = simple_title_case(root_term)
                    print(f"🔀 [INTENT] Dynamic Screen Disambiguation for '{disp_root}' ({len(sibling_screens)} screens in {module_name})")
                    return {
                        "intent": "screen_disambiguation",
                        "entity": disp_root,
                        "module": module_name,
                        "options": [
                            {
                                "label": s.label,
                                "path": s.path
                            }
                            for s in sibling_screens
                        ]
                    }

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
                t_raw = t["name"]
                t_norm = normalize_entity_name(t_raw)
                t_base = re.sub(r'(_header|_detail|_details|_mst|_master|_lines|_items)$', '', t_norm)
                if t_norm == norm_query or (t_base and t_base == norm_query):
                    detected_entity = t_raw
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
                t_raw = t["name"]
                t_norm = normalize_entity_name(t_raw)
                t_base = re.sub(r'(_header|_detail|_details|_mst|_master|_lines|_items)$', '', t_norm)
                if (t_norm and t_norm in norm_query) or (t_base and len(t_base) >= 3 and re.search(rf"\b{re.escape(t_base)}\b", norm_query)):
                    detected_entity = t_raw
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
