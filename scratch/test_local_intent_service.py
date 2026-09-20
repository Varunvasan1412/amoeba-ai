import sys, urllib.request, json
from unittest.mock import MagicMock, AsyncMock

# 1. Fetch live production semantic mappings for invoices
url = "https://amoeba.space/api/semantic/debug?api_key=am_live_1iorVmBSbL3STz7UqFBO6BvUDUpaLUrfULNuUXuWHjA&search=invoice"
req = urllib.request.Request(url, headers={'User-Agent': 'M'})
data = json.loads(urllib.request.urlopen(req).read().decode())
print(f"Loaded {len(data['matches'])} production invoice mappings.")

class MockSM:
    def __init__(self, d):
        self.ui_label = d.get("ui_label", "")
        self.tab_group = d.get("tab_group")
        self.database_table = d.get("database_table", "")
        self.default_filter = d.get("default_filter")

mock_sms = [MockSM(d) for d in data['matches']]

# Test the exact intent service logic
from app.services.intent_service import (
    TAB_DISCRIMINATORS, NON_ENTITY_WORDS, _stem_token,
    _is_ui_facing_label, simple_title_case
)
import re

def simulate_tab_disambiguation(query):
    query_lower = query.lower().strip()
    clean_q = query_lower
    for w in ["list", "table", "tables", "records", "data", "show", "view", "get"]:
        clean_q = re.sub(rf"\b{w}\b", "", clean_q).strip()
    
    clean_q = clean_q.replace("_", " ").lower()
    q_toks = set(re.findall(r'[a-zA-Z0-9]+', clean_q)) - NON_ENTITY_WORDS
    stemmed_q_toks = {_stem_token(t) for t in q_toks}
    
    has_tab_discriminator = any(td in clean_q.split() for td in TAB_DISCRIMINATORS)
    print(f"Query: '{query}' -> clean_q='{clean_q}', stemmed_q_toks={stemmed_q_toks}, has_disc={has_tab_discriminator}")
    
    if has_tab_discriminator:
        return "BYPASS_DISAMBIGUATION (tab already specified in query)"
        
    candidate_tabs = []
    seen_labels = set()
    for sm in mock_sms:
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

    if len(candidate_tabs) == 1:
        for sm in mock_sms:
            if not _is_ui_facing_label(sm.ui_label):
                continue
            lbl_clean = sm.ui_label.lower().strip()
            base_tokens = set(re.findall(r'[a-zA-Z0-9]+', lbl_clean)) - NON_ENTITY_WORDS
            stemmed_base = {_stem_token(t) for t in base_tokens}
            if stemmed_base and (stemmed_base == stemmed_q_toks):
                if not any(td in lbl_clean for td in TAB_DISCRIMINATORS):
                    clean_lbl = sm.ui_label.strip()
                    if clean_lbl not in seen_labels:
                        if "list" in clean_lbl.lower() or not any("list" in c.lower() for c in candidate_tabs):
                            seen_labels.add(clean_lbl)
                            candidate_tabs.append(clean_lbl)
                            break

    if len(candidate_tabs) >= 2:
        filtered_cand = []
        seen_cand_keys = set()
        for c in candidate_tabs:
            c_words = [w for w in c.lower().split() if w in TAB_DISCRIMINATORS]
            c_key = tuple(sorted(c_words)) if c_words else c.lower()
            if c_key not in seen_cand_keys:
                seen_cand_keys.add(c_key)
                filtered_cand.append(c)
                
        filtered_cand.sort(key=lambda t: 1 if any(k in t.lower() for k in ["complete", "closed", "approved"]) else 0)
        matched_group = simple_title_case(clean_q.replace("show", "").replace("list", "").replace("me", "").replace("the", "").strip()) or "this screen"
        return {
            "intent": "tab_disambiguation",
            "screen": matched_group,
            "tabs": [{"label": t} for t in filtered_cand]
        }
    return None

res1 = simulate_tab_disambiguation("List invoices")
print("RESULT for 'List invoices':", json.dumps(res1, indent=2))

res2 = simulate_tab_disambiguation("Show completed invoices")
print("RESULT for 'Show completed invoices':", res2)
