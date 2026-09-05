import os
import json
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
    schema_definitions = await get_relevant_schemas(user_query, client_id, session)
    # 1.5 Get Codebase Semantic Mappings
    from app.models.semantic_mapping import SemanticMapping
    semantics_res = await session.execute(select(SemanticMapping).where(SemanticMapping.client_id == client_id))
    semantics = semantics_res.scalars().all()
    
    semantic_context = ""
    semantic_tables = []
    if semantics:
        query_lower = user_query.lower()
        active_semantics = [s for s in semantics if s.ui_label.lower() in query_lower]
        
        if active_semantics:
            semantic_context = "CODEBASE SEMANTIC MAPPINGS (USE THESE TO MAP UI TERMS TO TABLES):\n"
            for s in active_semantics:
                semantic_context += f"- UI Term: '{s.ui_label}' is stored in table -> '{s.database_table}' (Found in {s.source_file})\n"
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
            # em.enum_mappings is a dict like {"1": "Active", "0": "Inactive"}
            map_str = ", ".join([f"{k}='{v}'" for k, v in em.enum_mappings.items()])
            semantic_context += f"- Table '{em.table_name}', Column '{em.column_name}': {map_str}\n"
            
    # Force include target_table and semantic_tables in the schema context so the AI isn't blind
    tables_to_force = set(semantic_tables)
    if target_table:
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
    7. **ABSOLUTE RULE**: If a table is listed in the 'CODEBASE SEMANTIC MAPPINGS' below, you MUST use that table instead of the guessed table.
    8. **ABSOLUTE RULE**: If there are multiple semantic mappings for a UI Term, you must logically deduce the primary main table (e.g. usually the one without '_detail' or the one that represents the core object) and query that table.
    9. **AUTOMATIC JOINS FOR READABILITY (CRITICAL)**: Users do not want to see raw IDs (like `customer_id`, `employee_id`, `city_id`). If the table you select has foreign key IDs, you MUST use LEFT JOINs to connect to the related tables (e.g., `customer`, `employee`, `city`) and select their readable names (e.g., `customer.name AS customer_name`). Never return raw IDs if a joined readable name is available.
    10. **COLUMN SELECTION**: Do NOT use `SELECT *` or `SELECT main_table.*`. You MUST explicitly list all relevant columns from the primary table to ensure no data is lost. HOWEVER, you MUST EXCLUDE the original raw `_id` columns (like `customer_id`) and replace them entirely with your joined readable columns (like `customer.name AS customer`). The final output must look perfectly clean to a non-technical user.
    11. **MISSING DATA**: If the user specifically asks for a column (like "date", "status", etc) but that column physically DOES NOT EXIST in the schema for the table you are querying, you MUST output a brief apology inside a <message> block before the <thought> block. Example: <message>I cannot show the date because the Bank table does not have a date column.</message>
    12. **ENUM/STATUS MAPPING**: If a table has an integer column named `status` or `type`, DO NOT return raw numbers like 0 or 1. You MUST use a SQL CASE statement to map them to readable text. Use standard ERP conventions: For `status`, 1='Active', 0='Inactive'. For `type`, map 1='Standard', 0='Custom' or similar. Example: `CASE WHEN status = 1 THEN 'Active' ELSE 'Inactive' END AS status`.

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
            # execute_sql_query uses the global connection in the current tool, 
            # but we should temporarily set it to the client's DB url if it's tenant-aware
            from app.core.context import current_db_url
            token = current_db_url.set(client_config.db_connection_url)
            try:
                records = await execute_sql_query(sql_query)
            finally:
                current_db_url.reset(token)
                
            if isinstance(records, str) and "Error" in records:
                print(f"Schema RAG execution failed: {records}")
                records = []
        except Exception as e:
            raise Exception(f"Failed to execute AI-generated SQL: {str(e)}")
            
    return {
        "generated_sql": sql_query,
        "records": records,
        "thought_process": thought_process,
        "user_message": user_message
    }
