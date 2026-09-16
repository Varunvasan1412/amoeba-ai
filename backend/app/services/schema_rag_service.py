import os
import json
import re
from typing import Dict, Any, List
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.schema_metadata import SchemaMetadata
from app.models.client_config import ClientConfig
from app.tools.database import execute_sql_query

async def get_relevant_schemas(query: str, client_id: int, session: AsyncSession) -> List[str]:
    """Retrieve the top 3 relevant table schemas for a given natural language query using pgvector."""
    try:
        from langchain_openai import OpenAIEmbeddings
        embedder = OpenAIEmbeddings(model="text-embedding-3-small")
        query_vec = await embedder.aembed_query(query)
    except Exception as e:
        print(f"Warning: Failed to load embedder for schema RAG: {e}")
        return []

    try:
        # Perform cosine similarity search on SchemaMetadata
        # The `<=>` operator is cosine distance in pgvector. Distance ASC = Similarity DESC
        stmt = select(SchemaMetadata).where(SchemaMetadata.client_id == client_id)\
            .order_by(SchemaMetadata.embedding.cosine_distance(query_vec))\
            .limit(3)
            
        res = await session.execute(stmt)
        schemas = res.scalars().all()
        
        return [s.schema_definition for s in schemas if s.schema_definition]
    except Exception as e:
        print(f"Warning: Vector search failed: {e}")
        return []

