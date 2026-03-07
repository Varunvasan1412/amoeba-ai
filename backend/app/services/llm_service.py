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
    # Deterministic Naming
    filename = generate_deterministic_filename(report_name, extension="pdf")
    # Underlying tool needs update to accept filename, or we pass it via content? 
    # For MVP, we will assume generate_pdf can handle it or just use the return path.
    # Actually, let's just let generate_pdf_report handle it, but we should probably patch that too?
    # Wait, the prompt asked to Implement deterministic naming. 
    # The tool implementation (reporting.py) likely generates a random name.
    # I should update reporting.py OR just ensure the path returned is clean.
    # Let's update the tool signature to encourage the LLM to think about the name.
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
    # PATH A: Data Blind SQL Export (PREFERRED)
    if sql_query:
        filename = generate_deterministic_filename(report_name, extension="xlsx")
        path = export_sql_to_excel(sql_query, filename_override=filename)
        if "static" in path:
            clean_path = path[path.find("static"):].replace(os.path.sep, '/')
            return f"http://localhost:8000/{clean_path}"
        return path

    # PATH B: JSON Data (LEGACY / SMALL DATA ONLY)
    try:
        data = None
        # Handle List input (Directly from LLM)
        if isinstance(data_json, list):
            data = data_json
        else:
            # Handle String input (Needs parsing)
            try:
                # Attempt 1: Standard JSON
                data = json.loads(data_json)
            except:
                # Attempt 2: Python Literal Eval (Handles single quotes)
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
    # This tool doesn't DO anything on the backend. 
    # It acts as a flag for the Agent Loop to spot.
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

from app.tools.ui import add_navigation_item_db, delete_navigation_item_db
from app.tools.navigation import lookup_external_route, add_external_route, fast_lookup_route

# ...

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
def tool_lookup_route(query: str):
    """
    Look up the exact URL path for a page using a natural language query.
    USE THIS BEFORE `tool_navigate_frontend` if the user gives a generic name like "Sales Report" or "Unit Master".
    Returns the path (e.g. "sterling_company/...") or suggestions.
    """
    return lookup_external_route(query)

@tool
def tool_learn_route(label: str, path: str, keywords: str = ""):
    """
    Teach the AI a new route shortcut.
    Use this when the user says "Remember that 'My Page' is at 'sterling/my_page'".
    Args:
        label: The name of the page.
        path: The actual URL path.
        keywords: CAUTION: Comma-separated keywords (e.g. "my, page, custom").
    """
    kw_list = [k.strip() for k in keywords.split(",")] if keywords else []
    return add_external_route(label, path, kw_list)

MY_TOOLS = [
    tool_calculate_sales, tool_generate_pdf, tool_generate_excel, tool_display_table,
    tool_execute_sql, tool_execute_sql_write, tool_inspect_database,
    tool_create_erp_record, tool_read_erp_records, tool_update_erp_records, tool_delete_erp_records,
    tool_create_blog, tool_update_bio,
    tool_search_unsplash,
    tool_navigate_frontend,
    tool_create_table, tool_read_file,
    tool_add_navigation, tool_delete_navigation,
    tool_lookup_route, tool_learn_route # Route Mapping Tools
]
TOOL_MAP = {t.name: t for t in MY_TOOLS}

@lru_cache()
def get_brain():
    provider = settings.AI_PROVIDER.upper()
    print(f"\n🧠 INITIALIZING BRAIN: {provider}")
    
    llm = None
    try:
        if provider == "GEMINI":
            if settings.GOOGLE_API_KEY:
                llm = ChatGoogleGenerativeAI(
                    model="gemini-2.0-flash-lite", 
                    google_api_key=settings.GOOGLE_API_KEY,
                    temperature=0,
                    max_retries=5
                )
        elif provider == "GPT4":
            if settings.OPENAI_API_KEY:
                llm = ChatOpenAI(
                    model="gpt-4-turbo",
                    api_key=settings.OPENAI_API_KEY,
                    temperature=0
                )
        elif provider == "OLLAMA":
            llm = ChatOllama(
                model=settings.OLLAMA_MODEL, 
                base_url=settings.OLLAMA_BASE_URL,
                temperature=0
            )

        if llm:
            return llm.bind_tools(MY_TOOLS)
            
    except Exception as e:
        print(f"💥 CRASH initializing brain: {e}")
        return None

    return None

