import re

def test_logic(query_lower, table_names):
    detected_intent = None
    INTENT_MAP = {
        "create": ["add", "create", "new", "insert", "post", "make"],
    }
    for intent, keywords in INTENT_MAP.items():
        for kw in keywords:
            if re.search(rf"\b{kw}\b", query_lower):
                detected_intent = intent
                break
    
    detected_entity = None
    for table_name in table_names:
        t_name = table_name.lower()
        # Strategy A Match
        if re.search(rf"\b{t_name}\b", query_lower) or re.search(rf"\b{t_name.rstrip('s')}\b", query_lower):
            detected_entity = table_name
            break
            
    print(f"Query: '{query_lower}' | Intent: {detected_intent} | Entity: {detected_entity}")
    return detected_intent, detected_entity

test_logic("add customer", ["customers"])
test_logic("add customers", ["customers"])
test_logic("create a new customer", ["customers"])
test_logic("add customer", ["customer"])
test_logic("add customers", ["customer"])
