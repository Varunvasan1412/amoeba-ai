# Amoeba AI v1 FIXED — Do not extend without version bump

import re
import json
import os
from typing import Tuple, Optional, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.models.report_registry import ReportRegistry

from app.tools.navigation import fast_lookup_route
from app.tools.reporting import export_sql_to_excel
from app.tools.dates import normalize_date_range
from app.tools.filenames import generate_deterministic_filename
from app.core.config import settings
# CHANGED: Import function matching instead of global object
from app.services.report_registry_service import match_report
from app.services.audit_service import log_audit
from app.core.rate_limiter import limiter

# -----------------------------------------------------------------------------
# 1. INTENT DETECTION
# -----------------------------------------------------------------------------

def is_export_intent(query: str) -> bool:
    """
    Liberal detection to avoid LLM fallthrough.
    """
    return bool(re.search(
        r"(?i)\b("
        r"export|extract|download|convert|"
        r"xlsx|excel|csv|spreadsheet|report"
        r")\b",
        query
    ))

def is_navigation_intent(query: str) -> bool:
    # 1. Detect standard navigation verbs (can be anywhere in the sentence)
    nav_pattern = r"(?i)\b(navigate(?:\s+me)?(?:\s+to)?|go\s+to|take\s+me\s+to|open)\s+(.+)$"
    if re.search(nav_pattern, query.strip()):
        return True
    
    # 2. Detect explicit button clicks from ambiguity resolution
    if "→" in query or "->" in query:
        return True
        
    return False

def extract_nav_target(query: str) -> str:
    """Helper to strip 'navigate to' prefix or button formatting"""
    # 1. Clean explicit button clicks
    if "→" in query:
        return query.split("→")[-1].strip()
    if "->" in query:
        return query.split("->")[-1].strip()
        
    # 2. Clean standard navigation verbs
    nav_pattern = r"(?i)\b(navigate(?:\s+me)?(?:\s+to)?|go\s+to|take\s+me\s+to|open)\s+(.+)$"
    match = re.search(nav_pattern, query.strip())
    if match:
        target = match.group(2).strip()
        # Remove common trailing punctuation
        target = re.sub(r"[?.!]+$", "", target).strip()
        # Remove common "the " or " page" wrapping if present
        target = re.sub(r"(?i)^(the\s+)", "", target).strip()
        target = re.sub(r"(?i)(\s+page)$", "", target).strip()
        return target
        
    return query.strip()

# -----------------------------------------------------------------------------
# 2. EXECUTION (FAST-PATH — NO LLM)
# -----------------------------------------------------------------------------