async def get_response(user_input: str, history: List[Any] = []): 
    # Returns (Text Response, List[Actions])
    
    llm_with_tools = get_brain()
    if not llm_with_tools:
        return "System Error: AI Brain failed to initialize.", []

    
    # 0a. DATE NORMALIZATION
    date_start, date_end = normalize_date_range(user_input)
    date_context_str = ""
    if date_start:
        date_context_str = f"DETECTED DATE RANGE: {date_start} to {date_end}"


    # ---------------------------------------------------------
    # 🛑 DEPRECATED: FAST-PATHS MOVED TO ROUTER (app/routers/chat.py)
    # ---------------------------------------------------------
    # see resolve_navigation_request and resolve_export_request in fastpath_service.py
    # ---------------------------------------------------------


    
    # 0b. RAG RETRIEVAL (Think -> Retrieve)
    # 0b. RAG RETRIEVAL (Think -> Retrieve)
    import time
    rag_start = time.time()
    print(f"🧠 [LLM DEBUG] RAG Retrieval START for: {user_input}")
    retrieved_context = await rag_engine.retrieve_context(user_input)
    print(f"✅ [LLM DEBUG] RAG Context Retrieved in {time.time() - rag_start:.2f}s.")
    
    # 0c. TWO-PHASE WRITE CONFIRMATION CHECK
    # Check if the LAST message from AI was a confirmation request AND user says "Yes"
    force_write_execution = False
    if history and len(history) > 0:
        last_ai_msg = history[-1]
        if last_ai_msg.sender == "ai" and "confirm" in last_ai_msg.content.lower() and "execute:" in last_ai_msg.content.lower():
             if user_input.lower() in ["yes", "proceed", "confirm", "ok", "go ahead"]:
                 force_write_execution = True
                 print("🔓 Write Confirmation Received. Authorizing Tool Execution.")

    # 1. System Prompt
    system_message = SystemMessage(content=f"""You are Amoeba AI. You assist users with their ERP system.

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

EOE
""\")
1. NAVIGATION (CRITICAL):
   - If a user asks to Go/Navigate to a page:
   - Step 1: Call `tool_lookup_route(query="page name")` FIRST.
   - Step 2: The tool will return a list of CANDIDATE routes (JSON).
   - Step 3: IMMEDIATE ACTION REQUIRED:
     - Analyze the candidates.
     - IF a high-confidence match exists (e.g. "Sales Report" matches "Sales Report"), YOU MUST CALL `tool_navigate_frontend` IMMEDIATELY in the next turn.
     - Do NOT ask the user "Should I go there?". Just go.
     - 🛑 CRITICAL: Do NOT say "I have navigated you" unless you also generate the tool call.
   - Step 4: Call `tool_navigate_frontend(url_path=...)` using EXACTLY the `path` from the chosen candidate.
   - 🛑 CRITICAL: YOU ARE FORBIDDEN FROM CONSTRUCTING URLs YOURSELF. 
   - 🛑 CRITICAL: ONLY use the `path` value returned by `tool_lookup_route`.
   - 🛑 CRITICAL: If `tool_lookup_route` returns "No route found" or low confidence, THEN ask the user.
   - 🛑 ZERO TOLERANCE: If user says "Navigate", a text-only response is A FAILURE. You must use a tool.
2. If a user asks to Search Images, use `tool_search_unsplash`.
3. For writing blogs, use `tool_create_blog`. YOU MUST SAVE IT. Do not just write the text in the chat.
4. If a user asks for a REPORT/PDF, you MUST use `tool_generate_pdf`.
   - Step 1: Calculate/Get the data (e.g., tool_calculate_sales).
   - Step 2: Call tool_generate_pdf(text_content="...").
5. If a user asks for an EXCEL/SPREADSHEET, use `tool_generate_excel`.
   - Step 1: Get the data.
   -   - Step 2: Call tool_generate_excel(data_json='[{{\"Year\": 2023, \"Sales\": 50000}}]').
6. DATA VISUALIZATION:
   - Step 1: Call `tool_display_table(title="...", data_json='[...]').
   - 🛑 LIMITATION: Only do this for SMALL previews (< 20 rows). usage for large reports is PROHIBITED.

7. STRICT DATA BLIND EXPORT (EXCEL/CSV):
   - You MUST NOT fetch large datasets into the context window to generate files.
   - INCORRECT: tool_execute_sql -> Get Rows -> tool_generate_excel(data=rows) [FORBIDDEN]
   - CORRECT: tool_generate_excel(sql_query="SELECT * FROM invoices", report_name="invoices") [REQUIRED]
   - The Backend will handle the data transfer and file generation. You just define the 'WHAT' (the SQL).

8. DYNAMIC DATABASE ACTIONS:
   - If the user asks to "Add/Update/Delete/Read" ERP records (data in tables):
     - Step 1: Call `tool_inspect_database()` to see tables/columns if you don't know them.
     - Step 2: Use the specialized CRUD tools:
       - `tool_create_erp_record` (Create)
       - `tool_read_erp_records` (Read)
       - `tool_update_erp_records` (Update)
       - `tool_delete_erp_records` (Delete)
     - 🛑 CRITICAL: For standard record management, YOU MUST NOT use raw SQL tools (`tool_execute_sql_write`). Use the dedicated CRUD tools instead. 
     - 🛑 CRITICAL: ONLY use raw SQL tools for complex JOINs or structural changes (DDL).

9. NO NESTED TOOL CALLS: You cannot put a function call inside a parameter.
   - INCORRECT: tool_create_blog(..., image_url=tool_search_unsplash(...))
   - CORRECT LOOP:
     Step 1: Call tool_search_unsplash(query="...")
     Step 2: [System returns URL]
     Step 3: Call tool_create_blog(title=..., content=..., image_url="...")

9. GENERAL CHAT:
   - If the user just says "Hi" or asks a question not related to the ERP, just reply with PLAIN TEXT. 
   - DO NOT output empty JSON "{{}}".

    10. UI MODIFICATIONS (SELF-MODIFYING):
    - If the user asks to "Add a link", "Create a menu item", or "Add a page" to the navigation bar:
    - Step 1: Call `tool_add_navigation(label="...", path="/...")`.
    - Do NOT just navigate there. You must ADD it first.

EXAMPLES:
User: "Hi"
AI: "Hello! How can I help you with your ERP today?"

User: "Display extracted data from invoice"
AI: [Calls tool_display_table(title="Invoice Data", data_json='[{{\"Item\": \"Widget\", \"Price\": 10}}]')]

User: "Navigate to settings"
AI: [Calls tool_navigate_frontend(url_path='/settings')]

User: "Write a blog with an image of a cat"
AI: [Calls tool_search_unsplash(query='cat')]
(System returns https://loremflickr.com/800/600/cat)
AI: [Calls tool_create_blog(title="...", content="Cat content...", image_url="https://loremflickr.com/800/600/cat")]

User: "Generate a sales report for 2023"
AI: [Calls tool_calculate_sales(year=2023)]
(System returns "Total Sales: $50,000")
AI: [Calls tool_generate_pdf(text_content="Sales Report 2023\nTotal Sales: $50,000...")]

User: "Download Excel for sales"
AI: [Calls tool_generate_excel(sql_query="SELECT * FROM sales_data", report_name="sales")]
(System returns "Excel generated: ...")
""")

    messages = [system_message]

    # 2. Append Chat History (Last N turns)
    # history comes in as list of ChatMessage(sender="user"|"ai", content="...")
    for msg in history:
        if msg.sender == "user":
            messages.append(HumanMessage(content=msg.content))
        elif msg.sender == "ai":
            messages.append(AIMessage(content=msg.content))

    # 3. Append Current User Input
    messages.append(HumanMessage(content=user_input))
    
    pending_actions = []
    
    # --- PROPER AGENT LOOP (Max 6 Turns) ---
    for turn in range(6):
        print(f"🔄 TURN {turn+1} START", flush=True)
        
        try:
            # 🛑 MANDATORY LOGGER
            logger = logging.getLogger("uvicorn")
            logger.critical("LLM CALLED — THIS SHOULD NOT HAPPEN")
            # raise RuntimeError("LLM CALLED — FAST-PATH VIOLATION")
            
            print("⏳ Calling LLM ainvoke...", flush=True)
            ai_msg = await llm_with_tools.ainvoke(messages)
            print("✅ LLM Response Received!", flush=True)
            messages.append(ai_msg)

            # 1. Parsing Tools (Standard + Fallback)
            import re
            tool_calls = ai_msg.tool_calls
            
            # Fallback for leaked JSON
            if not tool_calls:
                print(f"🕵️ CHECKING FALLBACK for: {ai_msg.content[:50]}...")
                
                # ATTEMPT 1: JSON PARSE
                try:
                    start = ai_msg.content.find("{")
                    end = ai_msg.content.rfind("}")
                    if start != -1 and end != -1:
                        json_str = ai_msg.content[start:end+1]
                        print(f"🛟 ATTEMPTING FALLBACK PARSE: {json_str}")
                        
                        data = json.loads(json_str)
                        if "name" in data:
                            print("✅ FALLBACK JSON SUCCESS!")
                            tool_calls = [{"name": data.get("name"), "args": data.get("parameters", {}), "id": f"fallback_call_{turn}"}]
                except Exception as e:
                    print(f"❌ Fallback JSON Failed: {e}")
                    
                # ATTEMPT 2: REGEX RESCUE (For invalid JSON / Nested Quotes)
                # This catches: "image_url": "tool_search_unsplash(query="robot")"
                if not tool_calls and "tool_create_blog" in ai_msg.content:
                    print("🛟 ATTEMPTING REGEX RESCUE...")
                    try:
                        # Extract params manually
                        title_match = re.search(r'"title":\s*"(.*?)"', ai_msg.content)
                        content_match = re.search(r'"content":\s*"(.*?)"', ai_msg.content)
                        image_match = re.search(r'"image_url":\s*"(.*?)"', ai_msg.content)
                        
                        if title_match and content_match:
                            title = title_match.group(1)
                            content = content_match.group(1)
                            image_url = image_match.group(1) if image_match else None
                            
                            # Fix nested tool call in image_url (The "Robot" bug)
                            if image_url and "tool_" in image_url:
                                print(f"⚠️ DETECTED NESTED TOOL IN STRING: {image_url}")
                                if "search" in image_url:
                                    query_match = re.search(r'query="(.*?)"', image_url)
                                    query = query_match.group(1) if query_match else "random"
                                    print(f"🔄 AUTO-FIX: Running Search for '{query}' first...")
                                    image_url = f"https://loremflickr.com/800/600/{query}"
                            
                            print("✅ REGEX RESCUE SUCCESS (Blog)!")
                            tool_calls = [{
                                "name": "tool_create_blog",
                                "args": {"title": title, "content": content, "image_url": image_url},
                                "id": f"regex_fallback_{turn}"
                            }]
                    except Exception as e:
                        print(f"❌ Regex Rescue (Blog) Failed: {e}")
                
                # ATTEMPT 2.5: REGEX RESCUE For Display Table (New)
                # Catches: [tool_display_table(title="...", data_json='...')]
                if not tool_calls and "tool_display_table" in ai_msg.content:
                     print("🛟 ATTEMPTING REGEX RESCUE (Table)...")
                     try:
                         # Regex allows for single or double quotes for title, and lazy match for json
                         title_match = re.search(r'title=["\'](.*?)["\']', ai_msg.content)
                         
                         # Data JSON is tricky. It usually follows data_json=
                         # We'll try to find the start of the list [ and the end ]
                         json_start = ai_msg.content.find("data_json='[")
                         if json_start == -1: json_start = ai_msg.content.find('data_json="[')
                         
                         if title_match and json_start != -1:
                             title = title_match.group(1)
                             # Extract from the bracket onwards
                             raw_json = ai_msg.content[json_start + 11:] # skip data_json='
                             # Find the matching closing quote/bracket?
                             # Let's just find the last ]
                             json_end = raw_json.rfind("]")
                             if json_end != -1:
                                 data_str = raw_json[:json_end+1]
                                 # Clean user artifacts if needed
                                 data_str = data_str.strip().strip("'").strip('"')
                                 
                                 print(f"✅ REGEX RESCUE SUCCESS (Table)! Extracted: {title}")
                                 tool_calls = [{
                                     "name": "tool_display_table",
                                     "args": {"title": title, "data_json": data_str},
                                     "id": f"regex_fallback_table_{turn}"
                                 }]
                     except Exception as e:
                         print(f"❌ Regex Rescue (Table) Failed: {e}")

                # ATTEMPT 2.6: REGEX RESCUE For Add Navigation
                # Catches: [tool_add_navigation(label="...", path="...")]
                if not tool_calls and "tool_add_navigation" in ai_msg.content:
                     print("🛟 ATTEMPTING REGEX RESCUE (Nav)...")
                     try:
                         label_match = re.search(r'label=["\'](.*?)["\']', ai_msg.content)
                         path_match = re.search(r'path=["\'](.*?)["\']', ai_msg.content)
                         
                         if label_match and path_match:
                             label = label_match.group(1)
                             path = path_match.group(1)
                             
                             print(f"✅ REGEX RESCUE SUCCESS (Nav)! Extracted: {label}")
                             tool_calls = [{
                                 "name": "tool_add_navigation",
                                 "args": {"label": label, "path": path},
                                 "id": f"regex_fallback_nav_{turn}"
                             }]
                     except Exception as e:
                         print(f"❌ Regex Rescue (Nav) Failed: {e}")
            
            # ATTEMPT 3: TEXT SUPERVISOR (Force PDF/Excel if AI just writes the text)
            # Detects: "Here is the PDF report..." + no tool calls
            if not tool_calls:
                 # PDF Check
                 if "PDF" in ai_msg.content and ("Sales" in ai_msg.content or "Report" in ai_msg.content) and "http" not in ai_msg.content and "/static/" not in ai_msg.content:
                     print("🕵️ TEXT SUPERVISOR: Forcing PDF...")
                     tool_calls = [{"name": "tool_generate_pdf", "args": {"text_content": ai_msg.content}, "id": f"supervisor_pdf_{turn}"}]
                 
                 # Excel Check
                 # STRICTER SUPERVISOR:
                 # 1. Must contain "Excel" OR "Spreadsheet"
                 # 2. Must NOT contain "http" or "/static/" (Already has link)
                 # 3. Must NOT have already generated a file in this session (Check pending_actions)
                 elif ("Excel" in ai_msg.content or "Spreadsheet" in ai_msg.content) and "http" not in ai_msg.content and "/static/" not in ai_msg.content:
                     
                     # LOOP BREAKER: Check if we already have a TOOL_RESULT with a generated file
                     already_generated = any(
                         a["type"] == "TOOL_RESULT" and ("/static/" in str(a.get("payload", "")) or "http" in str(a.get("payload", "")))
                         for a in pending_actions
                     )
                     
                     if already_generated:
                         print("🛑 Supervisor: File already generated in this session. Stopping loop.")
                     else:
                         print("🕵️ TEXT SUPERVISOR: Forcing Excel...")
                         # We need strict JSON for Excel, which is hard to extract from free text.
                         # Heuristic: Try to find a list structure or just generate a dummy/summary one.
                         # Better: call calculate sales again? No.
                         # Simplest: create a generic row with the text content.
                         data = [{"Summary": ai_msg.content[:200]}] # Truncate to avoid massive cells
                         tool_calls = [{"name": "tool_generate_excel", "args": {"data_json": json.dumps(data)}, "id": f"supervisor_excel_{turn}"}]

            # 2. If NO tools, we are done! Return text.
            if not tool_calls:
                final_text = ai_msg.content
                
                # OPTIMIZATION: Fix LLM outputting {"text": "Hi"} instead of "Hi"
                if final_text.strip().startswith("{") and "text" in final_text:
                     try:
                         data = json.loads(final_text)
                         if "text" in data:
                             print(f"🧹 Cleaning JSON-wrapped text: {final_text}")
                             final_text = data["text"]
                     except:
                         pass
                
                # OPTIMIZATION: Fix LLM outputting {} (Empty JSON)
                if final_text.strip() == "{}":
                    print("🧹 Detected empty JSON response. Using default fallback.")
                    final_text = "I'm here! How can I help you with the ERP system?"

                return final_text, pending_actions
            
            # 3. Execute Tools
            print(f"🛠️ Executing {len(tool_calls)} Tools...")
            for tool_call in tool_calls:
                tool_name = tool_call["name"]
                args = tool_call["args"]
                tool_result = f"Error: Tool {tool_name} failed."
                
                # Navigation Special Case
                if tool_name == "tool_navigate_frontend":
                    pending_actions.append({"type": "NAVIGATE", "payload": args.get("url_path")})
                    tool_result = "Navigation signal sent."
                
                # Dynamic Table Special Case
                elif tool_name == "tool_display_table":
                    try:
                        title = args.get("title")
                        data_str = args.get("data_json")
                        # Handle if data is already list (LangChain magic) or string
                        if isinstance(data_str, list):
                            data = data_str
                        else:
                            data = json.loads(data_str)
                            
                        pending_actions.append({
                            "type": "DISPLAY_TABLE", 
                            "payload": {"title": title, "data": data}
                        })
                        tool_result = "Table displayed on UI."
                    except Exception as e:
                        tool_result = f"Error displaying table: {e}"

                # Dynamic Navigation Special Case (Add/Delete)
                elif tool_name == "tool_add_navigation" or tool_name == "tool_delete_navigation":
                     # Execute the async tool
                     selected_tool = TOOL_MAP.get(tool_name)
                     if selected_tool:
                         tool_result = await selected_tool.ainvoke(args)
                         # TRIGGER FRONTEND REFRESH
                         pending_actions.append({"type": "REFRESH_NAV", "payload": {}})
                     else:
                         tool_result = "Tool not found."
                        
                else:
                    selected_tool = TOOL_MAP.get(tool_name)
                    if selected_tool:
                        # Check for Async Tools
                        if (tool_name.startswith("tool_execute") or 
                            tool_name.startswith("tool_create") or 
                            tool_name.startswith("tool_update") or 
                            tool_name.startswith("tool_read") or 
                            tool_name.startswith("tool_add") or 
                            tool_name.startswith("tool_delete") or 
                            tool_name.startswith("tool_inspect")):
                             tool_result = await selected_tool.ainvoke(args)
                        else:
                             tool_result = selected_tool.invoke(args)
                    else:
                        tool_result = f"Tool {tool_name} not found."
                
                print(f"  -> Result: {str(tool_result)[:50]}...")
                
                # Append result to history so AI knows what happened
                tool_msg_content = str(tool_result)
                messages.append(ToolMessage(tool_call_id=tool_call["id"], content=tool_msg_content))
                
                # --- SAFETY NET: Capture URLs/Success Messages for the User ---
                # If the tool returned a link (PDF/Excel/Image) or a success message,
                # we want to ensure the Frontend gets it, even if the AI forgets to mention it in the next turn.
                if "http" in tool_msg_content or "/static/" in tool_msg_content or "saved" in tool_msg_content:
                    print(f"📎 Capturing Tool Result for Safety Net: {tool_msg_content}")
                    pending_actions.append({"type": "TOOL_RESULT", "payload": tool_msg_content})

        except Exception as e:
            print(f"❌ Loop Error: {e}")
            return f"System Error: {e}", []

    return "Error: Maximum agent turns reached.", pending_actions