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
        semantic_context = "CODEBASE SEMANTIC MAPPINGS (USE THESE TO MAP UI TERMS TO TABLES):\n"
        for s in semantics:
            semantic_context += f"- UI Term: '{s.ui_label}' is stored in table -> '{s.database_table}' (Found in {s.source_file})\n"
            semantic_tables.append(s.database_table)
            
    # Force include target_table and semantic_tables in the schema context so the AI isn't blind
    tables_to_force = set(semantic_tables)
    if target_table:
        tables_to_force.add(target_table)
        
    if tables_to_force:
        from sqlmodel import col
        force_res = await session.execute(
            select(SchemaMetadata).where(
                SchemaMetadata.client_id == client_id,
                col(SchemaMetadata.table_name).in_(tables_to_force)
            )
        )
        force_schemas = force_res.scalars().all()
        for fs in force_schemas:
            if fs.schema_definition not in schema_definitions:
                schema_definitions.append(fs.schema_definition)
                
    schema_context = "\n\n".join(schema_definitions)

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
    4. Only return SELECT statements. Never INSERT, UPDATE, DROP, etc.
    5. The primary table they are asking about is likely: {target_table}
    6. Always add a LIMIT 100 to the query to prevent massive payloads, unless they are asking for a single aggregate value.
    7. WARNING: If you find multiple tables that might match, ALWAYS prefer the table that has a Row Count > 0. Ignore tables with Row Count: 0 as they are empty/abandoned.

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
    sql_query = response.content.strip()
    
    # Clean up markdown formatting if the LLM ignored instructions
    if sql_query.startswith("```sql"):
        sql_query = sql_query.replace("```sql", "").replace("```", "").strip()
    if sql_query.startswith("```"):
        sql_query = sql_query.replace("```", "").strip()
        
    print(f"🧠 [SCHEMA RAG] Generated SQL: {sql_query}")
    
    # 4. Execute SQL
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
            raise Exception(records)
            
        return {
            "records": records,
            "generated_sql": sql_query
        }
    except Exception as e:
        raise Exception(f"Failed to execute AI-generated SQL: {str(e)}")