async def execute_fastpath(user_input: str, context: dict = {}, db_session: AsyncSession = None) -> Tuple[Optional[str], List[Any]]:
    """
    Returns (response_text, actions) if fast-path triggers.
    Returns (None, []) otherwise.
    
    Args:
        user_input: The user's message.
        context: Session context containing client_id.
        db_session: Database session for looking up reports & states.
    """
    
    # ----------------------------
    # 0. GLOBAL CANCEL CHECK
    # ----------------------------
    clean_input = user_input.strip().lower()
    if clean_input in ["cancel", "exit", "quit", "stop", "nevermind", "abort"]:
        # We don't delete state here; that's done by conversation_service,
        # but we do want to return immediately so we don't accidentally "search" for "cancel"
        return None, []

    client_id_val = context.get("client_id")
    if not client_id_val or client_id_val == "default" or not db_session:
         return None, [] # Graceful fall-through if no tenant context

    client_id_int = int(client_id_val)
    # Use the session_id from context if provided (essential for isolation)
    session_id = context.get("session_id") or f"sess_{client_id_int}"

    # ----------------------------
    # 0.5. PRE-CHECK: NEW NAVIGATION INTENT INTERRUPT
    # ----------------------------
    is_new_nav = is_navigation_intent(user_input)

    # ----------------------------
    # 1. CHECK EXISTING DB STATE FOR AMBIGUITY/PENDING
    # ----------------------------
    from app.services.conversation_service import get_active_conversation
    state = await get_active_conversation(db_session, client_id_int, session_id)
    # ----------------------------
    # 2. RESOLVE EXISTING PENDING STATE
    # ----------------------------
    if state and not is_new_nav:
        
        # A. Resolving Report Follow-up (Date Range)
        if state.intent == "fastpath_report":
            report_id = state.collected_data.get("report_id")
            
            if not report_id:
                await db_session.delete(state); await db_session.commit()
                return "Error: Cannot resume report (missing ID).", [{"type": "TOOL_RESULT", "payload": "CLEAR_PENDING"}]

            statement = select(ReportRegistry).where(ReportRegistry.id == report_id)
            result = await db_session.execute(statement)
            pending_report = result.scalars().first()
            
            if not pending_report:
                await db_session.delete(state); await db_session.commit()
                return "Error: This report definition has changed or been removed.", [{"type": "TOOL_RESULT", "payload": "CLEAR_PENDING"}]

            print(f"[ROUTER] Resuming Pending Report: {pending_report.display_name} with input '{user_input}'")
            
            start_date, end_date = normalize_date_range(user_input)
            
            if start_date:
                sql_query = pending_report.sql_template
                sql_query = sql_query.replace(":start_date", f"'{start_date}'").replace(":end_date", f"'{end_date}'")
                
                filename = generate_deterministic_filename(pending_report.display_name, extension="xlsx")
                file_path = export_sql_to_excel(sql_query, filename_override=filename)
                
                if "static" in file_path:
                    clean_path = file_path[file_path.find("static"):].replace(os.path.sep, "/")
                    file_url = f"{settings.PUBLIC_BASE_URL}/{clean_path}"
                else:
                    file_url = file_path
                
                await db_session.delete(state); await db_session.commit()
                fast_text = f"Export Complete: {file_url}"
                fast_actions = [{"type": "TOOL_RESULT", "payload": file_url}, {"type": "TOOL_RESULT", "payload": "CLEAR_PENDING"}]
                return fast_text, fast_actions
            else:
                return "I didn't understand that date. Please say 'today', 'last 30 days', etc.", []
                
        # B. Resolving Navigation Ambiguity
        elif state.intent == "fastpath_nav_ambiguity":
            candidates = state.collected_data.get("candidates", [])
            selection_idx = None
            
            idx_match = re.search(r"^(\d+)", clean_input)
            if idx_match:
                selection_idx = int(idx_match.group(1))
            else:
                for i, cand in enumerate(candidates):
                    if cand['label'].lower() == clean_input:
                        selection_idx = i + 1
                        break

            if selection_idx is not None and 1 <= selection_idx <= len(candidates):
                best_match = candidates[selection_idx - 1]
                parents_str = " → ".join(best_match.get("parents", []))
                full_label = f"{parents_str} → {best_match['label']}" if parents_str else best_match['label']
                
                await db_session.delete(state); await db_session.commit()
                return f"Navigating to {full_label}...", [{"type": "NAVIGATE", "payload": best_match['path']}]
            
            # If not a valid selection, fall through to allow NEW intent detection
            # (Inquiry or other commands will then clear this state)
            return None, []

    # ----------------------------
    # 3. NAVIGATION FAST-PATH (NEW)
    # ----------------------------
    if is_new_nav:
        print(f"[ROUTER] Navigation Intent: {user_input}")
        
        client_id_val = context.get("client_id")
        if not client_id_val or client_id_val == "default" or not db_session:
             return "I'm not sure which client context this is for. Please try again.", []

        target_page = extract_nav_target(user_input)
        # NEW: Async, Tenant-Aware Lookup
        path, ambiguous_list = await fast_lookup_route(target_page, db_session, int(client_id_val))

        if path:
            return f"Navigating...", [{"type": "NAVIGATE", "payload": path}]
            
        if ambiguous_list:
            options = []
            text_lines = [f"I found multiple pages named \"{ambiguous_list[0]['label']}\":", ""]
            
            for idx, cand in enumerate(ambiguous_list[:5]):
                parents = " → ".join(cand.get("parents", []))
                label = cand["label"]
                is_custom = cand.get("is_custom", False)
                
                # --- BEAUTIFY THE LABEL ---
                # 1. Remove redundant parent prefix if the label starts with it (e.g. "Master Master Account" -> "Account")
                clean_label = label
                for p in cand.get("parents", []):
                    if clean_label.lower().startswith(p.lower()):
                        clean_label = clean_label[len(p):].strip()
                
                # 2. Add spaces before common suffixes (list, edit, create, view, details)
                clean_label = re.sub(r'(list|edit|create|view|details|category|head|master|report)$', r' \1', clean_label, flags=re.IGNORECASE)
                clean_label = re.sub(r'(details)(list|edit|create|view)', r'\1 \2', clean_label, flags=re.IGNORECASE)
                clean_label = re.sub(r'(category)(list|edit|create|view)', r'\1 \2', clean_label, flags=re.IGNORECASE)
                
                # 3. Capitalize words cleanly
                clean_label = " ".join(word.capitalize() for word in clean_label.split())
                if not clean_label:
                    clean_label = label # fallback
                
                # Add a clear visual clue for custom routes
                display = f"{parents} → {clean_label}" if parents else clean_label
                if is_custom:
                    display = f"⭐ {display} (Custom)"
                
                text_lines.append(f"{idx + 1}) {display}")
                options.append({
                    "label": display, # Keep label clean for the button
                    "path": cand["path"],
                    "original_label": label,
                    "index": idx + 1, # Frontend will send this index back
                    "is_custom": is_custom
                })
            
            text_lines.append("")
            text_lines.append("Reply with the number of your choice.")
            final_text = "\n".join(text_lines)
            
            # SAVE EXPLICIT STATE TO DB SO CHOICE RESOLUTION WORKS NEXT TIME
            from app.models.conversation_state import ConversationState
            if state:
                await db_session.delete(state)
            
            ambig_state = ConversationState(
                client_id=client_id_int,
                session_id=session_id,
                intent="fastpath_nav_ambiguity",
                entity_name="navigation",
                current_step="resolve_choice",
                collected_data={"candidates": options}
            )
            db_session.add(ambig_state)
            await db_session.commit()

            actions = [{
                "type": "CHOICE", 
                "payload": options
            }, {
                "type": "SET_AMBIGUITY", 
                "payload": ambiguous_list 
            }]
            return final_text, actions

        return "I couldn't find that page in the sitemap.", []

    # ----------------------------
    # 3. EXPORT / REPORT FAST-PATH (REGISTRY ONLY)
    # ----------------------------
    client_id = context.get("client_id")
    
    # We need a valid client and DB session
    if client_id and db_session and client_id != "default":
        # Check Registry (Async DB Call)
        matched_report = await match_report(db_session, int(client_id), user_input)
        print(f"📁 [ROUTER] Searching report for Client {client_id}: '{user_input}'", flush=True)
        
        if matched_report:
            print(f"✅ [ROUTER] Registry Match: {matched_report.display_name} (ID: {matched_report.id})")
            
            # Check Parameters (Assuming simple date Logic for now)
            # We can check sql_template for parameters
            requires_dates = ":start_date" in matched_report.sql_template
            
            if requires_dates:
                 start_date, end_date = normalize_date_range(user_input)
                 if not start_date:
                     # Serialize report model to dict for context
                     report_context = {"report_id": matched_report.id}
                     
                     from app.models.conversation_state import ConversationState
                     if state:
                         await db_session.delete(state)
                     
                     report_state = ConversationState(
                         client_id=int(client_id),
                         session_id=session_id,
                         intent="fastpath_report",
                         entity_name=matched_report.display_name,
                         current_step="collect_date",
                         collected_data=report_context
                     )
                     db_session.add(report_state)
                     await db_session.commit()
                     print(f"📁 [ROUTER] Saved Pending Report State for: {matched_report.display_name}")

                     return f"Please provide a date range for the {matched_report.display_name} (e.g., 'last 30 days' or 'today').", [{"type": "SET_PENDING_REPORT", "payload": report_context}]
                 
                 # Prepare SQL
                 sql_query = matched_report.sql_template
                 sql_query = sql_query.replace(":start_date", f"'{start_date}'").replace(":end_date", f"'{end_date}'")
            else:
                 sql_query = matched_report.sql_template

            # RATE LIMIT CHECK
            if not limiter.check_export(int(client_id)):
                return "⚠️ usage limit reached. You can only export 10 reports per hour.", []

            # Execute
            try:
                filename = generate_deterministic_filename(matched_report.display_name, extension="xlsx")
                file_path = export_sql_to_excel(sql_query, filename_override=filename)

                # Build public URL
                if "static" in file_path:
                    clean_path = file_path[file_path.find("static"):].replace(os.path.sep, "/")
                    file_url = f"{settings.PUBLIC_BASE_URL}/{clean_path}"
                else:
                    file_url = file_path

                fast_text = f"Here is your {matched_report.display_name}: {file_url}"
                fast_actions = [{"type": "TOOL_RESULT", "payload": file_url}]
                
                log_audit(int(client_id), "report_exported", {"report": matched_report.display_name})
                return fast_text, fast_actions
            except Exception as e:
                log_audit(int(client_id), "report_failed", {"error": str(e)})
                return "I couldn't generate that report due to a temporary system issue. Please try again later.", []

    # B. Check Generic Export Intent (Hard Safety Guard)
    # If user wants to export/report but it wasn't in registry -> TERMINATE
    if is_export_intent(user_input):
        print(f"[ROUTER] Generic Export Intent Detected (No Registry Match): {user_input}")
    if is_export_intent(user_input):
        print(f"[ROUTER] Generic Export Intent Detected (No Registry Match): {user_input}")
        if context.get("client_id"):
             log_audit(int(context["client_id"]), "invalid_report_attempt", {"query": user_input})
        return "This report hasn’t been configured yet. Please ask your admin to enable it in the Control Panel.", []

    return None, []
