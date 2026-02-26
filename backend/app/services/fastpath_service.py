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
    nav_pattern = r"(?i)^(?:navigate|go|take me|open)(?:\s+to)?\s+(.+)$"
    return bool(re.search(nav_pattern, query.strip()))

def extract_nav_target(query: str) -> str:
    """Helper to strip 'navigate to' prefix"""
    nav_pattern = r"(?i)^(?:navigate|go|take me|open)(?:\s+to)?\s+(.+)$"
    match = re.search(nav_pattern, query.strip())
    if match:
        return match.group(1).strip()
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
        context: Session context containing 'ambiguity_candidates' if in a resolution loop.
        db_session: Database session for looking up reports.
    """

    # ----------------------------
    # 0. PRE-CHECK: NEW NAVIGATION INTENT INTERRUPT
    # ----------------------------
    is_new_nav = is_navigation_intent(user_input)

    # ----------------------------
    # 0.5. PENDING REPORT RESOLUTION (Follow-up)
    # ----------------------------
    if not is_new_nav and context and "pending_report" in context:
        report_payload = context["pending_report"]
        report_id = report_payload.get("report_id")
        
        # 🛡️ ARCHITECTURAL FIX: Fetch fresh report from DB
        # Context only holds ID. We must query the DB for the latest SQL.
        if not report_id or not db_session:
             return "Error: Cannot resume report (missing context or DB session).", [{"type": "TOOL_RESULT", "payload": "CLEAR_PENDING"}]

        statement = select(ReportRegistry).where(ReportRegistry.id == report_id)
        result = await db_session.execute(statement)
        pending_report = result.scalars().first()
        
        if not pending_report:
             return "Error: This report definition has changed or been removed.", [{"type": "TOOL_RESULT", "payload": "CLEAR_PENDING"}]

        print(f"[ROUTER] Resuming Pending Report: {pending_report.display_name} with input '{user_input}'")
        
        # We assume the user input IS the date range
        start_date, end_date = normalize_date_range(user_input)
        
        if start_date:
            # Execute
            sql_query = pending_report.sql_template
            sql_query = sql_query.replace(":start_date", f"'{start_date}'").replace(":end_date", f"'{end_date}'")
            
            filename = generate_deterministic_filename(pending_report.display_name, extension="xlsx")
            file_path = export_sql_to_excel(sql_query, filename_override=filename)
            
            # Build public URL
            if "static" in file_path:
                clean_path = file_path[file_path.find("static"):].replace(os.path.sep, "/")
                file_url = f"{settings.PUBLIC_BASE_URL}/{clean_path}"
            else:
                file_url = file_path
            
            fast_text = f"Export Complete: {file_url}"
            fast_actions = [{"type": "TOOL_RESULT", "payload": file_url}, {"type": "TOOL_RESULT", "payload": "CLEAR_PENDING"}]
            return fast_text, fast_actions
        else:
            return "I didn't understand that date. Please say 'today', 'last 30 days', etc.", []

    # ----------------------------
    # 1. AMBIGUITY RESOLUTION
    # ----------------------------
    if not is_new_nav and context and "ambiguity_candidates" in context:
        candidates = context["ambiguity_candidates"]
        
        # Strict Numeric Check
        try:
            selection_idx = int(user_input.strip())
            
            if 1 <= selection_idx <= len(candidates):
                best_match = candidates[selection_idx - 1]
                parents_str = " → ".join(best_match.get("parents", []))
                full_label = f"{parents_str} → {best_match['label']}" if parents_str else best_match['label']
                return f"Navigating to {full_label}...", [{"type": "NAVIGATE", "payload": best_match['path']}]
            else:
                return f"Please reply with a number between 1 and {len(candidates)}.", []
        except ValueError:
            return "Please reply with the number of your choice (e.g., '1' or '2').", []

    # ----------------------------
    # 2. NAVIGATION FAST-PATH
    # ----------------------------
    if is_new_nav:
        print(f"[ROUTER] Navigation Intent: {user_input}")
        
        target_page = extract_nav_target(user_input)
        path, ambiguous_list = fast_lookup_route(target_page)

        if path:
            return f"Navigating...", [{"type": "NAVIGATE", "payload": path}]
            
        if ambiguous_list:
            options = []
            text_lines = [f"I found multiple pages named \"{ambiguous_list[0]['label']}\":", ""]
            
            for idx, cand in enumerate(ambiguous_list[:5]):
                parents = " → ".join(cand.get("parents", []))
                label = cand["label"]
                display = f"{parents} → {label}" if parents else label
                
                text_lines.append(f"{idx + 1}) {display}")
                options.append({
                    "label": f"{idx + 1}) {display}",
                    "path": cand["path"],
                    "original_label": label,
                    "index": idx + 1
                })
            
            text_lines.append("")
            text_lines.append("Reply with the number of your choice.")
            final_text = "\n".join(text_lines)
            
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
        
        if matched_report:
            print(f"[ROUTER] Registry Match: {matched_report.display_name}")
            
            # Check Parameters (Assuming simple date Logic for now)
            # We can check sql_template for parameters
            requires_dates = ":start_date" in matched_report.sql_template
            
            if requires_dates:
                 start_date, end_date = normalize_date_range(user_input)
                 if not start_date:
                     # Serialize report model to dict for context
                     report_context = {"report_id": matched_report.id}
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
