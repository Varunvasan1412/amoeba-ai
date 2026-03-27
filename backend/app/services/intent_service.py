import re
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.models.semantic_metadata import SemanticMetadata
from app.services.onboarding import discover_tables
from app.models.client_config import ClientConfig
from app.services.module_resolver import resolve_module_for_table

# Intent keywords - REORDERED: Update/Delete/Create before Read to avoid collisions with words like "list"
INTENT_MAP = {
    "update": ["update", "change", "edit", "modify", "patch", "set"],
    "delete": ["delete", "remove", "destroy", "drop", "terminate"],
    "create": ["add", "create", "new", "insert", "post", "make"],
    "navigate": ["navigate", "go to", "open", "show me the", "take me to", "goto"],
    "read": ["list", "view", "get", "fetch", "display"]
}

def normalize_entity_name(name: Optional[str]) -> str:
    """Removes common prefixes/suffixes and singularizes basic plurals."""
    if not name:
        return ""
    name = name.lower().strip()
    
    # 1. Remove common prefixes
    prefixes = ["mst_", "tbl_", "ref_", "sys_", "api_"]
    for p in prefixes:
        if name.startswith(p):
            name = name[len(p):]
            break
            
    # 2. Remove common suffixes (ERP specific) - underscore-separated
    suffixes = ["_header", "_head", "_detail", "_det", "_table", "_master", "_mst"]
    for s in suffixes:
        if name.endswith(s):
            name = name[:-len(s)]
            break

    # 2b. Remove common suffixes (ERP specific) - space-separated (for labels like "Enquiry Header")
    space_suffixes = [" header", " head", " detail", " det", " table", " master", " mst", " list"]
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

async def resolve_crud_intent(query: str, client_id: int, session: AsyncSession, history: list = [], mode: str = "operations") -> Optional[Dict[str, Any]]:
    """
    Detects CRUD intent and resolves entity. 
    Accepts optional history for context-aware pronoun resolution (e.g., "take me there").
    'mode' determines if we treat "how to" as an inquiry (Assistant) or an action (Operations).
    """
    query_lower = query.lower().strip()

    # --- INQUIRY DETECTION ---
    # Patterns that are PURE inquiries (always guide, never act)
    pure_inquiry_patterns = [r"explain", r"meaning\s+of", r"can\s+you\s+tell", r"tell\s+me\s+about", r"what\s+is", r"\?$"]
    # Patterns that are context-dependent (Guide in Assistant, Act in Operations)
    context_inquiry_patterns = [r"how\s+(to|do|can)", r"where\s+is"]
    
    is_pure_inquiry = any(re.search(p, query_lower) for p in pure_inquiry_patterns)
    is_context_inquiry = any(re.search(p, query_lower) for p in context_inquiry_patterns)
    
    # 1. Resolve Intent via Keywords
    detected_intent = None
    for intent, keywords in INTENT_MAP.items():
        for kw in keywords:
            if re.search(rf"\b{kw}\b", query_lower):
                detected_intent = intent
                break
        if detected_intent:
            break
            
    # Priority 1: Pure inquiries always resolve to 'inquiry'
    if is_pure_inquiry:
        return {"intent": "inquiry", "status": "resolved"}
        
    # Priority 2: Assistant mode always resolves context inquiries as 'inquiry'
    if mode == "assistant" and is_context_inquiry:
        return {"intent": "inquiry", "status": "resolved"}
        
    # Priority 3: Operations Mode Action Logic
    # If "where is" is asked in operations, we treat it as a 'navigate' intent
    if mode == "operations" and re.search(r"where\s+is", query_lower):
        detected_intent = "navigate"
    
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
        
        norm_query = normalize_entity_name(entity_query)
        print(f"DEBUG [INTENT] entity_query='{entity_query}' norm_query='{norm_query}' intent='{detected_intent}'")

        # --- PRONOUN RESOLUTION ---
        pronouns = ["there", "it", "that", "this"]
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

        if norm_query in ["it", "this", "that"]:
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

        # STRATEGY -1: Direct Navigation Label Match (HIGHEST PRIORITY)
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

        # STRATEGY -1B: Partial Navigation Match
        # Handles cases like "Create Enquiry" matching "Sales Enquiry"
        if not detected_entity:
            for q in candidate_queries:
                for nav in unique_navs:
                    if not nav.table_name: continue
                    nav_label_norm = normalize_entity_name(nav.label)
                    # Use a robust partial match (exact word overlap preferred, or containment)
                    if q in nav_label_norm or nav_label_norm in q:
                        detected_entity = nav.table_name
                        detected_url = nav.path
                        detected_label = nav.label
                        detected_module = nav.module
                        print(f"🎯 [INTENT] Partial Nav Match: '{nav.label}' -> {detected_entity} (Module: {detected_module})")
                        break
                if detected_entity: break

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
             tables = discover_tables(client_config.db_connection_url)
             for t in tables:
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
                if norm_query in normalize_entity_name(nav.label) or norm_query in nav.path.lower():
                    if detected_intent != "navigate" and not nav.table_name:
                        continue
                    detected_entity = nav.table_name or nav.label
                    detected_url = nav.path
                    detected_label = nav.label
                    detected_module = nav.module or await resolve_module_for_table(detected_entity, client_id, session)
                    break

        # Strategy 4: Fallback to Raw Tables (Partial)
        if not detected_entity:
             tables = discover_tables(client_config.db_connection_url)
             for t in tables:
                 if norm_query in normalize_entity_name(t["name"]):
                     detected_entity = t["name"]
                     detected_module = await resolve_module_for_table(detected_entity, client_id, session)
                     break
                     
        # Strategy 5: Fuzzy Matching (Typo Tolerance)
        if not detected_entity and len(norm_query) >= 3:
            import difflib
            best_ratio = 0.0
            best_table = None
            
            # Check Semantic Metadata first
            sem_result = await session.execute(sem_stmt)
            for sem in sem_result.scalars().all():
                sem_norm = normalize_entity_name(sem.label.lower().strip()) if sem.label else ""
                if sem_norm:
                    ratio = difflib.SequenceMatcher(None, norm_query, sem_norm).ratio()
                    if ratio > best_ratio:
                        best_ratio = ratio
                        best_table = sem.table_name
            
            # Check Raw Tables
            tables = discover_tables(client_config.db_connection_url)
            for t in tables:
                t_norm = normalize_entity_name(t["name"])
                ratio = difflib.SequenceMatcher(None, norm_query, t_norm).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_table = t["name"]
                    
            if best_ratio > 0.75: # 75% similarity threshold for typos
                detected_entity = best_table
                detected_module = await resolve_module_for_table(detected_entity, client_id, session)
                print(f"🎯 [INTENT] Fuzzy match found: '{norm_query}' -> {best_table} (ratio: {best_ratio:.2f})")
                     
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
