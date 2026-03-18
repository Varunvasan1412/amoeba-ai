from __future__ import annotations
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, AIMessage
from langchain_core.tools import tool
from app.core.config import settings
from functools import lru_cache
from typing import Union, List, Any
import json
import os
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.models.ai_settings import AISettings

# Import our tools
from app.tools.reporting import calculate_sales, generate_pdf_report, generate_excel_report, display_data_table, export_sql_to_excel
from app.tools.files import read_file_content
from app.tools.database import get_database_schema, execute_sql_query, execute_sql_write, execute_ddl
from app.tools.crud import tool_create_erp_record, tool_read_erp_records, tool_update_erp_records, tool_delete_erp_records
from app.tools.management import create_blog_post, update_user_bio
from app.tools.content import search_unsplash_image
from app.tools.ui import add_navigation_item_db, delete_navigation_item_db
from app.services.rag_service import rag_engine
from app.tools.dates import normalize_date_range
from app.tools.filenames import generate_deterministic_filename
import logging
import asyncio

# 2. HELPER FUNCTIONS FOR FAST-PATH
def is_export_intent(query: str) -> bool:
    import re
    # Strict regex for export/download intent
    return bool(re.search(r"(?i)\b(export|download|generate excel|csv|spreadsheet)\b", query))

_REPORT_TEMPLATES = None
def resolve_export_request(query: str):
    global _REPORT_TEMPLATES
    if _REPORT_TEMPLATES is None:
        try:
            # Load templates
            base_path = os.path.dirname(os.path.dirname(__file__)) # backend/app
            path = os.path.join(base_path, "data", "report_execution_templates.json")
            with open(path, "r") as f:
                _REPORT_TEMPLATES = json.load(f)
        except Exception as e:
            print(f"Error loading report templates: {e}")
            return None
            
    # 1. Date Extraction
    start_date, end_date = normalize_date_range(query)
    
    # 2. Template Matching
    query_lower = query.lower()
    matched_template = None
    matched_name = None
    
    for name, template in _REPORT_TEMPLATES.items():
        # Improved Matching: Check if important keywords from Template Name appear in Query
        # e.g. "Sales Summary" -> matches if "sales" in query.
        name_tokens = name.lower().split()
        if any(token in query_lower for token in name_tokens):
             matched_template = template
             matched_name = name
             break
            
    if not matched_template:
        return None
        
    # 3. SQL Construction
    base_query = f"SELECT * FROM {matched_template['base_table']} WHERE {matched_template['base_where']}"
    
    if start_date and matched_template.get("date_column"):
        base_query += f" AND {matched_template['date_column']} BETWEEN '{start_date}' AND '{end_date}'"
        
    return base_query, matched_name

# 1. WRAP TOOLS
@tool
def tool_calculate_sales(year: int):
    """Calculates the total sales for a specific year. Returns a string summary."""
    return calculate_sales(year)

@tool
def tool_generate_pdf(text_content: str, report_name: str = "report"):
    """Generates a PDF report. REQUIRED: Provide a short 'report_name' for the file."""
    filename = generate_deterministic_filename(report_name, extension="pdf")
    path = generate_pdf_report(text_content, filename_override=filename)
    
    if "static" in path:
        clean_path = path.replace(os.path.sep, '/')
        return f"http://localhost:8000/{clean_path}"
    return path

@tool
def tool_generate_excel(data_json: str = None, sql_query: str = None, report_name: str = "export"):
    """
    Generates an Excel report. 
    REQUIRED: Provide 'report_name' AND ('sql_query' OR 'data_json').
    BEST PRACTICE: Use 'sql_query' for all database reports (Data Blind Mode).
    """
    if sql_query:
        filename = generate_deterministic_filename(report_name, extension="xlsx")
        path = export_sql_to_excel(sql_query, filename_override=filename)
        if "static" in path:
            clean_path = path[path.find("static"):].replace(os.path.sep, '/')
            return f"http://localhost:8000/{clean_path}"
        return path

    try:
        data = None
        if isinstance(data_json, list):
            data = data_json
        else:
            try:
                data = json.loads(data_json)
            except:
                import ast
                try:
                    data = ast.literal_eval(data_json)
                except:
                    pass
        
        if not data or not isinstance(data, list):
            return "Error: data_json must be a valid JSON list of dictionaries."

        filename = generate_deterministic_filename(report_name, extension="xlsx")
        path = generate_excel_report(data, filename_override=filename)
        
        if "static" in path:
            clean_path = path[path.find("static"):].replace(os.path.sep, '/')
            return f"http://localhost:8000/{clean_path}"
        return path
    except Exception as e:
        return f"Error parsing JSON for Excel: {e}"

