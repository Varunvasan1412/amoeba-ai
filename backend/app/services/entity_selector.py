import re
import difflib
from typing import List, Dict, Any, Optional
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.navigation import NavigationItem
from app.models.semantic_metadata import SemanticMetadata
from app.services.intent_service import normalize_entity_name

class EntitySelector:
    @staticmethod
    async def resolve_ambiguous_entity(query_entity: str, client_id: int, session: AsyncSession, available_tables: List[str], intent: Optional[str] = None) -> List[Dict[str, str]]:
        # 1. Normalization
        clean_query = query_entity.lower().strip()
        norm_query = normalize_entity_name(clean_query)
        
        matches = []
        is_crud = intent in ["create", "update", "delete"]

        # Fetch navigation for module mapping
        nav_stmt = select(NavigationItem).where(NavigationItem.client_id == client_id)   
        nav_result = await session.execute(nav_stmt)
        nav_items = nav_result.scalars().all()

        table_module_map = {
            item.table_name: item.module
            for item in nav_items if item.table_name
        }
        
        def get_match_score(query: str, target: str) -> int:
            """
            Score 100: Exact match
            Score 50: Partial match (substring)
            Score 20-40: Fuzzy match (difflib)
            Score 0: No match
            """
            if not target: return 0
            q = query.lower().strip()
            # Normalize target similarly for comparison
            t = normalize_entity_name(target.lower().strip())
            
            if q == t: return 100
            if q and t and (q in t or t in q): return 50
            
            # Fuzzy fallback (Step 6 Improvement)
            if len(q) > 3 and len(t) > 3:
                ratio = difflib.SequenceMatcher(None, q, t).ratio()
                if ratio > 0.7:
                    return int(ratio * 40) # Scale to max 40
            
            return 0
            
    @staticmethod
    async def debug_entity_routing(query_entity: str, client_id: int, session: AsyncSession, available_tables: List[str]) -> List[Dict[str, Any]]:
        matches = []
        clean_query = query_entity.lower().strip()
        norm_query = normalize_entity_name(clean_query)
        
        nav_stmt = select(NavigationItem).where(NavigationItem.client_id == client_id)   
        nav_result = await session.execute(nav_stmt)
        nav_items = nav_result.scalars().all()
        table_module_map = {item.table_name: item.module for item in nav_items if item.table_name}
        
        # 1. Match Semantic Metadata
        sem_stmt = select(SemanticMetadata).where(
            SemanticMetadata.client_id == client_id,
            (SemanticMetadata.column_name == None) | (SemanticMetadata.column_name == "")
        )
        sem_result = await session.execute(sem_stmt)
        for sem in sem_result.scalars().all():
            score = EntitySelector._get_match_score(norm_query, sem.label)
            if score > 0:
                matches.append({"table_name": sem.table_name, "label": sem.label, "module": table_module_map.get(sem.table_name), "priority": 1 if score == 100 else 3, "score": score, "entry_id": sem.id, "is_synonym": False, "match_type": "Label", "matched_term": sem.label})
            
            if sem.synonyms:
                for syn in sem.synonyms:
                    score = EntitySelector._get_match_score(norm_query, syn)
                    if score > 0:
                        matches.append({"table_name": sem.table_name, "label": sem.label, "module": table_module_map.get(sem.table_name), "priority": 2 if score == 100 else 3, "score": score, "entry_id": sem.id, "is_synonym": True, "match_type": "Synonym", "matched_term": syn})
                        
        # 2. Match Raw Tables
        for table in available_tables:
            if any(m["table_name"] == table for m in matches): continue
            score = EntitySelector._get_match_score(norm_query, table)
            if score > 0:
                matches.append({"table_name": table, "label": EntitySelector.format_table_label(table), "priority": 4, "score": score, "match_type": "Table Name", "matched_term": table})
                
        # Sort and return all
        matches.sort(key=lambda x: (x["priority"], -x["score"]))
        return matches

    @staticmethod
    def _get_match_score(query: str, target: str) -> float:
        if not target: return 0.0
        q = query.lower().strip()
        t = normalize_entity_name(target.lower().strip())
        t_raw = target.lower().strip()
        if not q or not t: return 0.0
        
        if q == t or q == t_raw: return 1.0
        if t.startswith(q) or q.startswith(t) or t_raw.startswith(q) or q.startswith(t_raw): return 0.95
        if t in q or t_raw in q: return 0.90
        if q in t or q in t_raw: return 0.85

        # Check token-level containment
        q_tokens = set(re.findall(r'[a-zA-Z0-9]+', q))
        q_norm_tokens = {normalize_entity_name(tok) for tok in q_tokens}
        if t in q_tokens or t in q_norm_tokens or t_raw in q_tokens or t_raw in q_norm_tokens:
            return 0.90
        
        if len(q) > 3 and len(t) > 3:
            ratio = difflib.SequenceMatcher(None, q, t).ratio()
            if ratio > 0.7: return ratio
            
        return 0.0

    @staticmethod
    async def resolve_ambiguous_entity(
        query_entity: str, 
        client_id: int, 
        session: AsyncSession, 
        available_tables: List[str], 
        intent: Optional[str] = None,
        context_module: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        # 1. Normalization
        clean_query = query_entity.lower().strip()
        norm_query = normalize_entity_name(clean_query)
        matches = []
        is_crud = intent in ["create", "update", "delete"]

        nav_stmt = select(NavigationItem).where(NavigationItem.client_id == client_id)   
        nav_result = await session.execute(nav_stmt)
        nav_items = nav_result.scalars().all()
        table_module_map = {item.table_name: item.module for item in nav_items if item.table_name}
        get_match_score = EntitySelector._get_match_score

        def determine_priority(base_priority: int, score: float, cand_module: Optional[str]) -> int:
            if score >= 0.9:
                return base_priority
            if context_module and cand_module and context_module.lower() == cand_module.lower():
                return 4
            return 5

        # --- 1. Match Semantic Mappings (Priority 1) ---
        from app.models.semantic_mapping import SemanticMapping
        import json
        sm_stmt = select(SemanticMapping).where(SemanticMapping.client_id == client_id)
        sm_result = await session.execute(sm_stmt)
        for sm in sm_result.scalars().all():
            sm_mod = table_module_map.get(sm.database_table)
            if context_module and sm_mod and context_module.lower() != sm_mod.lower():
                continue

            labels_to_check = [a.strip() for a in (sm.ui_label or "").split(",") if a.strip()]
            if sm.synonyms:
                try:
                    syn_list = json.loads(sm.synonyms) if isinstance(sm.synonyms, str) else sm.synonyms
                    if isinstance(syn_list, list):
                        labels_to_check.extend([s.strip() for s in syn_list if s.strip()])
                except Exception:
                    pass

            for lbl in labels_to_check:
                score = get_match_score(clean_query, lbl)
                if score > 0:
                    prio = determine_priority(1, score, sm_mod)
                    if not any(m["table_name"] == sm.database_table for m in matches):
                        matches.append({"table_name": sm.database_table, "label": labels_to_check[0], "module": sm_mod, "priority": prio, "score": score, "strategy": "Semantic Mapping"})
                        break

        # --- 2. Match Navigation Labels (Priority 2) ---
        for item in nav_items:
            if is_crud and not item.table_name: continue
            
            # Module Filtering Requirement
            if context_module and item.module and context_module.lower() != item.module.lower():
                continue

            score = get_match_score(clean_query, item.label)
            if score > 0:
                prio = determine_priority(2, score, item.module)
                match_key = item.table_name if item.table_name else f"nav_path:{item.path}"
                if not any(m["table_name"] == match_key for m in matches):
                    matches.append({"table_name": match_key, "label": item.label, "module": item.module, "priority": prio, "score": score, "strategy": "Navigation"})

        # --- 3. Match Semantic Metadata (Priority 3) ---
        sem_stmt = select(SemanticMetadata).where(
            SemanticMetadata.client_id == client_id,
            (SemanticMetadata.column_name == None) | (SemanticMetadata.column_name == "")
        )
        sem_result = await session.execute(sem_stmt)
        for sem in sem_result.scalars().all():
            sem_mod = table_module_map.get(sem.table_name)
            
            # Module Filtering
            if context_module and sem_mod and context_module.lower() != sem_mod.lower():
                continue
                
            score = get_match_score(clean_query, sem.label)
            if score > 0:
                prio = determine_priority(3, score, sem_mod)
                if not any(m["table_name"] == sem.table_name for m in matches):
                    matches.append({"table_name": sem.table_name, "label": sem.label, "module": sem_mod, "priority": prio, "score": score, "strategy": "Semantic Label"})
            
            if sem.synonyms:
                for syn in sem.synonyms:
                    syn_score = get_match_score(clean_query, syn)
                    if syn_score > 0:
                        prio = determine_priority(3, syn_score, sem_mod)
                        if not any(m["table_name"] == sem.table_name for m in matches):
                            matches.append({"table_name": sem.table_name, "label": sem.label, "module": sem_mod, "priority": prio, "score": syn_score, "strategy": "Semantic Synonym"})

        # --- 4. Match Raw Table Names (Fallback) ---
        for table in available_tables:
            tab_mod = table_module_map.get(table)
            
            # Module Filtering
            if context_module and tab_mod and context_module.lower() != tab_mod.lower():
                continue
                
            score = get_match_score(clean_query, table)
            if score > 0:
                prio = determine_priority(5, score, tab_mod)
                if not any(m["table_name"] == table for m in matches):
                    matches.append({"table_name": table, "label": EntitySelector.format_table_label(table), "module": tab_mod, "priority": prio, "score": score, "strategy": "Raw Table"})

        # --- Step 5: Handle Missing Entity ---
        if not matches:
            print(f"[ENTITY_RESOLUTION] No match found for '{query_entity}'.")
            return []

        # --- Ranking & selection ---
        # priority ascending (1 is best), score descending (1.0 is best)
        matches.sort(key=lambda x: (x["priority"], -x["score"]))
        best = matches[0]

        # Debug Logging Requirement
        print(f"\n--- ENTITY RESOLUTION DEBUG ---")
        print(f"Query: '{query_entity}' -> '{norm_query}'")
        for m in matches[:5]:
            print(f"  [{m['priority']}] {m['label']} ({m['table_name']}) | Score: {m['score']:.2f} | Strategy: {m['strategy']}")
        print(f"✅ Selected: {best['label']} ({best['table_name']}) via {best['strategy']}")
        print(f"-------------------------------\n")

        final_matches = []
        seen = set()
        for m in matches:
            if m["priority"] == best["priority"] and m["score"] == best["score"]:
                key = (m["table_name"], m["label"], m["module"])
                if key not in seen:
                    seen.add(key)
                    final_matches.append({"table_name": m["table_name"], "label": m["label"], "module": m["module"]})

        # Hierarchy fallback for multiple exact matches (e.g. Header vs Detail)
        resolved_matches = final_matches
        if is_crud and len(final_matches) > 1:
            header = next((m for m in final_matches if "header" in m["table_name"].lower()), None)
            if header: resolved_matches = [header]
            
        import json
        audit_data = {
            "query": query_entity,
            "normalized_query": norm_query,
            "module": context_module,
            "candidates": [m["label"] for m in matches[:5]],
            "selected_label": resolved_matches[0]["label"] if resolved_matches else None,
            "selected_table": resolved_matches[0]["table_name"] if resolved_matches else None,
            "resolution_strategy": best["strategy"] if resolved_matches else None,
            "score": best["score"] if resolved_matches else None
        }
        print(f"ENTITY_RESOLUTION_AUDIT:\n{json.dumps(audit_data, indent=2)}")
            
        return resolved_matches

    @staticmethod
    def format_table_label(table_name: str) -> str:
        prefixes = ["mst_", "tbl_", "ref_", "sys_", "api_"]
        label = table_name
        for p in prefixes:
            if label.startswith(p):
                label = label[len(p):]
                break
        return label.replace("_", " ").title()
