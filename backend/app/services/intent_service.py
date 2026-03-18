import re
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.models.semantic_metadata import SemanticMetadata
from app.services.onboarding import discover_tables
from app.models.client_config import ClientConfig

# Intent keywords - REORDERED: Update/Delete/Create before Read to avoid collisions with words like "list"
INTENT_MAP = {
    "update": ["update", "change", "edit", "modify", "patch", "set"],
    "delete": ["delete", "remove", "destroy", "drop", "terminate"],
    "create": ["add", "create", "new", "insert", "post", "make"],
    "navigate": ["navigate", "go to", "open", "show me the", "take me to", "goto"],
    "read": ["list", "view", "get", "fetch", "display"]
}

def normalize_entity_name(name: Optional[str]) -> str:
    """Removes common prefixes and singularizes basic plurals."""
    if not name:
        return ""
    name = name.lower().strip()
    # Remove common prefixes
    prefixes = ["mst_", "tbl_", "ref_", "sys_", "api_"]
    for p in prefixes:
        if name.startswith(p):
            name = name[len(p):]
            break
            
    # Simple singularization (basic)
    if name.endswith("ies"):
        name = name[:-3] + "y"
    elif name.endswith("s") and not name.endswith("ss"):
        name = name[:-1]
        
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

        if is_pronoun and detected_url:
             # Pronoun resolved!
             return {
                 "intent": detected_intent,
                 "entity": detected_label or "previous item",
                 "url": detected_url,
                 "label": detected_label,
                 "status": "resolved"
             }

        # Strategy 0: Exact Match Nav Labels
        if not detected_entity:
            for nav in unique_navs:
                if normalize_entity_name(nav.label) == norm_query or normalize_entity_name(nav.module) == norm_query:
                    detected_entity = nav.table_name or nav.label
                    detected_url = nav.path
                    detected_label = nav.label
                    break
        
        # Strategy 1: Fuzzy Match Nav
        if not detected_entity:
            for nav in unique_navs:
                if norm_query in normalize_entity_name(nav.label) or norm_query in nav.path.lower():
                    detected_entity = nav.table_name or nav.label
                    detected_url = nav.path
                    detected_label = nav.label
                    break

        # Strategy 2: Table Names
        if not detected_entity:
             tables = discover_tables(client_config.db_connection_url)
             for t in tables:
                 if normalize_entity_name(t["name"]) == norm_query:
                     detected_entity = t["name"]
                     break
                     
        if detected_entity:
            return {
                "intent": detected_intent,
                "entity": detected_entity,
                "url": detected_url,
                "label": detected_label,
                "status": "resolved"
            }
        
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
