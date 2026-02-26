import json
import os
from typing import List, Optional, Dict, Tuple, Any

SITEMAP_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "external_sitemap.json")

# Global Cache
_SITEMAP_CACHE = None

def load_sitemap(refresh: bool = False) -> List[dict]:
    """
    Loads the sitemap from disk or cache.
    Args:
        refresh (bool): If True, forces reload from disk.
    """
    global _SITEMAP_CACHE
    
    if _SITEMAP_CACHE is not None and not refresh:
        return _SITEMAP_CACHE
        
    try:
        if not os.path.exists(SITEMAP_PATH):
            _SITEMAP_CACHE = []
            return []
            
        with open(SITEMAP_PATH, "r") as f:
            _SITEMAP_CACHE = json.load(f)
            print(f"🗺️  [Navigation] Sitemap loaded into memory ({len(_SITEMAP_CACHE)} routes).")
            return _SITEMAP_CACHE
            
    except Exception as e:
        print(f"[ERROR] Error loading sitemap: {e}")
        return []

def _infer_parents_from_path(path: str) -> List[str]:
    """
    Extracts explicit parents from URL path if 'parents' key is missing.
    Example: .../transaction/invoice -> ['Transaction', 'Invoice']
    Example: .../transaction/invoice_completed -> ['Transaction', 'Invoice', 'Completed']
    """
    # Normalize path separators
    path = path.replace("\\", "/")
    parts = path.split('/')
    
    # Filter out common prefixes or empty strings
    ignored = {'localhost', 'http:', 'https:', 'varun_sterling', 'sterling_company', 'application', 'controllers'}
    
    parents = []
    for p in parts:
        clean = p.strip()
        if not clean or clean.lower() in ignored or clean.isdigit():
            continue
            
        # HANDLE UNDERSCORES IN FILENAMES (CRITICAL FIX)
        # e.g., "jobcard_pending" -> ["Jobcard", "Pending"]
        if "_" in clean:
            sub_parts = clean.split("_")
            for sp in sub_parts:
                if sp and not sp.isdigit():
                    parents.append(sp.capitalize())
        else:
            parents.append(clean.capitalize())
    
    # The last element is usually the file/page itself, but in the context of "parents", 
    # we usually want the hierarchy leading UP to it. 
    # However, for display logic "Transaction -> Invoice -> Completed", including the file name as a parent 
    # helps if the label is generic like "Completed".
    # For now, let's keep all segments as potential context.
    
    return parents

def fast_lookup_route(query: str) -> Tuple[Optional[str], Optional[List[dict]]]:
    """
    Deterministic In-Memory Lookup for Navigation Fast-Path.
    
    Returns:
        (path, None): Single, confident match.
        (None, candidates_list): Ambiguous matches (List of FULL route objects).
        (None, None): No match.
    """
    routes = load_sitemap()
    query_tokens = set(query.lower().strip().split())
    
    # ---------------------------------------------------------
    # 0. PRE-PROCESS: Ensure parents exist (Shim for legacy data)
    # ---------------------------------------------------------
    processed_routes = []
    for r in routes:
        r_mod = r.copy()
        if "parents" not in r_mod:
            r_mod["parents"] = _infer_parents_from_path(r_mod["path"])
        processed_routes.append(r_mod)

    # ---------------------------------------------------------
    # 1. EXACT LABEL MATCH (Highest Priority)
    # ---------------------------------------------------------
    exact_matches = []
    for r in processed_routes:
        if r["label"].lower() == query.lower().strip():
            exact_matches.append(r)
    
    if len(exact_matches) == 1:
        return exact_matches[0]["path"], None # Single match
        
    if len(exact_matches) > 1:
        # Deep ambiguity (Same label, different path) -> Return FULL objects
        return None, exact_matches

    # ---------------------------------------------------------
    # 2. TOKEN-BASED COMPOUND MATCH (Order-Independent)
    #    Score = (Matched Label Tokens) + (Matched Parent Tokens)
    # ---------------------------------------------------------
    scored_candidates = []
    
    for r in processed_routes:
        label_tokens = set(r["label"].lower().split())
        parent_tokens = set(p.lower() for p in r["parents"])
        
        # We want to match ALL query tokens against the union of (Label + Parents)
        doc_tokens = label_tokens.union(parent_tokens)
        
        # Check if ALL query tokens are present in the doc_tokens
        if query_tokens.issubset(doc_tokens):
            # Prioritize matches where the Label is involved (avoid matching only parents)
            label_overlap = len(query_tokens.intersection(label_tokens))
            score = 100 + label_overlap
            scored_candidates.append((score, r))

    # Sort by score desc
    scored_candidates.sort(key=lambda x: x[0], reverse=True)
    
    # Filter top tier
    if scored_candidates:
        best_score = scored_candidates[0][0]
        # Keep all with the best score
        best_matches = [item[1] for item in scored_candidates if item[0] == best_score]
        
        if len(best_matches) == 1:
            return best_matches[0]["path"], None
        else:
            return None, best_matches

    # ---------------------------------------------------------
    # 3. SUBSTRING/FUZZY FALLBACK (Lower Priority)
    # ---------------------------------------------------------
    substring_matches = []
    for r in processed_routes:
        if query.lower() in r["label"].lower():
            substring_matches.append(r)
            
    if len(substring_matches) == 1:
        return substring_matches[0]["path"], None
    if len(substring_matches) > 1:
        return None, substring_matches # Ambiguous substring
        
    return None, None