@tool
def tool_display_table(title: str, data_json: str):
    """
    Renders a dynamic data table on the UI.
    Use this when the user asks to "Show table", "Display data", or "Visualize" the extraction results.
    Args:
        title (str): The title of the report/table.
        data_json (str): A JSON string representing a list of dictionaries. Example: '[{"Name": "A", "Value": 1}]'
    """
    return display_data_table(title, data_json)

@tool
async def tool_execute_sql(query: str):
    """Executes a READ-ONLY SQL query against the database. Use this to fetch data."""
    return await execute_sql_query(query)

@tool
async def tool_execute_sql_write(query: str):
    """
    Executes INSERT/UPDATE/DELETE queries.
    USE ONLY after confirming the table name via `tool_inspect_database`.
    """
    return await execute_sql_write(query)

@tool
async def tool_inspect_database():
    """
    Returns a list of all tables and columns in the database.
    Call this FIRST before writing any SQL to understand the schema.
    """
    return await get_database_schema()

@tool
async def tool_create_blog(title: str, content: str, image_url: str = None):
    """Safely creates a new blog post. Requires title and content. Optional image_url."""
    return await create_blog_post(title, content, image_url)

@tool
async def tool_update_bio(user_id: int, new_bio: str):
    """Safely updates a user's bio."""
    return await update_user_bio(user_id, new_bio)

@tool
def tool_search_unsplash(query: str):
    """Searches for an image on Unsplash. Returns an image URL."""
    return search_unsplash_image(query)

@tool
def tool_navigate_frontend(url_path: str):
    """
    REQUIRED: Call this tool when the user says 'navigate', 'go to', or 'open' a page.
    Args:
        url_path (str): The path to navigate to (e.g., '/about', '/contact', '/').
    """
    return "Navigation signal sent."

@tool
async def tool_create_table(query: str):
    """
    Executes DDL to CREATE or MODIFY tables.
    Use this when the user wants to create a new resource type.
    Example: "CREATE TABLE invoices (id SERIAL PRIMARY KEY, amount REAL)"
    """
    return await execute_ddl(query)

@tool
async def tool_read_file(file_path: str):
    """
    Reads the content of an uploaded file (Excel/CSV).
    Use this to inspect data before inserting it into the DB.
    Input: The 'filepath' returned from an upload.
    """
    return await read_file_content(file_path)

from app.tools.navigation import lookup_external_route, add_external_route

@tool
async def tool_add_navigation(label: str, path: str):
    """
    Adds a new item to the application's main navigation menu.
    Use this when the user says "Add a link to X" or "Create a menu item for Y".
    Args:
        label (str): The text to display (e.g., "Reports", "Sales").
        path (str): The internal path (e.g., "/report", "/sales").
    """
    return await add_navigation_item_db(label, path)

@tool
async def tool_delete_navigation(label: str):
    """
    Deletes a navigation item by its label.
    Use this when the user says "Remove the X link" or "Delete the menu item Y".
    Args:
        label (str): The exact label of the item to remove (e.g., "Reports").
    """
    return await delete_navigation_item_db(label)

@tool
async def tool_lookup_route(query: str, session: Any = None, client_id: Any = None):
    """
    Look up the exact URL path for a page using a natural language query.
    USE THIS BEFORE `tool_navigate_frontend` if the user gives a generic name like "Sales Report" or "Unit Master".
    Returns the path (e.g. "sterling_company/...") or suggestions.
    """
    if not session or not client_id:
        return "Internal Error: Navigation context missing."
    return await lookup_external_route(query, session, client_id)

@tool
async def tool_learn_route(label: str, path: str, keywords: str = "", session: Any = None, client_id: Any = None):
    """
    Teach the AI a new route shortcut.
    Use this when the user says "Remember that 'My Page' is at 'sterling/my_page'".
    Args:
        label: The name of the page.
        path: The actual URL path.
        keywords: CAUTION: Comma-separated keywords (e.g. "my, page, custom").
    """
    if not session or not client_id:
        return "Internal Error: Navigation context missing."
    kw_list = [k.strip() for k in keywords.split(",")] if keywords else []
    return await add_external_route(label, path, session, client_id, kw_list)

