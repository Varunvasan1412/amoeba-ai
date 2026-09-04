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
async def tool_navigate_frontend(url_path: str, client_id: int = None):
    """
    REQUIRED: Call this tool when the user says 'navigate', 'go to', or 'open' a page.
    Args:
        url_path (str): The path to navigate to (e.g., '/about', '/contact', '/').
    """
    if not client_id:
        return "Navigation signal sent (No validation)."
        
    from app.core.database import async_session
    from app.models.navigation import NavigationItem
    from sqlmodel import select
    
    async with async_session() as session:
        # Strip trailing slashes and base urls to compare paths safely
        clean_path = url_path.split("?")[0].strip("/")
        
        stmt = select(NavigationItem).where(NavigationItem.client_id == client_id)
        res = await session.execute(stmt)
        valid_items = res.scalars().all()
        
        for item in valid_items:
            item_clean = item.path.split("?")[0].strip("/")
            # If the LLM guessed the exact path, allow it
            if item_clean.endswith(clean_path) or clean_path.endswith(item_clean):
                return f"Navigation signal sent. (Matched: {item.label})"
                
        # If no match found, block the navigation to prevent a 404
        return f"ERROR: The path '{url_path}' DOES NOT EXIST in the database. DO NOT guess URLs. You MUST call tool_lookup_route with keywords (like 'Account') to find the real URLs, and ask the user to clarify if multiple match."


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
async def tool_lookup_route(query: str, client_id: int):
    """
    Look up the exact URL path for a page using a natural language query.
    USE THIS BEFORE `tool_navigate_frontend` if the user gives a generic name like "Sales Report" or "Unit Master".
    Returns the path (e.g. "sterling_company/...") or suggestions.
    """
    if not client_id:
        return "Internal Error: Navigation context missing."
    from app.core.database import async_session
    async with async_session() as session:
        return await lookup_external_route(query, session, client_id)

@tool
async def tool_learn_route(label: str, path: str, keywords: str = "", client_id: int = None):
    """
    Teach the AI a new route shortcut.
    Use this when the user says "Remember that 'My Page' is at 'sterling/my_page'".
    Args:
        label: The name of the page.
        path: The actual URL path.
        keywords: CAUTION: Comma-separated keywords (e.g. "my, page, custom").
    """
    if not client_id:
        return "Internal Error: Navigation context missing."
    kw_list = [k.strip() for k in keywords.split(",")] if keywords else []
    from app.core.database import async_session
    async with async_session() as session:
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