async def query_legacy_db_with_schema(user_query: str, target_table: str, client_id: int, session: AsyncSession) -> Dict[str, Any]:
    """
    Uses Schema RAG to accurately translate a natural language query into a raw SQL query.
    1. Grabs schema context via Vector Search
    2. Asks LLM to generate SQL using that exact schema
    3. Executes the SQL safely
    """
    if not os.getenv("OPENAI_API_KEY"):
        raise Exception("OpenAI API Key required for Schema RAG Engine.")
        
    client_config = await session.get(ClientConfig, client_id)
    if not client_config:
        raise Exception("Client config not found.")

    # 1. Get Schema Context
    schema_definitions = []
    if client_config.governance_mode != "strict":
        schema_definitions = await get_relevant_schemas(user_query, client_id, session)
    # 1.5 Get Codebase Semantic Mappings
    from app.models.semantic_mapping import SemanticMapping
    import re
    semantics_res = await session.execute(select(SemanticMapping).where(SemanticMapping.client_id == client_id))
    semantics = semantics_res.scalars().all()
    
    semantic_context = ""
    semantic_tables = []
    active_semantics = []
    if semantics:
        query_lower = user_query.lower()
        stop_words = {
            "list", "show", "get", "fetch", "find", "the", "all", "me", "from", "in", "of", "to", "for", 
            "please", "can", "you", "a", "an", "records", "data", "details", "total", "count", "sum", 
            "number", "how", "many", "much", "want", "just", "no", "yes", "i", "entries", "rows"
        }
        query_tokens = set(re.findall(r'[a-zA-Z0-9_]+', query_lower)) - stop_words
        
        scored_semantics = []
        for s in semantics:
            label_lower = s.ui_label.lower()
            label_tokens = set(re.findall(r'[a-zA-Z0-9_]+', label_lower)) - stop_words
            
            score = 0
            if label_lower in query_lower:
                score += 15 + len(label_lower)
            elif query_lower in label_lower:
                score += 8
                
            overlap = query_tokens.intersection(label_tokens)
            if overlap:
                score += len(overlap) * 5
                
            # Tab affinity bonus
            if ("pending" in query_lower and "pending" in label_lower) or ("completed" in query_lower and "completed" in label_lower):
                score += 20
            elif ("pending" in query_lower and "completed" in label_lower) or ("completed" in query_lower and "pending" in label_lower):
                score -= 30
                
            # Report vs History/Attendance/Log discriminator
            if "report" in query_lower and "report" in label_lower:
                score += 25
            elif "report" in query_lower and any(k in label_lower for k in ["history", "log", "attendance", "logs"]):
                score -= 35
            elif any(k in query_lower for k in ["history", "log", "attendance", "logs"]) and any(k in label_lower for k in ["history", "log", "attendance", "logs"]):
                score += 25
            elif any(k in query_lower for k in ["history", "log", "attendance", "logs"]) and "report" in label_lower:
                score -= 35
                
            if score > 0:
                scored_semantics.append((score, s))
                
        scored_semantics.sort(key=lambda x: x[0], reverse=True)
        active_semantics = [s for _, s in scored_semantics[:6]]
        
        # If we have a definitive target_table, ensure its semantic mapping is prioritized
        if target_table:
            target_sm = next((s for s in semantics if s.database_table == target_table), None)
            if target_sm:
                active_semantics = [s for s in active_semantics if s.database_table != target_table]
                active_semantics.insert(0, target_sm)
        
        if active_semantics:
            # Pre-fetch all known schema table names for validation
            all_schema_res = await session.execute(select(SchemaMetadata.table_name).where(SchemaMetadata.client_id == client_id))
            known_tables = set(r[0].lower() for r in all_schema_res.all() if r[0])
            
            table_filters = {}
            semantic_context = "CODEBASE SEMANTIC MAPPINGS (USE THESE TO MAP UI TERMS TO TABLES):\n"
            for s in active_semantics:
                # Validate: Only include mappings whose tables actually exist in the DB schema
                if known_tables and s.database_table.lower() not in known_tables:
                    print(f"⚠️ [SCHEMA RAG] Skipping semantic mapping '{s.ui_label}' -> '{s.database_table}' (table not found in schema)")
                    continue
                    
                cols_str = ""
                if s.ui_columns:
                    filter_match = re.search(r'\[Filter:\s*(.*?)\]', s.ui_columns)
                    if filter_match:
                        clean_cols = s.ui_columns[:filter_match.start()].rstrip(" ,;")
                        cols_part = f" (Displayed Columns: {clean_cols})" if clean_cols else ""
                        cols_str = f"{cols_part}"
                    else:
                        cols_str = f" (Displayed Columns: {s.ui_columns})"
                        
                extra_parts = []
                
                # Structural Filter Enforcement: We track the filter but DO NOT tell the LLM about it. 
                # We structurally wrap it at execution time.
                if s.default_filter:
                    table_filters[s.database_table] = s.default_filter
                    # NOTE: We intentionally do NOT append it to extra_parts as a prompt hint anymore.
                    
                if s.required_joins:
                    extra_parts.append(f"[Mandatory Joins: {s.required_joins}]")
                if s.base_query:
                    extra_parts.append(f"[Controller Base Query Template: {s.base_query}]")
                
                if extra_parts:
                    cols_str += " " + " ".join(extra_parts)
                    
                semantic_context += f"- UI Term: '{s.ui_label}' is stored in table -> '{s.database_table}'{cols_str}\n"
                semantic_tables.append(s.database_table)
                
    # 1.6 Get Enum Mappings from SemanticMetadata
    from app.models.semantic_metadata import SemanticMetadata
    enum_res = await session.execute(
        select(SemanticMetadata).where(
            SemanticMetadata.client_id == client_id, 
            SemanticMetadata.enum_mappings != None
        )
    )
    enum_metadata = enum_res.scalars().all()
    
    if enum_metadata:
        semantic_context += "\nENUM MAPPINGS (USE THESE TO CONVERT INTEGERS TO STRINGS VIA 'CASE WHEN' OR 'IF'):\n"
        for em in enum_metadata:
            if em.enum_mappings:
                map_str = ", ".join([f"{k}='{v}'" for k, v in em.enum_mappings.items()])
                semantic_context += f"- Table '{em.table_name}', Column '{em.column_name}': {map_str}\n"

    # 1.7 Field-Level App Concept Mapping (Virtual Field Dictionary)
    from app.models.field_metadata import FieldMetadata
    field_res = await session.execute(
        select(FieldMetadata).where(
            FieldMetadata.client_id == client_id,
            FieldMetadata.label != None,
            FieldMetadata.label != ""
        )
    )
    field_metadata = field_res.scalars().all()
    
    # 1.8 Fetch Synonyms for Field Mappings
    sm_res = await session.execute(
        select(SemanticMetadata).where(
            SemanticMetadata.client_id == client_id,
            SemanticMetadata.synonyms != None
        )
    )
    semantic_metadata = sm_res.scalars().all()
    synonym_map = {(sm.table_name, sm.column_name): sm.synonyms for sm in semantic_metadata}

    if field_metadata:
        semantic_context += "\nFIELD MAPPINGS FOR APP CONCEPTS (CRITICAL: Use these EXACT physical columns for these business terms):\n"
        for fm in field_metadata:
            syns = synonym_map.get((fm.table_name, fm.column_name), [])
            syn_str = f" (Synonyms: {', '.join(syns)})" if syns else ""
            semantic_context += f"- Table '{fm.table_name}': UI Term \"{fm.label}\"{syn_str} -> Physical Column `{fm.column_name}`\n"

    # Inject Amoeba Auto-Discovered / Explicitly Approved Relationships (Critical for legacy PHP apps without physical DB Foreign Keys)
    from app.services.relationship_service import get_relationship_graph
    rel_graph = await get_relationship_graph(session, client_id)
    if rel_graph:
        semantic_context += "\nAMOEBA CONFIGURED RELATIONSHIPS (USE THESE FOR JOINS):\n"
        for table_a, rels in rel_graph.items():
            for table_b, meta in rels.items():
                if meta.get("direction") == "forward":
                    semantic_context += f"- {table_a}.{meta['local_column']} = {table_b}.{meta['remote_column']}\n"
            
    # Force include target_table and semantic_tables in the schema context so the AI isn't blind
    tables_to_force = set(semantic_tables)
    if target_table:
        if client_config.governance_mode == "strict":
            # In strict mode, allow target_table if it's explicitly mapped OR configured in AllowedRelationship
            from app.models.semantic_mapping import SemanticMapping
            from app.models.allowed_relationship import AllowedRelationship
            from sqlalchemy import or_

            sm_stmt = select(SemanticMapping).where(
                SemanticMapping.client_id == client_id,
                SemanticMapping.database_table == target_table
            )
            is_mapped = (await session.execute(sm_stmt)).scalars().first()

            rel_stmt = select(AllowedRelationship).where(
                AllowedRelationship.client_id == client_id,
                AllowedRelationship.is_enabled == True,
                AllowedRelationship.is_restricted == False,
                or_(
                    AllowedRelationship.parent_table == target_table,
                    AllowedRelationship.child_table == target_table
                )
            )
            matching_rels = (await session.execute(rel_stmt)).scalars().all()

            if is_mapped or matching_rels:
                tables_to_force.add(target_table)
                for r in matching_rels:
                    tables_to_force.add(r.parent_table)
                    tables_to_force.add(r.child_table)
            else:
                print(f"⚠️ STRICT MODE: Skipping intent table '{target_table}' because it has no explicit SemanticMapping or AllowedRelationship.")
        else:
            tables_to_force.add(target_table)
        
    # We will fetch ALL schema definitions for this client to give the LLM full visibility for JOINs.
    from sqlmodel import col
    all_res = await session.execute(
        select(SchemaMetadata).where(SchemaMetadata.client_id == client_id)
    )
    all_schemas = all_res.scalars().all()
    
    # We prioritize semantic and RAG tables at the top, but include all others.
    prioritized_schemas = []
    other_schemas = []
    
    for fs in all_schemas:
        if fs.table_name in tables_to_force or fs.schema_definition in schema_definitions:
            if fs.schema_definition not in prioritized_schemas:
                prioritized_schemas.append(fs.schema_definition)
        else:
            other_schemas.append(fs.schema_definition)
            
    if client_config.governance_mode == "strict":
        schema_context = "\n\n".join(prioritized_schemas)
        if not prioritized_schemas:
            # Fast-fail if nothing is explicitly mapped in strict mode
            return {
                "generated_sql": "",
                "records": [{"Error": "This table is not configured yet. Please map it manually in the Admin Panel."}],
                "thought_process": "Strict mode is enabled and no explicit SemanticMappings were found for this intent. Fast-failing.",
                "user_message": "This table is not configured yet. Please map it manually in the Admin Panel.",
                "display_title": target_table or "Unknown"
            }
    else:
        schema_context = "\n\n".join(prioritized_schemas + other_schemas)

    # 2. Build LLM Prompt
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import SystemMessage, HumanMessage
    
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    
    system_prompt = f"""You are an expert SQL Data Analyst for a MySQL/MariaDB database.
    Your job is to convert the user's natural language question into a VALID, READ-ONLY raw SQL query.

    CRITICAL RULES:
    1. You must ONLY output a raw SQL query. Do not output markdown code blocks (no ```sql). Do not explain your answer.
    2. You MUST use the exact table and column names provided in the Schema Context below.
    3. Do NOT guess column names. If you don't know a column, use SELECT * or COUNT(*).
    4. You must output your thought process in a <thought> block before the SQL query. Evaluate which tables match the user's query, check their Row Counts, and check the Semantic Mappings. After the </thought> block, output ONLY the SELECT statement.
    5. The system guessed they are asking about this table: '{target_table}'. HOWEVER, this guess is often wrong. You must evaluate the Row Counts and Semantic Mappings to find the true table.
    6. Always add a LIMIT 100 to the query to prevent massive payloads.
    7. **CODEBASE SEMANTIC MAPPINGS (PRIMARY GUIDE)**:
        - Prioritize the table listed in the 'CODEBASE SEMANTIC MAPPINGS' below.
        - CRITICAL DISAMBIGUATION (COLUMN & ROW CHECK): If a mapped table has 0 rows in the Schema Context and lacks the columns matching the user's query or Displayed Columns, while another table in the Schema Context representing the same entity contains those exact matching columns and active rows (Row Count > 0), you MUST query that active entity table!
        - Use the Displayed Columns listed in the mapping to guide which columns to include in your SELECT clause.
        - NEVER switch to an entirely unrelated business entity (e.g. never query purchase orders when the user asks for quotations, sales, or customers).
    8. **MULTI-TABLE DEDUCTION**: If there are multiple candidate tables for a UI Term (e.g. parent vs child tables), choose the main parent table (usually without `_detail`, `_item`, or `_history`) that represents the business entity and has active rows.
    9. **AUTOMATIC JOINS FOR READABILITY (CRITICAL)**: Users do not want to see raw IDs (like `customer_id`, `employee_id`, `city_id`). If the table you select has foreign key IDs, you MUST use LEFT JOINs to connect to the related tables (e.g., `customer`, `employee`, `city`) and select their readable names (e.g., `customer.name AS customer_name`). Never return raw IDs if a joined readable name is available.
    10. **CONTROLLER QUERY & DEFAULT FILTERS (CRITICAL - HIGHEST PRIORITY)**:
        - If a semantic mapping specifies a '[Controller Base Query Template: <sql>]':
          * You MUST base your SQL on that exact driving table, mandatory JOINs, and WHERE clause structure. This represents the exact query executed by the ERP controller for this screen!
        - If a semantic mapping specifies '[Required Default Filter: <condition>]' (such as `eh.enquiry_status_id = 2 AND eh.log_status = 1`, `po.status = 1`, or `gh.status = 1`):
          * You MUST include that condition in your WHERE clause.
          * If the user specifies additional constraints in their question (e.g., date range, customer name, keyword), append them as additional AND conditions. NEVER omit or bypass the Required Default Filter!
        - If a semantic mapping specifies '[Mandatory Joins: <joins>]' or if the filter references joined tables (such as `gh` for `grn_header` or `c` for `customer`):
          * Ensure you include the appropriate LEFT JOIN so the filter and readable display columns can be evaluated.
        - This rule ensures 200% exact alignment with the ERP frontend web screen and eliminates discrepancies between raw database rows and custom workflow screens.
    11. **COLUMN SELECTION**: Do NOT use `SELECT *` or `SELECT main_table.*`. You MUST explicitly list all relevant columns from the primary table to ensure no data is lost. HOWEVER, you MUST EXCLUDE the original raw `_id` columns (like `customer_id`) and replace them entirely with your joined readable columns (like `customer.name AS customer`). The final output must look perfectly clean to a non-technical user.
    12. **UNDERSTANDING USER INTENT**: The user's query refers to business entities or UI screens (such as "GRN Inspection", "Purchase Orders", "Quotations"). DO NOT treat the entity name as a column name! Query the matching table and select its primary displayed columns. Never output apologies about missing columns for the main entity name.
    13. **ENUM/STATUS MAPPING**: If a table has an integer column named `status` or `type`, DO NOT return raw numbers like 0 or 1. You MUST use a SQL CASE statement to map them to readable text. Use standard ERP conventions: For `status`, 1='Active', 0='Inactive'. For `type`, map 1='Standard', 0='Custom' or similar. Example: `CASE WHEN status = 1 THEN 'Active' ELSE 'Inactive' END AS status`.
    14. **ALWAYS OUTPUT A SELECT STATEMENT**: You must ALWAYS generate a complete, valid SELECT query. NEVER refuse to write a query and NEVER output messages claiming no data exists. Let the database execute the query.
    15. **WORKFLOW LIFECYCLE & STATUS AWARENESS (UNIVERSAL ACROSS ALL MODULES)**:
        - When a user asks for 'Pending', 'Active', 'Draft', 'Approved', 'Completed', 'Cancelled', or 'Closed' records for ANY business entity (such as Quotations, Sales Orders, Purchase Orders, Invoices, Delivery Challans, Payments, or Inspections):
          * Check the ENUM MAPPINGS and CODEBASE SEMANTIC MAPPINGS for the corresponding status column (e.g. `status`, `approval_status`, `order_status_id`, `state`).
          * If the user asks for 'Pending' records of an entity that progresses into a downstream receiving or approval stage: ensure completed records (e.g. status=2 or companion receiving note status=2) are excluded, and only active/pending records (status=1 or downstream status IS NULL / 1) are returned.
          * If the user asks for 'Completed' or 'Approved' records: match the status value indicating completion (e.g. status=2 or approval_status=1).
          * If the user asks for 'Draft' records: match status=0 or draft status.
          * If the user asks for 'Cancelled' or 'Inactive' records: match status=0 or cancelled status.
    16. **STAGE-BASED WORKFLOWS VS COMPLETED TRANSACTION TABLES**:
        - In manufacturing/pipeline ERPs, pending stages (such as Pending Invoices, Pending Jobcards, Pending Delivery) exist in the driving pipeline header (`enquiry_header`, `order_header`) with stage IDs (`eh.enquiry_status_id = 9`). They do NOT yet exist in the downstream final table (`invoice_header`).
        - If the query specifies 'Pending' or matches a stage filter, you MUST query the driving pipeline header table. You MUST NEVER switch to the completed transaction table (`invoice_header`)!
        - Only query tables that actually exist in the schema. NEVER invent joins to non-existent columns (e.g. do not join customer to menu_master).
    17. **APP CONCEPTS & FIELD MAPPINGS (CRITICAL)**:
        - The user will ask questions using friendly business terms (e.g., "Quotation Value", "Customer Name", "Status").
        - You MUST look at the `FIELD MAPPINGS FOR APP CONCEPTS` block below. This dictionary provides the exact mapping from the user's friendly term to the exact physical column in the database (e.g. `Quotation Value` -> `amount`).
        - If a user asks for a business term that is mapped in the FIELD MAPPINGS block, you MUST use the corresponding physical column in your SELECT, WHERE, and JOIN clauses.
        - NEVER blindly guess physical column names for business terms if a mapping exists.
        - If the user uses a business term that is NOT in the FIELD MAPPINGS block but refers to an obvious standard column (like `created_at` for dates), you may use it. But for custom fields, rely on the dictionary.

    {semantic_context}

    SCHEMA CONTEXT FOR THIS DATABASE:
    {schema_context}
    """
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_query)
    ]
    
    # 3. Generate SQL
    response = await llm.ainvoke(messages)
    raw_content = response.content.strip()
    
    # Extract thought block and message block for debugging/UI
    thought_process = ""
    user_message = ""
    sql_query = raw_content
    
    if "<message>" in sql_query and "</message>" in sql_query:
        parts = sql_query.split("</message>")
        user_message = parts[0].replace("<message>", "").strip()
        sql_query = parts[1].strip()
        
    if "<thought>" in sql_query and "</thought>" in sql_query:
        parts = sql_query.split("</thought>")
        thought_process = parts[0].replace("<thought>", "").strip()
        sql_query = parts[1].strip()
        print(f"🧠 [SCHEMA RAG THOUGHT]: {thought_process}")
    
    # Clean up markdown formatting
    if sql_query.startswith("```sql"):
        sql_query = sql_query.replace("```sql", "").strip()
    if sql_query.startswith("```"):
        sql_query = sql_query.replace("```", "").strip()
    if sql_query.endswith("```"):
        sql_query = sql_query[:-3].strip()
        
    print(f"🧠 [SCHEMA RAG] Generated SQL: {sql_query}")
    
    # 4. Execute SQL
    records = []
    if sql_query:
        # Security: Ensure it's a SELECT query
        if not sql_query.lower().startswith("select"):
             raise Exception("Generated query was not a SELECT statement. Operation blocked.")
             
        try:
            from app.core.context import current_db_url
            token = current_db_url.set(client_config.db_connection_url)
            try:
                records = await execute_sql_query(sql_query, table_filters=table_filters)
            finally:
                current_db_url.reset(token)
                
            if isinstance(records, str) and "Error" in records:
                print(f"Schema RAG execution failed: {records}")
                records = []
        except Exception as e:
            raise Exception(f"Failed to execute AI-generated SQL: {str(e)}")
            
        # Self-Healing Fallback: If query returned 0 records, check if WHERE clause was overly restrictive
        if not records and "WHERE" in sql_query.upper():
            print("⚠️ [SCHEMA RAG] Query returned 0 records. Attempting self-healing fallback...")
            fallback_prompt = f"""The previous query returned 0 records:
{sql_query}

User Question: {user_query}

CRITICAL RULES FOR RETRY:
1. Check if the WHERE clause was overly restrictive (for example, filtering on an unneeded status or specific value) and relax it if appropriate for the entity being queried.
2. If the user's requested entity genuinely has 0 records in the database, output 'SELECT 1 WHERE 1=0' so the system accurately reports no records found.
3. NEVER switch to an entirely different or unrelated business entity (for example, NEVER return purchase orders when asked for quotations, and NEVER return sales when asked for vendors).
Write a valid SELECT query for the requested entity, or 'SELECT 1 WHERE 1=0' if no records exist. Output ONLY the raw SELECT statement."""
            try:
                fb_messages = [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=fallback_prompt)
                ]
                fb_resp = await llm.ainvoke(fb_messages)
                fb_sql = fb_resp.content.strip()
                if "<thought>" in fb_sql and "</thought>" in fb_sql:
                    fb_sql = fb_sql.split("</thought>")[1].strip()
                if fb_sql.startswith("```sql"): fb_sql = fb_sql.replace("```sql", "").strip()
                if fb_sql.startswith("```"): fb_sql = fb_sql.replace("```", "").strip()
                if fb_sql.endswith("```"): fb_sql = fb_sql[:-3].strip()
                
                if fb_sql.lower().startswith("select") and fb_sql != sql_query:
                    print(f"🧠 [SCHEMA RAG] Retrying with alternative SQL: {fb_sql}")
                    token = current_db_url.set(client_config.db_connection_url)
                    try:
                        fb_records = await execute_sql_query(fb_sql, table_filters=table_filters)
                    finally:
                        current_db_url.reset(token)
                        
                    if fb_records and not (isinstance(fb_records, str) and "Error" in fb_records):
                        print(f"🎉 [SCHEMA RAG] Self-healing succeeded with {len(fb_records)} records!")
                        records = fb_records
                        sql_query = fb_sql
            except Exception as fb_err:
                print(f"Self-healing fallback error: {fb_err}")
            
    # Determine clean UI displayed title (never db table name)
    top_ui_label = None
    if active_semantics:
        top_ui_label = active_semantics[0].ui_label
    elif semantics and target_table:
        matching_sm = next((s for s in semantics if s.database_table == target_table), None)
        if matching_sm:
            top_ui_label = matching_sm.ui_label
    if not top_ui_label and target_table:
        top_ui_label = target_table.replace("_", " ").title()

    return {
        "generated_sql": sql_query,
        "records": records,
        "thought_process": thought_process,
        "user_message": user_message,
        "display_title": top_ui_label
    }
