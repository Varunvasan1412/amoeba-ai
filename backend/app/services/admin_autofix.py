from sqlalchemy.ext.asyncio import AsyncSession
from app.models.navigation import NavigationItem
from app.models.semantic_metadata import SemanticMetadata
from typing import Dict, Any, List

class AdminAutofix:
    @staticmethod
    async def apply_fix(fix_payload: Dict[str, Any], session: AsyncSession, commit: bool = True) -> tuple[bool, Dict[str, Any]]:
        """
        Applies a single fix. Return tuple of (success, undo_payload).
        If commit=False, it adds to session but doesn't commit yet.
        """
        action = fix_payload.get("action")
        undo_payload = None
        
        try:
            if action == "update_navigation":
                item_id = fix_payload.get("item_id")
                field = fix_payload.get("field")
                value = fix_payload.get("value")
                
                item = await session.get(NavigationItem, item_id)
                if item and field and hasattr(item, field):
                    # Capture for undo
                    undo_payload = {
                        "action": "update_navigation",
                        "item_id": item.id,
                        "field": field,
                        "value": getattr(item, field),
                        "description": f"Revert {field} to original value"
                    }
                    
                    setattr(item, field, value)
                    session.add(item)
                    if commit: await session.commit()
                    return True, undo_payload
                else:
                    print(f"⚠️ NavigationItem {item_id} not found for update.")
                    return False, None
            elif action == "resolve_synonym_conflict":
                remove_from_ids = fix_payload.get("remove_from_ids", [])
                synonym = fix_payload.get("synonym")
                
                # In a real undo for synonym conflict we'd need to re-add the synonyms
                # For now, we'll construct a simplified version or just return None
                # As a basic implementation, we can skip full undo for semantic conflicts for now.
                for entry_id in remove_from_ids:
                    entry = await session.get(SemanticMetadata, entry_id)
                    if entry and entry.synonyms:
                        new_syns = [s for s in entry.synonyms if s.lower().strip() != synonym.lower().strip()]
                        entry.synonyms = new_syns
                        session.add(entry)
                
                if commit: await session.commit()
                return True, None
                
            elif action == "rename_semantic_label":
                entry_id = fix_payload.get("entry_id")
                new_term = fix_payload.get("new_term")
                old_term = fix_payload.get("old_term")
                is_synonym = fix_payload.get("is_synonym", False)

                entry = await session.get(SemanticMetadata, entry_id)
                if entry:
                    undo_payload = {
                        "action": "rename_semantic_label",
                        "entry_id": entry.id,
                        "new_term": old_term,
                        "old_term": new_term,
                        "is_synonym": is_synonym,
                        "description": f"Reverted '{new_term}' back to '{old_term}'"
                    }

                    if is_synonym and entry.synonyms:
                        # Replace the old synonym with the new term, or delete if empty
                        if new_term.strip() == "":
                            new_syns = [s for s in entry.synonyms if s.lower().strip() != old_term.lower().strip()]
                        else:
                            new_syns = [new_term if s.lower().strip() == old_term.lower().strip() else s for s in entry.synonyms]
                        entry.synonyms = new_syns
                    else:
                        entry.label = new_term

                    session.add(entry)
                    if commit: await session.commit()
                    return True, undo_payload
                else:
                    print(f"⚠️ SemanticMetadata {entry_id} not found for rename.")
                    return False, None

            elif action == "rename_navigation_label":
                item_id = fix_payload.get("item_id")
                new_label = fix_payload.get("new_label")
                old_label = fix_payload.get("old_label")

                item = await session.get(NavigationItem, item_id)
                if item:
                    undo_payload = {
                        "action": "rename_navigation_label",
                        "item_id": item.id,
                        "new_label": old_label,
                        "old_label": new_label,
                        "description": f"Reverted navigation label '{new_label}' back to '{old_label}'"
                    }
                    item.label = new_label
                    session.add(item)
                    if commit: await session.commit()
                    return True, undo_payload
                else:
                    print(f"⚠️ NavigationItem {item_id} not found for label rename.")
                    return False, None

        except Exception as e:
            print(f"❌ Error applying fix: {e}")
            if commit: await session.rollback()
            return False, None
            
        return False, None

    @staticmethod
    async def batch_apply_fixes(client_id: int, session: AsyncSession) -> Dict[str, Any]:
        """
        Applies all recommended fixes in a single transaction.
        """
        from app.services.admin_validator import AdminValidator
        
        # 1. Get current warnings
        results = await AdminValidator.get_configuration_warnings(client_id, session)
        warnings = results.get("warnings", [])
        
        # 2. Filter for items that HAVE a clear auto-suggestion
        # We skip items that require "Manual Selection"
        fixable = [w for w in warnings if w.get("suggested_fix") and w["suggested_fix"].get("value") is not None]
        
        if not fixable:
            return {
                "total_warnings": len(warnings),
                "applied": 0,
                "status": "nothing_to_fix",
                "message": "No auto-suggestions found among current warnings."
            }
        
        # 3. Apply all successfully in ONE transaction
        success_count = 0
        try:
            applied_fixes = []
            undo_fixes = []
            
            for w in fixable:
                payload = w["suggested_fix"]
                success, undo_payload = await AdminAutofix.apply_fix(payload, session, commit=False)
                
                if success:
                    success_count += 1
                    if undo_payload:
                        undo_fixes.append(undo_payload)
            
            await session.commit()
            return {
                "total_warnings": len(warnings),
                "fixable": len(fixable),
                "applied": success_count,
                "undo_fixes": undo_fixes,
                "status": "success",
                "message": f"Successfully applied {success_count} configuration fixes."
            }
        except Exception as e:
            await session.rollback()
            return {
                "status": "error",
                "message": f"Critical error during batch fix: {str(e)}",
                "applied": 0
            }

    @staticmethod
    async def run_batch(fixes: List[Dict[str, Any]], session: AsyncSession) -> Dict[str, Any]:
        """
        Applies an arbitrary list of fixes in one transaction.
        Used for Revert or custom multi-select fixes.
        """
        success_count = 0
        undo_fixes = []
        try:
            for fix in fixes:
                success, undo_payload = await AdminAutofix.apply_fix(fix, session, commit=False)
                if success:
                    success_count += 1
                    if undo_payload:
                        undo_fixes.append(undo_payload)
                        
            await session.commit()
            if success_count == 0 and len(fixes) > 0:
                return {"applied": 0, "status": "failed", "message": "No changes were applied. Check if the items still exist."}
            return {"applied": success_count, "status": "success", "undo_fixes": undo_fixes}
        except Exception as e:
            await session.rollback()
            return {"status": "error", "message": str(e)}