MY_TOOLS = [
    tool_calculate_sales, tool_generate_pdf, tool_generate_excel, tool_display_table,
    tool_execute_sql, tool_execute_sql_write, tool_inspect_database,
    tool_create_erp_record, tool_read_erp_records, tool_update_erp_records, tool_delete_erp_records,
    tool_create_blog, tool_update_bio,
    tool_search_unsplash,
    tool_navigate_frontend,
    tool_create_table, tool_read_file,
    tool_add_navigation, tool_delete_navigation,
    tool_lookup_route, tool_learn_route
]
TOOL_MAP = {t.name: t for t in MY_TOOLS}

async def get_brain(client_id: int = None, session: AsyncSession = None):
    # Default values from env
    provider = settings.AI_PROVIDER.upper()
    model_name = settings.OLLAMA_MODEL
    temperature = 0.0
    
    print(f"🕵️ [BRAIN DEBUG] Starting initialization for Client: {client_id}")
    
    if client_id and session:
        try:
            stmt = select(AISettings).where(AISettings.client_id == client_id)
            res = await session.execute(stmt)
            client_settings = res.scalars().first()
            if client_settings:
                provider = client_settings.provider.upper()
                model_name = client_settings.model
                temperature = client_settings.temperature
                print(f"✅ [BRAIN DEBUG] Found DB Settings for Client {client_id}: {provider} | {model_name}")
            else:
                print(f"⚠️ [BRAIN DEBUG] No DB Settings found for Client {client_id}. Using system fallback: {provider}")
        except Exception as e:
            print(f"❌ [BRAIN DEBUG] Error fetching DB settings for Client {client_id}: {e}")

    key_exists = bool(settings.GOOGLE_API_KEY) if provider == "GEMINI" else bool(settings.OPENAI_API_KEY)
    print(f"🧠 [BRAIN DEBUG] INITIALIZING: {provider} | Model: {model_name} | Key: {key_exists}")
    
    llm = None
    try:
        if provider == "GEMINI":
            if settings.GOOGLE_API_KEY:
                llm = ChatGoogleGenerativeAI(
                    model=model_name if "gemini" in model_name else "gemini-2.0-flash-lite", 
                    google_api_key=settings.GOOGLE_API_KEY,
                    temperature=temperature,
                    max_retries=5
                )
        elif provider == "OPENAI" or provider == "GPT4":
            if settings.OPENAI_API_KEY:
                llm = ChatOpenAI(
                    model=model_name if "gpt" in model_name else "gpt-4-turbo",
                    api_key=settings.OPENAI_API_KEY,
                    temperature=temperature
                )
        elif provider == "OLLAMA":
            import httpx
            urls = [settings.get_ollama_url(), "http://localhost:11434", "http://127.0.0.1:11434"]
            
            connected_url = None
            for url in urls:
                try:
                    print(f"📡 [BRAIN DEBUG] Testing Ollama at {url}...")
                    async with httpx.AsyncClient() as client:
                        resp = await asyncio.wait_for(client.get(f"{url}/api/tags"), timeout=3.0)
                        if resp.status_code == 200:
                            connected_url = url
                            print(f"✅ [BRAIN DEBUG] Ollama Connected at {url}")
                            break
                except Exception as conn_err:
                    print(f"⚠️ [BRAIN DEBUG] Failed to connect to {url}: {conn_err}")
                    continue
            
            if connected_url:
                llm = ChatOllama(
                    model=model_name, 
                    base_url=connected_url,
                    temperature=temperature,
                    timeout=120
                )
            else:
                print(f"❌ [BRAIN DEBUG] Ollama not reachable at any of {urls}")
                return None, provider, None

        if llm:
            # We return (Bound LLM, Provider Name, Raw LLM)
            # This allows fallbacks if the bound version fails due to tool support
            return llm.bind_tools(MY_TOOLS), provider, llm
            
    except Exception as e:
        print(f"💥 [BRAIN DEBUG] CRASH during initialization: {e}")
        return None, provider, None

    return None, provider, None

