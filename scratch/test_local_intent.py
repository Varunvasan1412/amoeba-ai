import re

NON_ENTITY_WORDS = {
    "list", "lists", "view", "views", "show", "get", "fetch", "display", "all", "table", "data", "records",
    "row", "rows", "screen", "screens", "page", "pages", "menu", "menus", "tab", "tabs", "details", "detail", "item", "items",
    "the", "a", "an", "and", "or", "to", "for", "in", "of", "on", "with", "me", "please",
    "want", "you", "i", "need", "can", "would", "like"
}

def _stem_token(token: str) -> str:
    """Universal singularization for English nouns matching navigation.py."""
    t = token.lower().strip()
    if len(t) <= 3:
        return t
    if t.endswith("ies") and len(t) > 4:
        return t[:-3] + "y"
    if t.endswith("ses") or t.endswith("xes") or t.endswith("shes") or t.endswith("ches"):
        return t[:-2]
    if t.endswith("s") and not t.endswith("ss"):
        return t[:-1]
    return t

class DummySM:
    def __init__(self, label, tbl, tab_grp):
        self.ui_label = label
        self.database_table = tbl
        self.default_filter = None
        self.tab_group = tab_grp

sm_all = [
    DummySM("Pending Invoice List", "enquiry_header", "Invoices"),
    DummySM("Completed Invoice List", "invoice_header", "Invoices"),
    DummySM("Payroll Report", "employee", "Payroll"),
    DummySM("Payroll History Details", "attendance_header", "Payroll"),
]

def test_intent(query):
    norm_query = query.strip().lower()
    clean_q = norm_query.replace("_", " ").lower()
    q_toks = set(re.findall(r'[a-zA-Z0-9]+', clean_q)) - NON_ENTITY_WORDS
    stemmed_q_toks = {_stem_token(t) for t in q_toks}
    
    TAB_DISCRIMINATORS = {
        "pending", "completed", "complete", "active", "inactive", "converted", 
        "open", "closed", "approved", "rejected", "cancelled", "draft", "tax",
        "report", "reports", "history", "log", "logs", "attendance", "summary",
        "details", "detail"
    }
    has_tab_discriminator = any(td in clean_q.split() for td in TAB_DISCRIMINATORS)
    
    tab_groups = {}
    for sm in sm_all:
        grp = getattr(sm, "tab_group", None)
        if grp:
            tab_groups.setdefault(grp, []).append(sm)
            
    matched_group = None
    matched_tabs = []
    for grp, grp_sms in tab_groups.items():
        grp_lower = grp.lower().strip()
        grp_core_toks = set(re.findall(r'[a-zA-Z0-9]+', grp_lower)) - NON_ENTITY_WORDS
        stemmed_grp_toks = {_stem_token(t) for t in grp_core_toks}
        
        is_group_match = False
        if grp_lower in clean_q or _stem_token(grp_lower) in clean_q:
            is_group_match = True
        elif stemmed_grp_toks and (stemmed_grp_toks.issubset(stemmed_q_toks) or stemmed_q_toks.issubset(stemmed_grp_toks)):
            is_group_match = True
            
        if is_group_match:
            views_map = {}
            for s in grp_sms:
                view_key = (s.database_table, s.default_filter or "")
                clean_lbl = s.ui_label.strip()
                if view_key not in views_map:
                    views_map[view_key] = clean_lbl
                else:
                    existing = views_map[view_key]
                    if "list" in existing.lower() and "list" not in clean_lbl.lower():
                        views_map[view_key] = clean_lbl

            unique_tabs = list(views_map.values())
            unique_tabs.sort(key=lambda t: 0 if any(k in t.lower() for k in ["pending", "draft", "new", "create"]) else (1 if any(k in t.lower() for k in ["complete", "closed", "approved"]) else 2))
            
            is_tab_specified = False
            for tab_lbl in unique_tabs:
                tab_lbl_clean = tab_lbl.lower().strip()
                if tab_lbl_clean in clean_q:
                    is_tab_specified = True
                    break
                tab_tokens = set(re.findall(r'[a-zA-Z0-9]+', tab_lbl_clean)) - NON_ENTITY_WORDS
                stemmed_tab_tokens = {_stem_token(t) for t in tab_tokens} - stemmed_grp_toks
                if stemmed_tab_tokens and stemmed_tab_tokens.intersection(stemmed_q_toks):
                    is_tab_specified = True
                    break
                    
            if not is_tab_specified:
                matched_group = grp
                matched_tabs = unique_tabs
                print(f"[{query}] -> DISAMBIGUATION for {matched_group}: {matched_tabs}")
                return "tab_disambiguation"
            else:
                print(f"[{query}] -> DIRECT EXECUTION (Tab specified)")
                return "direct_tab"
                
    print(f"[{query}] -> NO GROUP MATCH")
    return "strategy_0a"

print("\nRunning verification:")
test_intent("List invoices")
test_intent("I want you to list the invoice list table")
test_intent("List pending invoices")
test_intent("List completed invoices")
test_intent("List the payroll report")
test_intent("List the payroll history")
test_intent("List the payroll")
