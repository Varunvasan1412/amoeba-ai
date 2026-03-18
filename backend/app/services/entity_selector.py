import re
from typing import List, Dict, Any, Optional
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.navigation import NavigationItem
from app.models.semantic_metadata import SemanticMetadata
from app.services.intent_service import normalize_entity_name

class EntitySelector:
    @staticmethod
    async def resolve_ambiguous_entity(query_entity: str, client_id: int, session: AsyncSession, available_tables: List[str]) -> List[Dict[str, str]]:
        # Clean query
        clean_query = query_entity.lower().replace("_", " ").strip()
        norm_query = normalize_entity_name(clean_query)
        # Tokenize for partial matches (e.g. "sales" and "contact")
        query_tokens = [w for w in norm_query.split() if len(w) > 2]
        
        matches = {} # {table_name: label}

        def is_match(target_str: str) -> bool:
            if not target_str: return False
            norm_target = normalize_entity_name(target_str.lower().replace("_", " "))
            if norm_query in norm_target or norm_target in norm_query:
                return True
            # Check if ALL query tokens are present in the target (Intersection)
            if query_tokens:
                target_words = norm_target.split()
                if all(any(token in tw for tw in target_words) for token in query_tokens):
                    return True
            return False

        # 1. Match Raw Table Names (HIGH PRIORITY for CRUD)
        for table in available_tables:
            if is_match(table):
                matches[table] = EntitySelector.format_table_label(table)
        
        # 2. Match Semantic Metadata (Table Level)
        sem_stmt = select(SemanticMetadata).where(
            SemanticMetadata.client_id == client_id,
            (SemanticMetadata.column_name == None) | (SemanticMetadata.column_name == "")
        )
        sem_result = await session.execute(sem_stmt)
        for sem in sem_result.scalars().all():
            if sem.table_name in matches: continue
            if is_match(sem.label):
                matches[sem.table_name] = sem.label

        # 3. Match Navigation Labels (ONLY if no table matches found)
        if not matches:
            nav_stmt = select(NavigationItem).where(NavigationItem.client_id == client_id)
            nav_result = await session.execute(nav_stmt)
            raw_navs = nav_result.scalars().all()
            
            seen_nav_keys = set()
            for item in raw_navs:
                key = (item.label.strip(), item.path.strip())
                if key in seen_nav_keys: continue
                seen_nav_keys.add(key)
                
                if is_match(item.label):
                    match_key = item.table_name if item.table_name else f"nav_path:{item.path}"
                    if match_key not in matches:
                        matches[match_key] = item.label
        
        return [{"table_name": table, "label": label} for table, label in matches.items()]

    @staticmethod
    def format_table_label(table_name: str) -> str:
        prefixes = ["mst_", "tbl_", "ref_", "sys_", "api_"]
        label = table_name
        for p in prefixes:
            if label.startswith(p):
                label = label[len(p):]
                break
        return label.replace("_", " ").title()
