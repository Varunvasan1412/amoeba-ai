import re, json, urllib.request, os

url = "https://amoeba.space/api/semantic/debug?api_key=am_live_1iorVmBSbL3STz7UqFBO6BvUDUpaLUrfULNuUXuWHjA&search=invoice"
req = urllib.request.Request(url, headers={'User-Agent': 'M'})
data = json.loads(urllib.request.urlopen(req).read().decode())

class SM:
    def __init__(self, d):
        self.ui_label = d.get("ui_label", "")
        self.tab_group = d.get("tab_group")
        self.database_table = d.get("database_table", "")
        self.default_filter = d.get("default_filter")

sm_all = [SM(d) for d in data['matches']]

NON_ENTITY_WORDS = {
    "list", "show", "get", "fetch", "all", "the", "me", "view", "display",
    "see", "find", "open", "read", "details", "detail", "data", "records",
    "record", "information", "info", "items", "item", "rows", "row"
}

TAB_DISCRIMINATORS = {
    "pending", "completed", "complete", "active", "inactive", "converted", 
    "open", "closed", "approved", "rejected", "cancelled", "draft", "tax",
    "report", "reports", "history", "log", "logs", "attendance", "summary"
}

INTERNAL_ACTION_WORDS = {
    "save", "delete", "remove", "update", "insert", "create", "add", "edit",
    "json", "ajax", "data", "fetch", "get", "search", "export", "import",
    "upload", "download", "print", "pdf", "excel", "csv", "entry",
    "salary", "stage", "action", "process", "submit", "approve", "reject",
    "convert", "generate", "calculate", "compute", "validate", "check",
    "byid", "bybrand", "bydate", "byname", "bypass", "detail", "details"
}

def simple_title_case(s: str) -> str:
    if not s:
        return ""
    s = os.path.splitext(s)[0]
    s = s.replace("_", " ").replace("-", " ")
    s = re.sub(r'\[.*?\]', 'Detail', s)
    return s.title().strip()

def _stem_token(word: str) -> str:
    w = word.lower()
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("es") and len(w) > 3:
        return w[:-2]
    if w.endswith("s") and len(w) > 2 and not w.endswith("ss"):
        return w[:-1]
    if w.endswith("ing") and len(w) > 4:
        return w[:-3]
    if w.endswith("ed") and len(w) > 3:
        return w[:-2]
    return w

def _is_ui_facing_label(label: str) -> bool:
    if not label:
        return False
    lbl_lower = label.lower().strip()
    lbl_words = set(re.findall(r'[a-zA-Z0-9]+', lbl_lower))
    if lbl_words.intersection(INTERNAL_ACTION_WORDS):
        return False
    return True

clean_q = "invoice"
q_toks = set(re.findall(r'[a-zA-Z0-9]+', clean_q)) - NON_ENTITY_WORDS
stemmed_q_toks = {_stem_token(t) for t in q_toks}

print("Testing query:", clean_q)

# Strategy A test:
candidate_tabs = []
seen_labels = set()
for sm in sm_all:
    if not _is_ui_facing_label(sm.ui_label):
        continue
    lbl_clean = sm.ui_label.lower().strip()
    base_tokens = set(re.findall(r'[a-zA-Z0-9]+', lbl_clean)) - TAB_DISCRIMINATORS - NON_ENTITY_WORDS
    stemmed_base = {_stem_token(t) for t in base_tokens}
    if stemmed_base and (stemmed_base.issubset(stemmed_q_toks) or stemmed_q_toks.issubset(stemmed_base)):
        if any(td in lbl_clean for td in TAB_DISCRIMINATORS):
            if sm.ui_label.strip() not in seen_labels:
                seen_labels.add(sm.ui_label.strip())
                candidate_tabs.append(sm.ui_label.strip())

print("Strategy A candidates before counterpart check:", candidate_tabs)

if len(candidate_tabs) == 1:
    for sm in sm_all:
        if not _is_ui_facing_label(sm.ui_label):
            continue
        lbl_clean = sm.ui_label.lower().strip()
        base_tokens = set(re.findall(r'[a-zA-Z0-9]+', lbl_clean)) - NON_ENTITY_WORDS
        stemmed_base = {_stem_token(t) for t in base_tokens}
        if stemmed_base and (stemmed_base == stemmed_q_toks):
            if not any(td in lbl_clean for td in TAB_DISCRIMINATORS):
                if sm.ui_label.strip() not in seen_labels:
                    seen_labels.add(sm.ui_label.strip())
                    candidate_tabs.append(sm.ui_label.strip())
                    break

print("Strategy A candidates after counterpart check:", candidate_tabs)

filtered_cand = []
seen_cand_keys = set()
for c in candidate_tabs:
    c_words = [w for w in c.lower().split() if w in TAB_DISCRIMINATORS]
    c_key = tuple(sorted(c_words)) if c_words else c.lower()
    if c_key not in seen_cand_keys:
        seen_cand_keys.add(c_key)
        filtered_cand.append(c)

filtered_cand.sort(key=lambda t: 1 if any(k in t.lower() for k in ["complete", "closed", "approved"]) else 0)
matched_group = simple_title_case(clean_q) or "this screen"

print(f"Result -> Group: '{matched_group}', Tabs: {filtered_cand}")