async def get_brain(client_id: int = None, session: AsyncSession = None, model_override: str = None):
    # Default values from env
    provider = settings.AI_PROVIDER.upper()
    model_name = settings.OLLAMA_MODEL
    temperature = 0.0
    
    print(f"🕵️ [BRAIN DEBUG] Starting initialization for Client: {client_id} (Override: {model_override})")
    
    if model_override:
        model_name = model_override
        # Determine provider based on model name
        if "gemini" in model_override.lower():
            provider = "GEMINI"
        elif "gpt" in model_override.lower():
            provider = "OPENAI"
        else:
            provider = "OLLAMA"
        print(f"🎯 [BRAIN DEBUG] Using Model Override: {model_name} (Provider: {provider})")

    if client_id and session and not model_override:
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
            await session.rollback()
            print(f"❌ [BRAIN DEBUG] Error fetching DB settings for Client {client_id}: {e}")

    key_exists = bool(settings.GOOGLE_API_KEY) if provider == "GEMINI" else bool(settings.OPENAI_API_KEY)
    print(f"🧠 [BRAIN DEBUG] INITIALIZING: {provider} | Model: {model_name} | Key: {key_exists}")
    
    llm = None
    try:
        if provider == "GEMINI":
            if settings.GOOGLE_API_KEY:
                valid_model = model_name if "gemini" in model_name.lower() else "gemini-1.5-flash"
                llm = ChatGoogleGenerativeAI(
                    model=valid_model, 
                    google_api_key=settings.GOOGLE_API_KEY,
                    temperature=temperature,
                    max_retries=5
                )
        elif provider == "OPENAI" or provider == "GPT4":
            if settings.OPENAI_API_KEY:
                # Users often put fake branding names like 'GPT-5.6-LUNA' in the DB. This crashes OpenAI with a 400 error.
                valid_model = model_name if "gpt-" in model_name.lower() else "gpt-4o-mini"
                llm = ChatOpenAI(
                    model=valid_model,
                    openai_api_key=settings.OPENAI_API_KEY,
                    temperature=temperature,
                    max_retries=5
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
                    timeout=300
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

async def get_response(user_input: str, history: List[Any] = [], session: AsyncSession = None, client_id: int = None, memory_summary: str = "", model_override: str = None): 
    try:
        res_brain = await get_brain(client_id, session, model_override=model_override)
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
   - 🕒 TEMPORAL PRIORITY: When a user asks for records "from this week/month", prioritize filtering on `created_at`, `creation_date`, or `date` columns. Avoid using "effective" range columns unless the user is specifically asking about availability.
   - 🕒 TRANSPARENCY: When responding to a temporal query, ALWAYS explicitly state the resolved date range (e.g., "From 2026-04-08 to 2026-04-15") so the user knows exactly what timeframe was queried.

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
   - Step 2: Analysis and IMMEDIATE ACTION: if there is a single high-confidence match, CALL `tool_navigate_frontend` IMMEDIATELY.
   - Step 3: DISAMBIGUATION: If multiple ambiguous routes are returned (e.g. they asked for 'Accounts' but you found 'Account Details' and 'Accounts Category'), DO NOT call the navigate tool. Instead, reply to the user listing the exact labels found and ask them which one they meant.
   - 🛑 CRITICAL: DO NOT construct URLs yourself. ONLY use path from `tool_lookup_route`.

9. DATABASE ACTIONS:
   - If the user asks to "Add/Update/Delete/Read" ERP records:
     - Step 1: Call `tool_inspect_database()`.
     - Step 2: Use specialized CRUD tools (`tool_create_erp_record`, etc.).
     - 🛑 CRITICAL: Do NOT use raw SQL tools for standard record management.
     - 🛑 CRITICAL: Use the exact JSON format. 'table_name' MUST be at the top level of arguments.
     - Example: {{"table_name": "products", "filters_json": {{"status": "active"}}, "limit": 10}}

EOE
"""
        if "Extract filters for table" in user_input or "Your task is to parse filters" in user_input:
            system_prompt_text = f"You are a headless JSON parsing utility. You NEVER chat. You NEVER explain. You NEVER construct SQL. You ONLY output a single, structurally valid JSON object matching the requested schema. Use the following dynamic date context if needed: {date_context_str}"

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
        session_total_tokens = 0
        
        # 🚨 FORCE JSON MODE FOR DELEGATED READS ON OLLAMA
        if "OLLAMA" in current_provider.upper() and ("Extract filters for table" in user_input or "Your task is to parse filters" in user_input or "[SYSTEM: Execute READ/AGGREGATE" in user_input):
            print("🔧 [BRAIN] Forcing strict format='json' for Ollama read delegation.")
            llm_with_tools = base_llm.bind(format="json")

        
        for turn in range(6):
            print(f"🔄 TURN {turn+1} START", flush=True)
            try:
                ai_msg = await asyncio.wait_for(llm_with_tools.ainvoke(messages), timeout=300.0)
                
                # --- NEW: TOKEN USAGE LOGGING ---
                if hasattr(ai_msg, "response_metadata") and "token_usage" in ai_msg.response_metadata:
                    usage = ai_msg.response_metadata["token_usage"]
                    in_tokens = usage.get("prompt_tokens", 0)
                    out_tokens = usage.get("completion_tokens", 0)
                    total_tokens = usage.get("total_tokens", 0)
                    session_total_tokens += total_tokens
                    print(f"💰 [TOKEN USAGE] Input: {in_tokens} | Output: {out_tokens} | Total: {total_tokens}")
                # --------------------------------
                
            except asyncio.TimeoutError:
                provider_desc = "local AI model (Ollama)" if current_provider == "OLLAMA" else f"AI service ({current_provider})"
                print(f"💥 LLM Timeout: The {provider_desc} took too long to respond.")
                return f"The {provider_desc} is taking too long to respond (timeout). This usually happens when the model is still loading from disk or the system is under heavy load. Please try again or wait a moment.", []
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
                
                # --- OLLAMA FALLBACK PARSER ---
                # Smaller models tend to output {"name": "tool_read_...} OR {"tool": "tool_read_..."} 
                # as literal text instead of using native tool bindings.
                import re
                json_match = re.search(r'(\{[\s\S]*"(name|tool)"[\s\S]*"tool_[a-zA-Z_]+"[\s\S]*\})', final_text)
                if json_match:
                    try:
                        raw_tool = json.loads(json_match.group(1))
                        t_name = raw_tool.get("name") or raw_tool.get("tool")
                        t_args = raw_tool.get("parameters") or raw_tool.get("args")
                        
                        # If the AI put args at the top level (very common for small models)
                        if not t_args:
                            # Filter out known non-arg keys to treat the rest as args
                            t_args = {k: v for k, v in raw_tool.items() if k not in ["name", "tool", "parameters", "args"]}

                        if t_name and t_args is not None:
                            tool_calls = [{
                                "name": t_name,
                                "args": t_args,
                                "id": "call_ollama_fallback"
                            }]
                            # CRITICAL: Mutate the ai_msg so the ToolMessage isn't orphaned
                            ai_msg.tool_calls = tool_calls
                            ai_msg.content = "" # clear the ugly json from chat
                            
                            print(f"🔧 [OLLAMA FALLBACK] Extracted tool call for {t_name} with {len(t_args)} args")
                    except Exception as e:
                        print(f"⚠️ [OLLAMA FALLBACK] Failed to parse JSON block: {e}")
                
                if not tool_calls:
                    if final_text.strip().startswith("{") and "text" in final_text:
                         try:
                             data = json.loads(final_text)
                             if "text" in data:
                                 final_text = data["text"]
                         except:
                             pass
                    if final_text.strip() == "{}":
                        final_text = "I'm here! How can I help you with the ERP system?"
                        
                    if session_total_tokens > 0:
                        final_text += f"\n\n*(💰 {session_total_tokens} tokens)*"
                        try:
                            await session.execute(
                                __import__('sqlalchemy').text("UPDATE clientconfig SET total_tokens_used = COALESCE(total_tokens_used, 0) + :t WHERE id = :cid"),
                                {"t": session_total_tokens, "cid": client_id}
                            )
                            await session.commit()
                        except Exception:
                            pass
                        
                    return final_text, pending_actions
            
            print(f"🛠️ Executing {len(tool_calls)} Tools...")
            short_circuit_return = None
            
            for tool_call in tool_calls:
                tool_name = tool_call["name"]
                args = tool_call["args"]
                tool_result = f"Error: Tool {tool_name} failed."
                
                if tool_name == "tool_navigate_frontend":
                    selected_tool = TOOL_MAP.get(tool_name)
                    args["client_id"] = client_id
                    tool_result = await selected_tool.ainvoke(args)
                    
                    if "ERROR:" not in tool_result:
                        pending_actions.append({"type": "NAVIGATE", "payload": args.get("url_path")})
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
                        # NEW: Inject context for ALL data-aware tools
                        if tool_name in [
                            "tool_lookup_route", "tool_learn_route", "tool_execute_sql", 
                            "tool_read_erp_records", "tool_create_erp_record", 
                            "tool_update_erp_records", "tool_delete_erp_records"
                        ]:
                             args["client_id"] = client_id
                             
                        # SAFETY NET: Small models sometimes omit table_name even though it was heavily prompted
                        if tool_name == "tool_read_erp_records" and not args.get("table_name"):
                             import re
                             table_match = re.search(r"Execute READ on table '([^']+)'", user_input)
                             if table_match:
                                 args["table_name"] = table_match.group(1)
                                 print(f"🔧 [SAFETY NET] Auto-injected missing table_name: {args['table_name']}")
                        
                        if hasattr(selected_tool, "ainvoke"):
                            tool_result = await selected_tool.ainvoke(args)
                        else:
                            tool_result = selected_tool.invoke(args)
                            
                        # INJECT NATIVE DATA TABLE for read operations
                        if tool_name == "tool_read_erp_records":
                            print(f"🕵️ [TRACE] Entering tool_read_erp_records hook. tool_result type: {type(tool_result)}")
                            try:
                                data = None
                                if isinstance(tool_result, (list, dict)):
                                    print("🕵️ [TRACE] tool_result is list/dict natively")
                                    data = tool_result
                                elif isinstance(tool_result, str):
                                    print("🕵️ [TRACE] tool_result is string")
                                    # If it's the custom formatted "RESULTS:\n[...]\n\nWARNING:..." string
                                    if tool_result.startswith("RESULTS:\n"):
                                        print("🕵️ [TRACE] string starts with RESULTS:\\n")
                                        json_part = tool_result.split("RESULTS:\n")[1].split("\n\nWARNING:")[0]
                                        print(f"🕵️ [TRACE] extracted json_part starting with: {json_part[:20]}")
                                        data = json.loads(json_part)
                                    elif tool_result.startswith("[") or tool_result.startswith("{"):
                                        print("🕵️ [TRACE] string starts with [ or {")
                                        data = json.loads(tool_result)
                                else:
                                    print("🕵️ [TRACE] tool_result is something else!")
                                
                                if data is not None:
                                    print(f"🕵️ [TRACE] data is populated, type: {type(data)}")
                                    
                                    # Handle Aggregated Dict Result
                                    if isinstance(data, dict) and "aggregate" in data:
                                        print(f"🕵️ [TRACE] Detected aggregate result: {data['aggregate']} = {data['value']}")
                                        agg_type = data.get("aggregate", "Result").upper()
                                        agg_val = data.get("value")
                                        agg_col = data.get("column", "Count")
                                        
                                        pending_actions.append({
                                            "type": "data_table",
                                            "payload": {
                                                "title": f"{agg_type} Summary",
                                                "headers": [agg_col, "Value"],
                                                "rows": [{agg_col: f"Total {agg_type}", "Value": str(agg_val)}],
                                                "total": 1,
                                                "query_payload": {
                                                    "table_name": args.get("table_name", ""),
                                                    "filters": args.get("filters_json", None),
                                                    "user_query": user_input,
                                                    "client_id": int(client_id)
                                                }
                                            }
                                        })
                                        short_circuit_return = f"The result for your {agg_type} query is **{agg_val}**. I have displayed the summary above."
                                    
                                    # Handle Grouped Results
                                    elif isinstance(data, dict) and "grouped_results" in data:
                                        records = data["grouped_results"]
                                        if isinstance(records, list) and len(records) > 0:
                                            headers = list(records[0].keys())
                                            pending_actions.append({
                                                "type": "data_table",
                                                "payload": {
                                                    "title": "Grouped Analysis",
                                                    "headers": headers,
                                                    "rows": records,
                                                    "total": len(records),
                                                    "query_payload": {
                                                        "table_name": args.get("table_name", ""),
                                                        "filters": args.get("filters_json", None),
                                                        "user_query": user_input,
                                                        "client_id": int(client_id)
                                                    }
                                                }
                                            })
                                            short_circuit_return = f"I have calculated the breakdown by group for you. There are {len(records)} groups in total."

                                    # Handle Standard List Result
                                    else:
                                        records = data.get("records", data) if isinstance(data, dict) else data
                                        if isinstance(records, list):
                                            print(f"🕵️ [TRACE] records is a list with {len(records)} items")
                                            headers = list(records[0].keys())[:8] if records else []
                                            rows = [{h: str(r.get(h, ""))[:50] for h in headers} for r in records]
                                            pending_actions.append({
                                                "type": "data_table",
                                                "payload": {
                                                    "title": args.get("table_name", "Data Results"),
                                                    "headers": headers,
                                                    "rows": rows,
                                                    "total": len(records),
                                                    "query_payload": {
                                                        "table_name": args.get("table_name", ""),
                                                        "filters": args.get("filters_json", None),
                                                        "user_query": user_input,
                                                        "client_id": int(client_id)
                                                    }
                                                }
                                            })
                                            if records:
                                                short_circuit_return = f"I retrieved the {len(records)} records you asked for. You can view them exactly in the table format above."
                                            else:
                                                short_circuit_return = f"I executed the query, but no records were found matching your criteria."
                                    
                                    print(f"🕵️ [TRACE] short_circuit_return ASSIGNED: {short_circuit_return}")
                                else:
                                    print("🕵️ [TRACE] data is None!")
                            except Exception as parse_e:
                                import traceback
                                print(f"⚠️ Could not parse tool_read_erp_records output for UI: {parse_e}")
                                # traceback.print_exc() is too noisy for production loops                           print(f"⚠️ Could not parse tool_read_erp_records output for UI: {parse_e}\n{traceback.format_exc()}")
                    else:
                        tool_result = f"Tool {tool_name} not found."
                
                messages.append(ToolMessage(tool_call_id=tool_call["id"], content=str(tool_result)))
                if any(x in str(tool_result) for x in ["http", "/static/", "saved"]):
                    pending_actions.append({"type": "TOOL_RESULT", "payload": str(tool_result)})
            
            if short_circuit_return:
                if session_total_tokens > 0:
                    short_circuit_return += f"\n\n*(💰 {session_total_tokens} tokens)*"
                return short_circuit_return, pending_actions

        return "Error: Maximum agent turns reached.", pending_actions

    except Exception as e:
        import traceback
        print(f"❌ get_response Error: {e}\n{traceback.format_exc()}")
        return f"System Error: {e}", []