async def get_response(user_input: str, history: List[Any] = [], session: AsyncSession = None, client_id: int = None, memory_summary: str = ""): 
    try:
        res_brain = await get_brain(client_id, session)
        llm_with_tools = res_brain[0] if res_brain else None
        current_provider = res_brain[1] if res_brain else "UNKNOWN"
        base_llm = res_brain[2] if res_brain else None

        if not llm_with_tools:
            error_msg = f"System Error: AI Brain failed to initialize. (Provider: {current_provider}, Client: {client_id})"
            return error_msg, []

        date_start, date_end = normalize_date_range(user_input)
        date_context_str = ""
        if date_start:
            date_context_str = f"DETECTED DATE RANGE: {date_start} to {date_end}"

        import time
        rag_start = time.time()
        print(f"🧠 [LLM DEBUG] RAG Retrieval START for: {user_input}")
        retrieved_context = await rag_engine.retrieve_context(user_input, client_id=client_id, session=session)
        print(f"✅ [LLM DEBUG] RAG Context Retrieved in {time.time() - rag_start:.2f}s.")
        
        force_write_execution = False
        if history and len(history) > 0:
            last_ai_msg = history[-1]
            msg_role = last_ai_msg.get("role") if isinstance(last_ai_msg, dict) else getattr(last_ai_msg, "role", "")
            msg_content = last_ai_msg.get("content") if isinstance(last_ai_msg, dict) else getattr(last_ai_msg, "content", "")
            if msg_role == "ai" and "confirm" in msg_content.lower() and "execute:" in msg_content.lower():
                 if user_input.lower() in ["yes", "proceed", "confirm", "ok", "go ahead"]:
                     force_write_execution = True
                     print("🔓 Write Confirmation Received. Authorizing Tool Execution.")

        system_prompt_text = f"""You are Amoeba AI. You assist users with their ERP system.

### MEMORY (PAST CONVERSATIONS) ###
{memory_summary}

### RETRIEVED KNOWLEDGE (THE TRUTH) ###
--------------------------------------
{retrieved_context}
--------------------------------------
{date_context_str}

EXECUTION PROTOCOL (MANDATORY):
1. THINK: Analyze the user's request.
2. RETRIEVE: Look at the 'RETRIEVED KNOWLEDGE' above.
3. PLAN: 
   - If the user wants to navigate, find the EXACT path from [NAVIGATION].
   - If the user wants data, find the table from [DATABASE SCHEMA].
   - If the user wants a report, check [REPORTS] and [REPORT TEMPLATES].
   - If information is missing, STOP and ask the user.
4. TOOL: Execute the tool.

RULES:
1. NO HALLUCINATIONS:
   - You MUST NOT guess table names or URLs.
   - ONLY use what is in the [RETRIEVED KNOWLEDGE] section.
   
2. REPORT TEMPLATES (STRICT):
   - If a [REPORT TEMPLATE] is retrieved, you MUST follow it exactly.
   - Use ONLY the `base_table`, `base_where`, and `allowed_aggregations` defined.
   - Do NOT invent new columns or tables.
   
3. DATE HANDLING:
   - If 'DETECTED DATE RANGE' is provided above, USE IT in your SQL WHERE clauses (e.g. `order_date BETWEEN '{date_start}' AND '{date_end}'`).
   - Do NOT use '2023' or 'this month' in SQL. Use the specific dates.

4. SQL SAFETY (TWO-PHASE WRITE):
   - READ (SELECT) is allowed.
   - WRITE (INSERT/UPDATE/DELETE):
     - IF `{force_write_execution}` is TRUE, you may call `tool_execute_sql_write` NOW.
     - ELSE, you MUST NOT call the write tool yet.
     - Instead, output the PROPOSED SQL to the user and ask for confirmation.
     - Example: "I am about to execute: INSERT INTO ... Please confirm."
     - SCOPE SAFETY: Any UPDATE/DELETE MUST have a WHERE clause. "DELETE FROM users" is FORBIDDEN.

5. MANDATORY FILE GENERATION & NAMING:
   - If the user asks for a Report/Export:
   - Call `tool_generate_pdf` or `tool_generate_excel`.
   - You MUST provide a `report_name` argument (e.g. "sales_summary").
   - Do NOT construct the filename yourself.

6. DATA AGGREGATION (SMART GROUP-BY):
   - IGNORE `group_by` in templates IF the user asks for "Total", "Summary", or "Overall".
   - APPLY `group_by` IF the user asks for "Breakdown", "Per Customer", or "By Status".

7. NAVIGATION:
   - Use `tool_navigate_frontend(url_path=...)` only with paths found in [NAVIGATION].

8. NAVIGATION CRITICAL:
   - If a user asks to Go/Navigate to a page:
   - Step 1: Call `tool_lookup_route(query="page name")` FIRST.
   - Step 2: Analysis and IMMDIATE ACTION: if high-confidence match, CALL `tool_navigate_frontend` IMMEDIATELY.
   - 🛑 CRITICAL: DO NOT construct URLs yourself. ONLY use path from `tool_lookup_route`.

9. DATABASE ACTIONS:
   - If the user asks to "Add/Update/Delete/Read" ERP records:
     - Step 1: Call `tool_inspect_database()`.
     - Step 2: Use specialized CRUD tools (`tool_create_erp_record`, etc.).
     - 🛑 CRITICAL: Do NOT use raw SQL tools for standard record management.

EOE
"""
        system_message = SystemMessage(content=system_prompt_text)
        messages = [system_message]

        for msg in history:
            role = msg.role if hasattr(msg, "role") else msg.get("role")
            content = msg.content if hasattr(msg, "content") else msg.get("content")
            if role == "user":
                messages.append(HumanMessage(content=content))
            else:
                messages.append(AIMessage(content=content))

        messages.append(HumanMessage(content=user_input))
        pending_actions = []
        
        for turn in range(6):
            print(f"🔄 TURN {turn+1} START", flush=True)
            try:
                ai_msg = await asyncio.wait_for(llm_with_tools.ainvoke(messages), timeout=90.0)
            except asyncio.TimeoutError:
                print("💥 LLM Timeout: The model took too long to respond.")
                return "The AI model (Ollama) is taking too long to respond (timeout). This usually happens when the local system is under heavy load. Please try again in a moment.", []
            except Exception as tool_err:
                error_str = str(tool_err) if str(tool_err) else tool_err.__class__.__name__
                if "does not support tools" in error_str or "400" in error_str:
                    model_info = f"(Model: {res_brain[1]})" if res_brain else ""
                    error_msg = f"Error: The configured local model {model_info} does not support tool calling. Please upgrade to a tool-capable model (like llama3.1, llama3.2, or mistral) or switch to **Assistant Mode** for basic chat."
                    return error_msg, []
                raise tool_err
                
            messages.append(ai_msg)

            tool_calls = ai_msg.tool_calls
            if not tool_calls:
                final_text = ai_msg.content
                if final_text.strip().startswith("{") and "text" in final_text:
                     try:
                         data = json.loads(final_text)
                         if "text" in data:
                             final_text = data["text"]
                     except:
                         pass
                if final_text.strip() == "{}":
                    final_text = "I'm here! How can I help you with the ERP system?"
                return final_text, pending_actions
            
            print(f"🛠️ Executing {len(tool_calls)} Tools...")
            for tool_call in tool_calls:
                tool_name = tool_call["name"]
                args = tool_call["args"]
                tool_result = f"Error: Tool {tool_name} failed."
                
                if tool_name == "tool_navigate_frontend":
                    pending_actions.append({"type": "NAVIGATE", "payload": args.get("url_path")})
                    tool_result = "Navigation signal sent."
                elif tool_name == "tool_display_table":
                    try:
                        title = args.get("title")
                        data_str = args.get("data_json")
                        data = data_str if isinstance(data_str, list) else json.loads(data_str)
                        pending_actions.append({"type": "DISPLAY_TABLE", "payload": {"title": title, "data": data}})
                        tool_result = "Table displayed on UI."
                    except Exception as e:
                        tool_result = f"Error displaying table: {e}"
                elif tool_name in ["tool_add_navigation", "tool_delete_navigation"]:
                     selected_tool = TOOL_MAP.get(tool_name)
                     if selected_tool:
                         tool_result = await selected_tool.ainvoke(args)
                         pending_actions.append({"type": "REFRESH_NAV", "payload": {}})
                     else:
                         tool_result = "Tool not found."
                else:
                    selected_tool = TOOL_MAP.get(tool_name)
                    if selected_tool:
                        if tool_name in ["tool_lookup_route", "tool_learn_route"]:
                             args["session"] = session
                             args["client_id"] = client_id
                        
                        if hasattr(selected_tool, "ainvoke"):
                            tool_result = await selected_tool.ainvoke(args)
                        else:
                            tool_result = selected_tool.invoke(args)
                    else:
                        tool_result = f"Tool {tool_name} not found."
                
                messages.append(ToolMessage(tool_call_id=tool_call["id"], content=str(tool_result)))
                if any(x in str(tool_result) for x in ["http", "/static/", "saved"]):
                    pending_actions.append({"type": "TOOL_RESULT", "payload": str(tool_result)})

        return "Error: Maximum agent turns reached.", pending_actions

    except Exception as e:
        import traceback
        print(f"❌ get_response Error: {e}\n{traceback.format_exc()}")
        return f"System Error: {e}", []