def lookup_external_route(query: str) -> str:
    """
    Legacy/Tool Dictionary Search (Used by LLM as fallback).
    Searches the sitemap for a route matching the query.
    Returns a string describing the match or suggestions.
    """
    routes = load_sitemap()
    query = query.lower().strip()
    
    # 1. Exact Name/Label Match
    for route in routes:
        if route["label"].lower() == query:
            return json.dumps([route])
            
    # 2. Scored Matching
    scored_matches = []
    query_parts = set(query.split())
    
    for route in routes:
        label = route["label"].lower()
        label_parts = set(label.split())
        
        score = 0
        
        # A. Containment (High Score)
        if query in label: score += 50
        if label in query: score += 50
        
        # B. Exact Word Overlap
        intersection = query_parts.intersection(label_parts)
        score += len(intersection) * 10
        
        # C. Keyword Match
        for kw in route.get("keywords", []):
            if kw == query: score += 30
            elif kw in query: score += 10
            
        if score > 0:
            scored_matches.append({"route": route, "score": score})

    # 3. Fuzzy Match (Difflib) - Fallback
    import difflib
    all_labels = [r["label"] for r in routes]
    fuzzy_results = difflib.get_close_matches(query, all_labels, n=3, cutoff=0.6)
    
    for fuzzy_label in fuzzy_results:
        found = False
        for sm in scored_matches:
            if sm["route"]["label"] == fuzzy_label:
                found = True
                break
        if not found:
             for r in routes:
                 if r["label"] == fuzzy_label:
                     scored_matches.append({"route": r, "score": 5}) 
    
    # Sort by Score DESC
    scored_matches.sort(key=lambda x: x["score"], reverse=True)
    final_matches = [m["route"] for m in scored_matches[:10]]
    
    if not final_matches:
        return "No route found."
        
    return json.dumps(final_matches)

def add_external_route(label: str, path: str, keywords: List[str] = []) -> str:
    """Adds a new route to the sitemap."""
    routes = load_sitemap() # Gets cache
    
    # Check duplicate
    updated = False
    for r in routes:
        if r["label"].lower() == label.lower():
            r["path"] = path 
            if keywords: r["keywords"] = keywords
            updated = True
            break
            
    if not updated:
        new_route = {
            "label": label,
            "path": path,
            "keywords": keywords if keywords else [label.lower()]
        }
        routes.append(new_route)
    
    # Write to Disk
    try:
        with open(SITEMAP_PATH, "w") as f:
            json.dump(routes, f, indent=4)
        
        # Update Cache
        global _SITEMAP_CACHE
        _SITEMAP_CACHE = routes
        
        action = "Updated" if updated else "Added"
        return f"{action} route '{label}' pointing to {path}"
    except Exception as e:
        return f"Error saving route: {e}"

def batch_learn_routes(new_routes: List[dict]) -> str:
    """
    Bulk adds routes. 
    Input: [{"label": "Home", "path": "/"}, ...]
    """
    routes = load_sitemap()
    existing_labels = {r["label"].lower(): r for r in routes}
    
    count = 0
    for item in new_routes:
        label = item.get("label", "").strip()
        path = item.get("path", "").strip()
        
        if not label or not path or len(label) < 2: 
            continue
        if "javascript:" in path or path == "#" or "void(0)" in path:
            continue
            
        if label.lower() in existing_labels:
            existing_labels[label.lower()]["path"] = path
        else:
            routes.append({
                "label": label,
                "path": path,
                "keywords": [label.lower()]
            })
            count += 1
            
    try:
        with open(SITEMAP_PATH, "w") as f:
            json.dump(routes, f, indent=4)
        
        global _SITEMAP_CACHE
        _SITEMAP_CACHE = routes
        
        return f"Learned {count} new routes."
    except Exception as e:
        return f"Error saving routes: {e}"
