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
2. YOU MUST ONLY OUTPUT VALID JSON.
3. Your output will be executed by a backend pipeline. Do not include markdown, explanations, or any text other than the JSON itself.
4. FOR CREATE OPERATIONS: NEVER invent or infer values for required fields. If the user did not provide a value for a required field, DO NOT invent a default. Omit it from the JSON output so the backend can properly prompt the user.

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
  "fields": {{
    // Map the user's requested values to the EXACT physical column_name here.
    // For CREATE, include all required fields.
    // For UPDATE, only include the fields that are being changed.
    // For DELETE, omit this key or pass an empty object.
  }}
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
2. DO NOT include markdown formatting, explanations, or any text other than the JSON itself.
3. You may ONLY use the keys listed under AVAILABLE FIELDS below. If the user mentions a field not in this list, DO NOT include it in the filter.
4. Your output will be used to construct a WHERE clause to identify the correct record to {action}.

TARGET ENVIRONMENT:
Action: {action}
App Concept: {concept}
Physical Table: {table_name}

AVAILABLE FIELDS:
{fields_info}

JSON SCHEMA TO FOLLOW:
{{
  // Example for "Update John's email": {{"name": {{"op": "ilike", "value": "John"}}}}
  // Example for "Delete quotation 123": {{"id": 123}}
  // Use simple key-value for exact match, or dict for operators (op: ilike, like, contains, =, etc.)
}}

USER REQUEST:
"{user_query}"

OUTPUT ONLY THE JSON OBJECT.
"""
    return prompt
