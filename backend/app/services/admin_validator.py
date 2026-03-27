from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from app.models.navigation import NavigationItem
from app.models.semantic_metadata import SemanticMetadata
from app.models.client_config import ClientConfig
from app.services.onboarding import discover_tables
from typing import List, Dict, Any, Optional
import difflib

class AdminValidator:
    @staticmethod
    async def get_configuration_warnings(client_id: int, session: AsyncSession) -> Dict[str, Any]:
        warnings = []
        
        # Fetch client config for DB discovery
        client_stmt = select(ClientConfig).where(ClientConfig.id == client_id)
        result = await session.execute(client_stmt)
        client = result.scalars().first()
        
        available_tables = []
        if client and client.db_connection_url:
            try:
                # We use sync discovery here, might want to wrap in run_in_executor if hit often
                schema = discover_tables(client.db_connection_url)
                available_tables = [t['name'] for t in schema]
            except Exception as e:
                print(f"⚠️ Could not discover tables for validation: {e}")

        # 1. Navigation Validation
        nav_stmt = select(NavigationItem).where(NavigationItem.client_id == client_id)
        result = await session.execute(nav_stmt)
        nav_items = result.scalars().all()
        
        labels_seen = {}
        for item in nav_items:
            # Check for missing table mapping
            if not item.table_name:
                suggested_table = None
                if available_tables:
                    # Try to find a match for the label (e.g. "Lead Category" -> "master_leadcategory")
                    clean_label = (item.label or "").lower().replace(" ", "").replace("master", "").replace("list", "")
                    matches = difflib.get_close_matches(clean_label, available_tables, n=1, cutoff=0.3)
                    if not matches:
                        # Try searching for substring
                        matches = [t for t in available_tables if clean_label in t.replace("_", "")]
                    
                    if matches:
                        suggested_table = matches[0]

                warnings.append({
                    "id": f"nav_missing_{item.id}",
                    "type": "navigation_missing_table",
                    "severity": "warning",
                    "message": f"Navigation item '{item.label}' has no table mapping.",
                    "item_id": item.id,
                    "suggested_fix": {
                        "action": "update_navigation",
                        "item_id": item.id,
                        "field": "table_name",
                        "value": suggested_table,
                        "description": f"Map to table '{suggested_table}'" if suggested_table else "Manually select a table"
                    }
                })
            
            # Check for missing module
            if not item.module:
                warnings.append({
                    "id": f"nav_module_{item.id}",
                    "type": "navigation_missing_module",
                    "severity": "info",
                    "message": f"Navigation item '{item.label}' has no module assigned.",
                    "item_id": item.id,
                    "suggested_fix": {
                        "action": "update_navigation",
                        "item_id": item.id,
                        "field": "module",
                        "value": "Master", # Sensible default for most ERP setups
                        "description": "Set module to 'Master'"
                    }
                })
            
            # Duplicate Label Detection
            if item.label in labels_seen:
                suggested_label = f"{item.label} ({item.module or 'Other'})"
                warnings.append({
                    "id": f"duplicate_{item.id}",
                    "type": "duplicate_label",
                    "severity": "error",
                    "message": f"Duplicate label found: '{item.label}'.",
                    "item_id": item.id,
                    "suggested_fix": {
                        "action": "update_navigation",
                        "item_id": item.id,
                        "field": "label",
                        "value": suggested_label,
                        "description": f"Rename to '{suggested_label}'"
                    }
                })
            else:
                labels_seen[item.label] = item.id

        # 2. Semantic Conflict Detection
        sem_stmt = select(SemanticMetadata).where(SemanticMetadata.client_id == client_id)
        result = await session.execute(sem_stmt)
        sem_entries = result.scalars().all()
        
        synonym_map = {} # synonym -> List[SemanticMetadata]
        for entry in sem_entries:
            if not entry.synonyms:
                continue
            for syn in entry.synonyms:
                syn_lower = syn.lower().strip()
                if syn_lower not in synonym_map:
                    synonym_map[syn_lower] = []
                synonym_map[syn_lower].append(entry)
        
        for syn, entries in synonym_map.items():
            if len(entries) > 1:
                # Suggest keeping the one that has the most synonyms or is a 'master' table
                best_entry = sorted(entries, key=lambda e: (len(e.synonyms or []), "master" in (e.table_name or "").lower()), reverse=True)[0]
                to_remove = [e for e in entries if e.id != best_entry.id]
                
                warnings.append({
                    "id": f"syn_conflict_{syn}",
                    "type": "semantic_conflict",
                    "severity": "error",
                    "message": f"Synonym conflict: '{syn}' maps to multiple tables ({', '.join([str(e.table_name) for e in entries])}).",
                    "synonym": syn,
                    "suggested_fix": {
                        "action": "resolve_synonym_conflict",
                        "keep_id": best_entry.id,
                        "remove_from_ids": [e.id for e in to_remove],
                        "synonym": syn,
                        "description": f"Keep for '{best_entry.table_name}', remove from others"
                    }
                })

        response = {
            "warnings": warnings,
            "available_tables": available_tables
        }
        return response

    @staticmethod
    async def term_search(client_id: int, term: str, session: AsyncSession) -> List[Dict[str, Any]]:
        """
        Searches for all occurrences of a term across Navigation and Semantic Metadata.
        """
        results = []
        term_lower = term.lower().strip()
        
        # Search Navigation
        nav_stmt = select(NavigationItem).where(
            NavigationItem.client_id == client_id,
            func.lower(NavigationItem.label).contains(term_lower)
        )
        nav_res = await session.execute(nav_stmt)
        for item in nav_res.scalars().all():
            results.append({
                "source": "navigation",
                "id": f"nav_{item.id}", # Prefix to avoid ID collisions in frontend
                "db_id": item.id,
                "label": item.label,
                "table": item.table_name,
                "module": item.module
            })
            
        # Search Semantic Metadata
        # We perform filtering in Python for synonyms to ensure cross-dialect safety
        sem_stmt = select(SemanticMetadata).where(SemanticMetadata.client_id == client_id)
        sem_res = await session.execute(sem_stmt)
        for entry in sem_res.scalars().all():
            label_match = term_lower in (entry.label or "").lower()
            syn_match = any(term_lower in str(s).lower() for s in (entry.synonyms or []))
            
            if label_match or syn_match:
                results.append({
                    "source": "semantic",
                    "id": f"sem_{entry.id}",
                    "db_id": entry.id,
                    "label": entry.label,
                    "table": entry.table_name,
                    "column": entry.column_name,
                    "module": "Semantic Layer"
                })
        
        return results[:20] # Limit results
