def get_crud_generation_prompt(action: str, table_name: str, concept: str, user_query: str, field_metadata: list, record_id: int = None, record_data: dict = None) -> str:
    """
    Generates the system prompt to convert a natural language request into a strict CrudOperation JSON.
    """
    
    fields_info = ""
    for f in field_metadata:
        fields_info += f"- {f['column_name']} (Type: {f['data_type']}"
        if f.get('is_required'):
            fields_info += ", Required"
        if f.get('synonyms'):
            fields_info += f", Synonyms: {', '.join(f['synonyms'])}"
        fields_info += ")\n"

    record_context = ""
    if action in ["UPDATE", "DELETE"] and record_id is not None:
        record_context = f"\nTARGET RECORD ID: {record_id}\n"
        if record_data:
            record_context += f"CURRENT RECORD DATA:\n{record_data}\n"

    prompt = f"""You are Amoeba AI, an ERP backend data modification generator.
Your sole job is to translate a natural language request into a strict JSON object that conforms to the CrudOperation schema.

CRITICAL RULES:
1. YOU MUST NEVER GENERATE EXECUTABLE SQL.
2. YOU MUST ONLY OUTPUT VALID JSON. Do NOT include markdown code fences, comments, or explanations.
3. FOR CREATE OPERATIONS: Map any user-provided field values to their physical column names in "fields". If the user did not provide any field values (e.g. "create quotation"), leave "fields" as an empty object: {{}}.
4. FOR UPDATE OPERATIONS: Only include the fields that are being changed.
5. FOR DELETE OPERATIONS: Omit "fields" or leave as {{}}.
6. NEVER invent or hallucinate field values.

TARGET ENVIRONMENT:
Action: {action}
App Concept: {concept}
Physical Table: {table_name}
{record_context}

AVAILABLE FIELDS:
{fields_info}

JSON SCHEMA TO FOLLOW:
{{
  "action": "{action}",
  "table": "{table_name}",
  "record_id": {record_id if record_id is not None else "null"},
  "fields": {{}}
}}

USER REQUEST:
"{user_query}"

OUTPUT ONLY THE JSON OBJECT.
"""
    return prompt

def get_crud_filter_extraction_prompt(action: str, table_name: str, concept: str, user_query: str, field_metadata: list) -> str:
    """
    Generates the system prompt to extract search filters for a target record (UPDATE/DELETE).
    Only semantic fields allowed by FieldMetadata should be used.
    """
    fields_info = ""
    for f in field_metadata:
        # Only allow filtering on fields that are mapped
        fields_info += f"- {f['column_name']} (Type: {f['data_type']}"
        if f.get('synonyms'):
            fields_info += f", Synonyms: {', '.join(f['synonyms'])}"
        fields_info += ")\n"

    prompt = f"""You are Amoeba AI, an ERP backend data filter generator.
Your sole job is to translate a natural language {action} request into a JSON object containing the exact search filters needed to find the target record.

CRITICAL RULES:
1. YOU MUST ONLY OUTPUT VALID JSON.
2. DO NOT include markdown formatting, explanations, comments, or any text other than the JSON itself.
3. You may ONLY use the keys listed under AVAILABLE FIELDS below. If the user mentions a field not in this list, DO NOT include it in the filter.
4. If no specific record filters can be identified from the request, output an empty JSON object: {{}}

TARGET ENVIRONMENT:
Action: {action}
App Concept: {concept}
Physical Table: {table_name}

AVAILABLE FIELDS:
{fields_info}

EXAMPLE JSON OUTPUTS:
Exact match: {{"name": "John"}}
Match by ID: {{"id": 123}}

USER REQUEST:
"{user_query}"

OUTPUT ONLY THE JSON OBJECT.
"""
    return prompt
