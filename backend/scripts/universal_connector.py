import os
import re
import json
import sys
import ssl
import urllib.request
import urllib.parse
from urllib.parse import urljoin, urlparse
from urllib.error import URLError
from collections import Counter, defaultdict
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

# =========================================================================
# 🧠 AMOEBA FULLSTACK MVC & SPA CONNECTOR AGENT v3.0
# =========================================================================
# Bridges the gap between Frontend UI Screens and Backend Database Queries.
# Supports: CodeIgniter, Laravel, Django, Express, Next.js, React, Vue, PHP
# =========================================================================

DEFAULT_AMOEBA_HOST = os.environ.get("AMOEBA_HOST", "https://amoeba.space").rstrip("/")
IGNORE_DIRS = {
    '.git', 'node_modules', 'vendor', '__pycache__', 'dist', 'build', '.next', 
    'coverage', '.venv', 'venv', 'cache', 'logs', 'assets', 'plugins'
}

SQL_STOP_WORDS = {
    'select', 'where', 'order', 'group', 'limit', 'dual', 'set', 'this', 'and', 'or',
    'left', 'right', 'inner', 'outer', 'join', 'from', 'into', 'table', 'update', 'delete',
    'insert', 'values', 'having', 'like', 'in', 'is', 'null', 'not', 'as', 'on', 'by',
    'the', 'for', 'to', 'at', 'with', 'id', 'view', 'data', 'db', 'true', 'false', 'all',
    'distinct', 'case', 'when', 'then', 'else', 'end', 'count', 'sum', 'avg', 'min', 'max',
    'between', 'exists', 'any', 'some', 'union', 'desc', 'asc', 'primary', 'key', 'status',
    'path', 'href', 'url', 'class', 'type', 'echo', 'return', 'public', 'private', 'function'
}

def simple_title_case(s):
    """Converts 'user-profile' or 'user_profile' to 'User Profile'"""
    s = os.path.splitext(s)[0]
    s = s.replace("_", " ").replace("-", " ")
    s = re.sub(r'\[.*?\]', 'Detail', s)
    return s.title()

def clean_ui_text(text):
    """Cleans up raw HTML/PHP strings into readable UI labels."""
    if not text: return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'<\?php.*?\?>', '', text, flags=re.DOTALL)
    text = re.sub(r'<\?=.*?\?>', '', text, flags=re.DOTALL)
    text = re.sub(r'\{\{.*?\}\}', '', text)
    text = re.sub(r'[\r\n\t]+', ' ', text).strip()
    return text

def detect_framework(root_path):
    """Detects the framework used in the client codebase."""
    if os.path.exists(os.path.join(root_path, 'next.config.js')) or os.path.exists(os.path.join(root_path, 'next.config.mjs')):
        return "NEXTJS"
    if os.path.exists(os.path.join(root_path, 'artisan')):
        return "LARAVEL"
    if os.path.exists(os.path.join(root_path, 'application', 'config', 'config.php')):
        return "CODEIGNITER"
    if os.path.exists(os.path.join(root_path, 'composer.json')):
        return "PHP_MVC"
    if os.path.exists(os.path.join(root_path, 'package.json')):
        return "JS_SPA"
    return "LEGACY_PHP_HTML"

# =========================================================================
# 1. ROUTE SCANNER
# =========================================================================

def scan_nextjs_routes(root_path, base_url):
    print("⚡ Scanning Next.js Routes...")
    routes = []
    target_dirs = ['pages', 'app', 'src/pages', 'src/app']
    for relative_dir in target_dirs:
        scan_dir = os.path.join(root_path, relative_dir)
        if not os.path.exists(scan_dir): continue
        for subdir, dirs, files in os.walk(scan_dir):
            for file in files:
                if file.startswith('_') or file.startswith('.'): continue
                if not file.endswith(('.js', '.jsx', '.ts', '.tsx')): continue
                full_path = os.path.join(subdir, file)
                rel_from_pages = os.path.relpath(full_path, scan_dir)
                route_path = os.path.splitext(rel_from_pages)[0]
                if route_path.endswith('index'): route_path = route_path[:-5]
                route_path = route_path.replace("\\", "/")
                if not route_path.startswith('/'): route_path = '/' + route_path
                label = simple_title_case(os.path.basename(file))
                if not label: label = "Home"
                full_url = urllib.parse.urljoin(base_url, route_path)
                routes.append({
                    "label": label,
                    "path": full_url,
                    "keywords": label.lower().split() + ["nextjs"]
                })
    return routes

def scan_generic_spa_routes(root_path, base_url):
    print("⚛️  Scanning SPA Router definitions...")
    routes = []
    seen_paths = set()
    router_regex = re.compile(r"""path\s*[:=]\s*["']([^"']+)["']""", re.IGNORECASE)
    for subdir, dirs, files in os.walk(root_path):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for file in files:
            if not file.endswith(('.js', '.jsx', '.ts', '.tsx', '.vue')): continue
            try:
                with open(os.path.join(subdir, file), 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    matches = router_regex.findall(content)
                    for match in matches:
                        if match.startswith('/') and match not in seen_paths:
                            label = simple_title_case(match.split('/')[-1])
                            if not label: label = "Home"
                            full_url = urllib.parse.urljoin(base_url, match)
                            routes.append({
                                "label": label,
                                "path": full_url,
                                "keywords": label.lower().split()
                            })
                            seen_paths.add(match)
            except Exception: pass
    return routes

def scan_php_mvc_routes(root_path, base_url):
    print("🐘 Scanning PHP / MVC Controllers and Routes...")
    routes = []
    seen_paths = set()
    
    # 1. Look for controllers and their public methods
    for subdir, dirs, files in os.walk(root_path):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for file in files:
            if not file.lower().endswith('.php'): continue
            rel_path = os.path.relpath(os.path.join(subdir, file), root_path).replace('\\', '/')
            
            if 'controllers' in subdir.lower() or 'controller' in file.lower():
                try:
                    with open(os.path.join(subdir, file), 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    controller_name = os.path.splitext(file)[0].lower()
                    methods = re.findall(r'public\s+function\s+([a-zA-Z0-9_]+)\s*\(', content)
                    c_lbl = simple_title_case(controller_name)
                    for m in methods:
                        if m.startswith('_') or m in ['construct', '__construct', 'get_instance']: continue
                        route_rel = f"{controller_name}/{m}"
                        full_url = urllib.parse.urljoin(base_url, route_rel)
                        if full_url not in seen_paths:
                            m_lbl = simple_title_case(m)
                            if m.lower() == 'index':
                                clean_lbl = c_lbl
                                # Also register base controller URL without /index
                                base_ctrl_url = urllib.parse.urljoin(base_url, controller_name)
                                if base_ctrl_url not in seen_paths:
                                    routes.append({
                                        "label": c_lbl,
                                        "path": base_ctrl_url,
                                        "keywords": [controller_name, c_lbl.lower()]
                                    })
                                    seen_paths.add(base_ctrl_url)
                            elif m.lower() in ['report', 'list', 'history', 'summary', 'details']:
                                clean_lbl = f"{c_lbl} {m_lbl}"
                            else:
                                clean_lbl = f"{c_lbl} {m_lbl}"

                            routes.append({
                                "label": clean_lbl,
                                "path": full_url,
                                "keywords": m_lbl.lower().split() + [controller_name, c_lbl.lower(), clean_lbl.lower()]
                            })
                            seen_paths.add(full_url)
                except Exception: pass
            elif not any(k in subdir.lower() for k in ['views', 'templates', 'models', 'libraries', 'config']):
                # Procedural script
                web_path = rel_path
                full_url = urllib.parse.urljoin(base_url, web_path)
                if full_url not in seen_paths:
                    label = simple_title_case(file)
                    routes.append({
                        "label": label,
                        "path": full_url,
                        "keywords": label.lower().split()
                    })
                    seen_paths.add(full_url)
    return routes

# =========================================================================
# 2. FULLSTACK MVC & SPA CROSS-CORRELATION SCANNER
# =========================================================================


def extract_base_query_with_ai(php_code, base_api_url, api_key):
    try:
        url = f"{base_api_url}/api/v2/semantic/extract-sql"
        data = json.dumps({"php_code": php_code}).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={
            'Content-Type': 'application/json',
            'X-API-Key': api_key,
            'User-Agent': 'AmoebaConnector/3.5'
        })
        with urllib.request.urlopen(req) as response:
            res = json.loads(response.read().decode('utf-8'))
            return res.get("base_query")
    except Exception as e:
        print(f"⚠️ AI SQL Extraction failed: {e}")
        return None

def extract_sql_filters(code_snippet):
    """
    Extracts default query WHERE filters (e.g. status = 1, is_deleted = 0)
    from PHP Active Record, Eloquent, or raw SQL inside controller/model methods.
    """
    filters = []
    # Pattern 1: ->where('col', val) or ->where("col", "val")
    for m in re.finditer(r'->where\s*\(\s*[\'"]([a-zA-Z0-9_\.]+)[\'"]\s*,\s*[\'"]?([a-zA-Z0-9_]+)[\'"]?\s*\)', code_snippet, re.IGNORECASE):
        col, val = m.group(1).strip(), m.group(2).strip()
        if not val.startswith('$') and val.lower() not in ['true', 'false', 'null']:
            filters.append(f"{col} = {val}")
        elif val.lower() in ['true', 'false', 'null']:
            filters.append(f"{col} IS {val.upper()}")

    # Pattern 1B: ->where('col !=', val) or ->where('col >', val)
    for m in re.finditer(r'->where\s*\(\s*[\'"]([a-zA-Z0-9_\.]+\s*(?:!=|<>|>|<|>=|<=))\s*[\'"]\s*,\s*[\'"]?([a-zA-Z0-9_]+)[\'"]?\s*\)', code_snippet, re.IGNORECASE):
        col_op, val = m.group(1).strip(), m.group(2).strip()
        if not val.startswith('$'):
            filters.append(f"{col_op} {val}")

    # Pattern 1C: Associative array ->where(array('po.status' => 1)) or ->where(['po.status' => 1])
    for m in re.finditer(r'[\'"]([a-zA-Z0-9_\.]+)[\'"]\s*=>\s*[\'"]?([a-zA-Z0-9_]+)[\'"]?', code_snippet):
        col, val = m.group(1).strip(), m.group(2).strip()
        if any(k in col.lower() for k in ['status', 'deleted', 'active', 'state', 'type', 'inspection']):
            if not val.startswith('$') and val.lower() not in ['true', 'false', 'null']:
                filters.append(f"{col} = {val}")
            
    # Pattern 2: ->where('col = val') or ->where("po.status = 1") or ->where("is_deleted = 0")
    for m in re.finditer(r'->where\s*\(\s*[\'"]([a-zA-Z0-9_\.]+\s*(?:=|!=|<>|IS)\s*[^$\'"]+?)[\'"]\s*\)', code_snippet, re.IGNORECASE):
        cond = m.group(1).strip()
        if not any(bad in cond for bad in ['$', '?', 'session', 'auth', 'user_id', 'branch_id']):
            filters.append(cond)
            
    # Pattern 3: Raw SQL WHERE conditions for status, active, deleted flags
    for m in re.finditer(r'\b(?:WHERE|AND)\s+([a-zA-Z0-9_\.]+\s*(?:=|!=|<>)\s*(?:[0-9]+|\'[a-zA-Z0-9_]+\'))\b', code_snippet, re.IGNORECASE):
        cond = m.group(1).strip()
        if any(k in cond.lower() for k in ['status', 'deleted', 'active', 'state', 'type', 'inspection']):
            filters.append(cond)
            
    # Pattern 4: Soft deletes ->whereNull('deleted_at')
    for m in re.finditer(r'->whereNull\s*\(\s*[\'"]([a-zA-Z0-9_\.]+)[\'"]\s*\)', code_snippet, re.IGNORECASE):
        filters.append(f"{m.group(1)} IS NULL")
        
    # Post-processing: Remove filters containing PHP variables, session data, or user-specific conditions
    FILTER_BLACKLIST = ['$', 'session', 'userdata', 'auth_user', 'user_id', 'branch_id', 'company_id', 'logged_in', 'this->', 'self::']
    unique = []
    seen = set()
    for f in filters:
        f_clean = re.sub(r'\s+', ' ', f).strip()
        if f_clean.lower() not in seen:
            if not any(bad in f_clean.lower() for bad in FILTER_BLACKLIST):
                unique.append(f_clean)
                seen.add(f_clean.lower())
    return unique

def scan_fullstack_semantics(root_path):
    """
    Cross-correlates Frontend UI Screens (Views, titles, displayed columns, multiple tabs)
    with the Backend Controllers/Models, physical Database Tables, and Default Query Filters.
    """
    print("🕵️  Executing Fullstack MVC Cross-Correlation Profiler...")
    
    # --- PHASE 1: Index Controllers, Models, Database Queries & Query Filters ---
    controller_methods = {} # key -> { tables, from_tables, views, subcalls, filters, file }
    controller_files = {}   # class_name -> { file, methods }
    
    method_regex = re.compile(r'(?:public\s+)?function\s+([a-zA-Z0-9_]+)\s*\([^)]*\)\s*\{(.*?)(?=(?:public\s+)?function|\Z)', re.DOTALL | re.IGNORECASE)
    from_table_regex = re.compile(r'(?:\$table\s*=\s*[\'"]|->(?:from|get|table)\s*\(\s*[\'"]|DB::table\s*\(\s*[\'"]|\bFROM\s+`?)([a-zA-Z0-9_]+)', re.IGNORECASE)
    table_regex = re.compile(r'(?:\$table\s*=\s*[\'"]|->(?:from|get|join|table)\s*\(\s*[\'"]|DB::table\s*\(\s*[\'"]|(?:FROM|JOIN)\s+`?)([a-zA-Z0-9_]+)', re.IGNORECASE)
    view_regex = re.compile(r'(?:load->view|view|render)\s*\(\s*[\'"]([^\'"]+)[\'"]', re.IGNORECASE)
    subcall_regex = re.compile(r'(?:->|::)([a-zA-Z0-9_]+)\s*\(', re.IGNORECASE)

    for subdir, dirs, files in os.walk(root_path):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for file in files:
            if not file.endswith(('.php', '.js', '.ts', '.py')): continue
            rel_path = os.path.relpath(os.path.join(subdir, file), root_path).replace('\\', '/')
            is_backend = any(k in rel_path.lower() for k in ['controller', 'model', 'api', 'handler', 'service'])
            
            if is_backend or 'controllers' in subdir.lower() or 'models' in subdir.lower():
                try:
                    with open(os.path.join(subdir, file), 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    class_name = os.path.splitext(file)[0].lower()
                    methods_in_file = {}
                    
                    # Extract class-level table declarations (CodeIgniter var $table, Eloquent protected $table, Django db_table)
                    class_default_tables = []
                    for prop_m in re.finditer(r'(?:var|public|protected|private)\s+\$table\s*=\s*[\'"]([a-zA-Z0-9_]+)[\'"]', content, re.IGNORECASE):
                        tbl = prop_m.group(1).lower()
                        if tbl not in SQL_STOP_WORDS and len(tbl) > 2:
                            class_default_tables.append(tbl)
                    for prop_m in re.finditer(r'\$this->table\s*=\s*[\'"]([a-zA-Z0-9_]+)[\'"]', content, re.IGNORECASE):
                        tbl = prop_m.group(1).lower()
                        if tbl not in SQL_STOP_WORDS and len(tbl) > 2:
                            class_default_tables.append(tbl)
                    for prop_m in re.finditer(r'(?:db_table|__tablename__)\s*=\s*[\'"]([a-zA-Z0-9_]+)[\'"]', content, re.IGNORECASE):
                        tbl = prop_m.group(1).lower()
                        if tbl not in SQL_STOP_WORDS and len(tbl) > 2:
                            class_default_tables.append(tbl)
                    
                    for match in method_regex.finditer(content):
                        fn_name = match.group(1).lower()
                        fn_body = match.group(2)
                        
                        raw_from = from_table_regex.findall(fn_body)
                        clean_from = [t.lower() for t in raw_from if len(t) > 2 and t.lower() not in SQL_STOP_WORDS]
                        
                        raw_tables = table_regex.findall(fn_body)
                        clean_tables = [t.lower() for t in raw_tables if len(t) > 2 and t.lower() not in SQL_STOP_WORDS]
                        
                        # If method references $this->table or is in a model with class-level table, inherit it
                        if class_default_tables:
                            if '$this->table' in fn_body or not clean_from:
                                for dt in class_default_tables:
                                    if dt not in clean_from:
                                        clean_from.append(dt)
                                    if dt not in clean_tables:
                                        clean_tables.append(dt)
                        
                        raw_joins = []
                        for j_m in re.finditer(r'->join\s*\(\s*[\'"]([a-zA-Z0-9_]+(?:\s+[a-zA-Z0-9_]+)?)[\'"]\s*,\s*[\'"]([^\'"]+)[\'"](?:\s*,\s*[\'"]([^\'"]+)[\'"])?', fn_body, re.IGNORECASE):
                            j_table = j_m.group(1).strip()
                            j_cond = j_m.group(2).strip()
                            j_type = (j_m.group(3) or 'left').strip().upper()
                            raw_joins.append(f"{j_type} JOIN {j_table} ON {j_cond}")
                        
                        raw_group_by = []
                        for g_m in re.finditer(r'->group_by\s*\(\s*[\'"]([^\'"]+)[\'"]', fn_body, re.IGNORECASE):
                            raw_group_by.append(g_m.group(1).strip())
                        for g_m in re.finditer(r'\bGROUP\s+BY\s+([^;\r\n"\']+)', fn_body, re.IGNORECASE):
                            raw_group_by.append(g_m.group(1).strip())

                        raw_order_by = []
                        for o_m in re.finditer(r'->order_by\s*\(\s*[\'"]([^\'"]+)[\'"](?:\s*,\s*[\'"]([a-zA-Z]+)[\'"])?', fn_body, re.IGNORECASE):
                            col = o_m.group(1).strip()
                            direction = (o_m.group(2) or '').strip().upper()
                            raw_order_by.append(f"{col} {direction}".strip())
                        for o_m in re.finditer(r'\bORDER\s+BY\s+([^;\r\n"\']+)', fn_body, re.IGNORECASE):
                            raw_order_by.append(o_m.group(1).strip())

                        raw_queries = []
                        for q_m in re.finditer(r'(?:->query\s*\(\s*[\'"]|\$sql\s*=\s*[\'"]|\$query\s*=\s*[\'"])\s*(SELECT\b[\s\S]*?\bFROM\b[\s\S]*?)(?:[\'"]\s*\)|[\'"];)', fn_body, re.IGNORECASE):
                            raw_q = re.sub(r'\s+', ' ', q_m.group(1)).strip()
                            if len(raw_q) > 20 and not any(bad in raw_q.lower() for bad in ['$', 'password', 'token', 'session']):
                                raw_queries.append(raw_q)

                        loaded_views = [v.replace('\\', '/').lower() for v in view_regex.findall(fn_body)]
                        subcalls = [s.lower() for s in subcall_regex.findall(fn_body)]
                        filters = extract_sql_filters(fn_body)
                        
                        methods_in_file[fn_name] = {
                            "raw_code": fn_body,
                            "tables": clean_tables,
                            "from_tables": clean_from,
                            "joins": raw_joins,
                            "group_by": raw_group_by,
                            "order_by": raw_order_by,
                            "queries": raw_queries,
                            "views": loaded_views,
                            "subcalls": subcalls,
                            "filters": filters,
                            "file": rel_path
                        }
                        
                        controller_methods[f"{class_name}/{fn_name}"] = methods_in_file[fn_name]
                        controller_methods[fn_name] = methods_in_file[fn_name]
                        
                    controller_files[class_name] = {
                        "file": rel_path,
                        "methods": methods_in_file,
                        "default_tables": class_default_tables
                    }
                except Exception: pass

    # Trace helper subcalls & propagate tables & filters (up to 3 levels deep)
    for _ in range(3):
        for fn_key, data in list(controller_methods.items()):
            for sc in data.get("subcalls", []):
                if sc in controller_methods and sc != fn_key:
                    target_data = controller_methods[sc]
                    for t in target_data.get("tables", []):
                        if t not in data["tables"]:
                            data["tables"].append(t)
                    for t in target_data.get("from_tables", []):
                        if "from_tables" not in data:
                            data["from_tables"] = []
                        if t not in data["from_tables"]:
                            data["from_tables"].append(t)
                    for f in target_data.get("filters", []):
                        if f not in data["filters"]:
                            data["filters"].append(f)
                    for j in target_data.get("joins", []):
                        if "joins" not in data:
                            data["joins"] = []
                        if j not in data["joins"]:
                            data["joins"].append(j)
                    for g in target_data.get("group_by", []):
                        if "group_by" not in data:
                            data["group_by"] = []
                        if g not in data["group_by"]:
                            data["group_by"].append(g)
                    for o in target_data.get("order_by", []):
                        if "order_by" not in data:
                            data["order_by"] = []
                        if o not in data["order_by"]:
                            data["order_by"].append(o)
                    for q in target_data.get("queries", []):
                        if "queries" not in data:
                            data["queries"] = []
                        if q not in data["queries"]:
                            data["queries"].append(q)

    print(f"📊 Indexed {len(controller_files)} backend controllers/models ({len(controller_methods)} methods).")

    # --- PHASE 2: Index Frontend Views, Headers, Multi-Tabs & AJAX Data Sources ---
    views = []
    th_regex = re.compile(r'<th[^>]*>(.*?)</th>', re.IGNORECASE | re.DOTALL)
    table_block_regex = re.compile(r'<table[^>]*>(.*?)</table>', re.IGNORECASE | re.DOTALL)
    tab_regex = re.compile(r'<(?:a|button|li)[^>]+(?:data-toggle=["\']tab["\']|role=["\']tab["\']|href=["\']#[^"\']+["\'])[^>]*>(.*?)</(?:a|button|li)>', re.IGNORECASE | re.DOTALL)
    title_regex = re.compile(r'<(?:h[1-4]|title)[^>]*>(.*?)</(?:h[1-4]|title)>|<div[^>]*class=["\'][^"\']*(?:card-title|box-title|page-title|page-header)[^"\']*["\'][^>]*>(.*?)</div>', re.IGNORECASE | re.DOTALL)

    for subdir, dirs, files in os.walk(root_path):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for file in files:
            if not file.endswith(('.php', '.html', '.blade.php', '.vue', '.jsx', '.tsx')): continue
            rel_path = os.path.relpath(os.path.join(subdir, file), root_path).replace('\\', '/')
            if any(k in rel_path.lower() for k in ['templates', 'template', 'header', 'footer', 'sidebar', 'menu']):
                continue
                
            try:
                with open(os.path.join(subdir, file), 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    
                # Extract Table Headers (filtering out index and action buttons)
                raw_headers = th_regex.findall(content)
                clean_headers = []
                for h in raw_headers:
                    ch = clean_ui_text(h)
                    if ch and len(ch) > 1 and ch.lower() not in ['s.no', 'sno', 'sl.no', 'slno', 'action', 'actions', '#', 'edit', 'delete', 'options']:
                        clean_headers.append(ch)
                        
                # Extract Table Headers per <table> block (for multi-table / multi-tab views)
                table_headers_list = []
                for tbl in table_block_regex.findall(content):
                    t_headers = []
                    for h in th_regex.findall(tbl):
                        ch = clean_ui_text(h)
                        if ch and len(ch) > 1 and ch.lower() not in ['s.no', 'sno', 'sl.no', 'slno', 'action', 'actions', '#', 'edit', 'delete', 'options']:
                            t_headers.append(ch)
                    if t_headers:
                        table_headers_list.append(t_headers[:15])

                # Extract Tab Elements (nav-tabs, tab pills)
                clean_tabs = []
                for t in tab_regex.findall(content):
                    t_clean = clean_ui_text(re.sub(r'<[^>]+>', '', t))
                    if t_clean and len(t_clean) > 2 and len(t_clean) < 50 and t_clean.lower() not in ['home', 'close', 'next', 'prev', 'menu']:
                        clean_tabs.append(t_clean)

                # Extract Screen Titles
                titles = []
                for match in title_regex.findall(content):
                    t = match[0] or match[1]
                    ct = clean_ui_text(t)
                    if ct and len(ct) > 2 and len(ct) < 60 and not ct.startswith('$') and not ct.startswith('<?'):
                        titles.append(ct)
                        
                # Extract AJAX endpoints using multi-pattern scanning
                ajax_endpoints = []
                seen_eps = set()
                
                # Pattern 1: base_url('controller/method') or site_url('controller/method')
                for c, m in re.findall(r'(?:base_url|site_url)\s*\(\s*[\'"]/?([a-zA-Z0-9_]+)/([a-zA-Z0-9_]+)[\'"]', content, re.I):
                    if c.lower() not in ['assets', 'static', 'plugins', 'css', 'js', 'images', 'vendor', 'dist']:
                        ep = f"{c.lower()}/{m.lower()}"
                        if ep not in seen_eps:
                            ajax_endpoints.append(ep)
                            seen_eps.add(ep)
                            
                # Pattern 2: url/ajax/sAjaxSource: "<?= base_url(...) ?>/controller/method" or "controller/method"
                for c, m in re.findall(r'(?:url|ajax|sAjaxSource|data-url|action)\s*(?::|=)\s*[\'"]?(?:<\?php\s+echo\s+|\<\?=\s*)?(?:base_url\([^)]*\)|site_url\([^)]*\))?[\s\.\'"]*/?([a-zA-Z0-9_]+)/([a-zA-Z0-9_]+)', content, re.I):
                    if c.lower() not in ['http', 'https', 'window', 'document', 'location', 'assets', 'static', 'plugins', 'css', 'js']:
                        ep = f"{c.lower()}/{m.lower()}"
                        if ep not in seen_eps:
                            ajax_endpoints.append(ep)
                            seen_eps.add(ep)

                # Pattern 3: Any quoted path with endpoint keywords
                for c, m in re.findall(r'[\'"]/?([a-zA-Z0-9_]+)/([a-zA-Z0-9_]*(?:json|ajax|data|list|pending|completed|datatable)[a-zA-Z0-9_]*)[\'"]', content, re.I):
                    if c.lower() not in ['http', 'https', 'assets', 'static', 'plugins', 'css', 'js', 'images', 'vendor', 'dist']:
                        ep = f"{c.lower()}/{m.lower()}"
                        if ep not in seen_eps:
                            ajax_endpoints.append(ep)
                            seen_eps.add(ep)
                    
                ui_label = titles[0] if titles else simple_title_case(file)
                view_key = os.path.splitext(rel_path)[0].lower()
                view_base = os.path.splitext(file)[0].lower()
                
                views.append({
                    "file": file,
                    "rel_path": rel_path,
                    "view_key": view_key,
                    "view_base": view_base,
                    "ui_label": ui_label,
                    "headers": clean_headers[:15],
                    "table_headers_list": table_headers_list,
                    "clean_tabs": clean_tabs,
                    "ajax_endpoints": ajax_endpoints,
                    "content": content
                })
            except Exception: pass

    print(f"📊 Indexed {len(views)} UI views/templates.")

    # --- PHASE 3: Cross-Correlate Views to Database Tables & Query Filters ---
    semantics = []
    seen = set()

    # Common ERP table name abbreviation expansions
    TABLE_ABBREVIATIONS = {
        'po': 'purchase order', 'so': 'sales order', 'se': 'sales enquiry',
        'grn': 'goods received note', 'dc': 'delivery challan', 'dn': 'delivery note',
        'inv': 'invoice', 'pi': 'purchase indent', 'pr': 'purchase request',
        'sq': 'sales quotation', 'pq': 'purchase quotation', 'rfq': 'request for quotation',
        'wo': 'work order', 'jo': 'job order', 'bom': 'bill of material',
        'hr': 'human resource', 'emp': 'employee', 'dept': 'department',
        'mr': 'material request', 'mi': 'material issue', 'qc': 'quality control',
        'qi': 'quality inspection', 'insp': 'inspection',
    }
    
    def choose_primary_table(table_list, headers=None, from_tables=None):
        if not table_list:
            return None
            
        lookup_tables = {'users', 'user', 'employee', 'branch', 'city', 'state', 'country', 'settings', 'currency', 'company', 'admin', 'auth', 'master_city', 'master_state', 'master_country'}
        
        # Priority 1: Driving tables (from_tables) that are not lookup tables
        core_from = [t for t in (from_tables or []) if t not in lookup_tables]
        core_all = [t for t in table_list if t not in lookup_tables]
        
        pool = core_from if core_from else (core_all if core_all else table_list)
        
        # Prefer header/parent tables over detail/items tables
        detail_suffixes = ['_detail', '_details', '_items', '_item', '_history', '_log', '_det', '_lines', '_line']
        header_tables = [t for t in pool if not any(t.endswith(sfx) for sfx in detail_suffixes)]
        candidate_pool = header_tables if header_tables else pool
        
        # Priority 2: Score candidate tables against UI column headers if available
        if headers:
            header_text = " ".join(headers).lower()
            header_tokens = set(re.findall(r'[a-zA-Z0-9]+', header_text))
            
            best_tbl = None
            best_score = -1
            for tbl in candidate_pool:
                tbl_clean = tbl.replace('_', ' ').lower()
                tbl_tokens = set(re.findall(r'[a-zA-Z0-9]+', tbl_clean))
                
                # Expand abbreviated table tokens (e.g. 'po' -> 'purchase order')
                expanded_tokens = set(tbl_tokens)
                for tok in list(tbl_tokens):
                    if tok in TABLE_ABBREVIATIONS:
                        expanded_tokens.update(TABLE_ABBREVIATIONS[tok].split())
                
                overlap = len(header_tokens.intersection(expanded_tokens))
                score = overlap * 15
                
                # Substring match (e.g. "purchase" or "order" in header text)
                for t in expanded_tokens:
                    if len(t) >= 4 and t in header_text:
                        score += 10
                        
                # Driving FROM table bonus
                if core_from and tbl in core_from:
                    score += 8
                    
                # Frequency bonus: tables referenced more often in the method are more likely primary
                score += table_list.count(tbl)
                
                # _head/_header suffix bonus (these are typically the primary/parent tables)
                if any(tbl.endswith(sfx) for sfx in ['_head', '_header', '_master', '_mst']):
                    score += 5
                
                if score > best_score:
                    best_score = score
                    best_tbl = tbl
                    
            if best_tbl and best_score > 0:
                return best_tbl
                
        if candidate_pool:
            return Counter(candidate_pool).most_common(1)[0][0]
        return table_list[0] if table_list else None

    for v in views:
        # Resolve companion controller for this view
        related_ctrl_methods = {}
        related_ctrl_file = None
        c_name = None
        for cn, c_info in controller_files.items():
            if cn in v["view_base"] or v["view_base"] in cn or any(cn in ep for ep in v["ajax_endpoints"]):
                related_ctrl_methods = dict(c_info["methods"])
                related_ctrl_file = c_info["file"]
                c_name = cn
                # Also merge companion model methods & tables (e.g. quotation_model for quotation)
                for comp_suffix in ['_model', 'model', '_mdl', 'mdl']:
                    comp_name = f"{cn}{comp_suffix}"
                    if comp_name in controller_files:
                        for m_name, m_data in controller_files[comp_name]["methods"].items():
                            if m_name not in related_ctrl_methods:
                                related_ctrl_methods[m_name] = m_data
                break

        handled_via_tabs = False
        primary_pending_table = None
        primary_pending_filters = None
        last_primary_table = None
        last_ui_cols = None

        def add_endpoint_entry(label_text, target_tbl, cols, src, default_filter=None, base_query=None, required_joins=None, tab_group=None):
            # HARDCODED OVERRIDE: Client 4 stores payment vouchers in expence_details
            if 'voucher' in label_text.lower() and target_tbl in ['voucher', 'payment_voucher', 'expense_master', 'expense']:
                target_tbl = 'expence_details'
                
            # HARDCODED OVERRIDE: Client 4 uses 'product' table for parts setting list view
            if 'parts setting' in label_text.lower() and target_tbl in ['product_parts_setting', 'parts_setting', 'part_setting', 'partssetting']:
                target_tbl = 'product'
                
            key = (label_text.lower(), target_tbl)
            if key not in seen and len(label_text) >= 3:
                semantics.append({
                    "ui_label": label_text,
                    "database_table": target_tbl,
                    "source_file": f"{v['rel_path']} -> {src}",
                    "ui_columns": cols,
                    "default_filter": default_filter,
                    "base_query": base_query,
                    "required_joins": required_joins,
                    "tab_group": tab_group
                })
                seen.add(key)

        # A. TAB-BASED CORRELATION (Multi-tab views: e.g. Pending Inspection vs Completed Inspection)
        if v["clean_tabs"]:
            for tab_idx, tab_name in enumerate(v["clean_tabs"]):
                tab_l = tab_name.lower()
                tab_headers = v["table_headers_list"][tab_idx] if tab_idx < len(v["table_headers_list"]) else v["headers"]
                
                # Find candidate methods from related_ctrl_methods
                candidate_matches = []
                for m_name, m_data in related_ctrl_methods.items():
                    if not m_data.get("tables"): continue
                    
                    match_score = 0
                    for kw in ['pending', 'completed', 'approved', 'rejected', 'cancelled', 'history', 'draft', 'active', 'closed', 'new', 'open']:
                        if kw in tab_l and kw in m_name:
                            match_score += 40
                            
                    table_score = 0
                    if tab_headers:
                        hdr_text = " ".join(tab_headers).lower()
                        for t in m_data.get("tables", []):
                            t_clean = t.replace('_', ' ').lower()
                            t_tokens = [tok for tok in re.findall(r'[a-zA-Z0-9]+', t_clean) if len(tok) >= 3]
                            for tok in t_tokens:
                                if tok in hdr_text:
                                    table_score += 25
                                    
                    total_score = match_score + table_score
                    if total_score > 0:
                        candidate_matches.append((total_score, m_name, m_data))
                        
                if candidate_matches:
                    candidate_matches.sort(key=lambda x: x[0], reverse=True)
                    best_score, best_m_name, best_m_data = candidate_matches[0]
                    
                    target_tbl = choose_primary_table(
                        best_m_data["tables"], 
                        headers=tab_headers, 
                        from_tables=best_m_data.get("from_tables")
                    )
                    
                    if target_tbl:
                        handled_via_tabs = True
                        last_primary_table = target_tbl
                        headers_str = ", ".join(tab_headers) if tab_headers else ""
                        filter_str = " AND ".join(best_m_data.get("filters", []))
                        tab_cols = f"{headers_str} [Filter: {filter_str}]".strip() if filter_str else (headers_str or None)
                        last_ui_cols = tab_cols
                        
                        joins_list = best_m_data.get("joins", [])
                        joins_str = " ".join(joins_list) if joins_list else None
                        if best_m_data.get("queries"):
                            base_query_str = best_m_data["queries"][0]
                        else:
                            parts = [f"SELECT * FROM {target_tbl}"]
                            if joins_str: parts.append(joins_str)
                            if filter_str: parts.append(f"WHERE {filter_str}")
                            if best_m_data.get("group_by"): parts.append(f"GROUP BY {', '.join(dict.fromkeys(best_m_data['group_by']))}")
                            if best_m_data.get("order_by"): parts.append(f"ORDER BY {', '.join(dict.fromkeys(best_m_data['order_by']))}")
                            base_query_str = " ".join(parts).strip() if (joins_str or filter_str or best_m_data.get("group_by") or best_m_data.get("order_by")) else None
                            
                            if use_ai and best_m_data.get("raw_code"):
                                print(f"🧠 Using AI to extract SQL for {best_m_name}...")
                                ai_query = extract_base_query_with_ai(best_m_data["raw_code"], amoeba_host, api_key)
                                if ai_query: base_query_str = ai_query

                        
                        source_ctrl = f"{best_m_data['file']}::{c_name}/{best_m_name}" if c_name else f"{best_m_data['file']}::{best_m_name}"
                        screen_group = v['ui_label']
                        
                        add_endpoint_entry(tab_name, target_tbl, tab_cols, source_ctrl, default_filter=filter_str or None, base_query=base_query_str, required_joins=joins_str, tab_group=screen_group)
                        add_endpoint_entry(f"{tab_name} List", target_tbl, tab_cols, source_ctrl, default_filter=filter_str or None, base_query=base_query_str, required_joins=joins_str, tab_group=screen_group)
                        if v['ui_label'].lower() not in tab_name.lower():
                            add_endpoint_entry(f"{v['ui_label']} {tab_name}", target_tbl, tab_cols, source_ctrl, default_filter=filter_str or None, base_query=base_query_str, required_joins=joins_str, tab_group=screen_group)
                            add_endpoint_entry(f"{tab_name} {v['ui_label']}", target_tbl, tab_cols, source_ctrl, default_filter=filter_str or None, base_query=base_query_str, required_joins=joins_str, tab_group=screen_group)
                            
                        # Default active tab (Pending / First tab) represents the default screen view
                        if tab_idx == 0 or 'pending' in tab_l or primary_pending_table is None:
                            primary_pending_table = target_tbl
                            primary_pending_filters = tab_cols

        # B. ENDPOINT-BASED CORRELATION (AJAX endpoints declared in scripts / DataTables)
        handled_via_endpoints = handled_via_tabs
        if v["ajax_endpoints"]:
            for idx, ep in enumerate(v["ajax_endpoints"]):
                c_data = controller_methods.get(ep)
                m_only = ep.split('/')[-1]
                if not c_data:
                    c_data = controller_methods.get(m_only)
                
                if c_data and c_data.get("tables"):
                    handled_via_endpoints = True
                    endpoint_headers = v["headers"]
                    if idx < len(v["table_headers_list"]) and v["table_headers_list"][idx]:
                        endpoint_headers = v["table_headers_list"][idx]
                        
                    primary_table = choose_primary_table(
                        c_data["tables"], 
                        headers=endpoint_headers, 
                        from_tables=c_data.get("from_tables")
                    )
                    
                    headers_str = ", ".join(endpoint_headers) if endpoint_headers else ""
                    filter_str = " AND ".join(c_data.get("filters", []))
                    ui_cols = f"{headers_str} [Filter: {filter_str}]".strip() if filter_str else (headers_str or None)
                    
                    joins_list = c_data.get("joins", [])
                    joins_str = " ".join(joins_list) if joins_list else None
                    if c_data.get("queries"):
                        base_query_str = c_data["queries"][0]
                    else:
                        parts = [f"SELECT * FROM {primary_table}"]
                        if joins_str: parts.append(joins_str)
                        if filter_str: parts.append(f"WHERE {filter_str}")
                        if c_data.get("group_by"): parts.append(f"GROUP BY {', '.join(dict.fromkeys(c_data['group_by']))}")
                        if c_data.get("order_by"): parts.append(f"ORDER BY {', '.join(dict.fromkeys(c_data['order_by']))}")
                        base_query_str = " ".join(parts).strip() if (joins_str or filter_str or c_data.get("group_by") or c_data.get("order_by")) else None
                        
                        if use_ai and c_data.get("raw_code"):
                            print(f"🧠 Using AI to extract SQL for {m_only}...")
                            ai_query = extract_base_query_with_ai(c_data["raw_code"], amoeba_host, api_key)
                            if ai_query: base_query_str = ai_query

                    
                    source_ctrl = f"{c_data['file']}::{ep}"
                    
                    clean_m = re.sub(r'(_json|_ajax|_data|_list)$', '', m_only, flags=re.IGNORECASE)
                    method_label = simple_title_case(clean_m)
                    if len(method_label) >= 3:
                        add_endpoint_entry(method_label, primary_table, ui_cols, source_ctrl, default_filter=filter_str or None, base_query=base_query_str, required_joins=joins_str)
                        add_endpoint_entry(f"{method_label} List", primary_table, ui_cols, source_ctrl, default_filter=filter_str or None, base_query=base_query_str, required_joins=joins_str)
                        if v['ui_label'].lower() not in method_label.lower():
                            add_endpoint_entry(f"{v['ui_label']} {method_label}", primary_table, ui_cols, source_ctrl, default_filter=filter_str or None, base_query=base_query_str, required_joins=joins_str)
                        
                    if not primary_pending_table:
                        primary_pending_table = primary_table
                        primary_pending_filters = ui_cols
                    last_primary_table = primary_table
                    last_ui_cols = ui_cols

        # C. Default Main View Title (e.g. "GRN Inspection" -> default tab / table)
        if handled_via_tabs or handled_via_endpoints:
            target_main_table = primary_pending_table if primary_pending_table else last_primary_table
            main_cols = primary_pending_filters if primary_pending_filters else last_ui_cols
            if target_main_table:
                add_endpoint_entry(v["ui_label"], target_main_table, main_cols, v["rel_path"])
                add_endpoint_entry(f"{v['ui_label']} List", target_main_table, main_cols, v["rel_path"])
                base_label = re.sub(r'\b(Pending|Completed|List|View|Report|Details|Master|Management|Index)\b', '', v["ui_label"], flags=re.IGNORECASE).strip()
                if base_label and base_label.lower() != v["ui_label"].lower():
                    add_endpoint_entry(base_label, target_main_table, main_cols, v["rel_path"])

        # D. Single View / Non-AJAX Fallback
        if not handled_via_tabs and not handled_via_endpoints:
            matched_tables = []
            source_controller = None
            extracted_filters = []
            extracted_joins = []
            
            for fn_key, c_data in controller_methods.items():
                for loaded_view in c_data["views"]:
                    if v["view_base"] in loaded_view or loaded_view in v["view_key"]:
                        if c_data["tables"]:
                            matched_tables.extend(c_data["tables"])
                            extracted_filters.extend(c_data.get("filters", []))
                            extracted_joins.extend(c_data.get("joins", []))
                            source_controller = f"{c_data['file']}::{fn_key}"
                            break
                if matched_tables:
                    break

            if not matched_tables:
                for cn, c_info in controller_files.items():
                    if cn in v["view_base"] or v["view_base"] in cn:
                        all_c_tables = []
                        for m in c_info["methods"].values():
                            all_c_tables.extend(m["tables"])
                            extracted_filters.extend(m.get("filters", []))
                            extracted_joins.extend(m.get("joins", []))
                        if c_info.get("default_tables"):
                            all_c_tables.extend(c_info["default_tables"])
                        # Also include companion model tables
                        for comp_suffix in ['_model', 'model', '_mdl', 'mdl']:
                            comp_name = f"{cn}{comp_suffix}"
                            if comp_name in controller_files:
                                comp_info = controller_files[comp_name]
                                for m in comp_info["methods"].values():
                                    all_c_tables.extend(m["tables"])
                                    extracted_filters.extend(m.get("filters", []))
                                    extracted_joins.extend(m.get("joins", []))
                                if comp_info.get("default_tables"):
                                    all_c_tables.extend(comp_info["default_tables"])
                        if all_c_tables:
                            matched_tables.extend(all_c_tables)
                            source_controller = c_info["file"]
                            break

            if not matched_tables:
                direct_tables = table_regex.findall(v["content"])
                clean_direct = [t.lower() for t in direct_tables if len(t) > 2 and t.lower() not in SQL_STOP_WORDS]
                if clean_direct:
                    matched_tables.extend(clean_direct)
                    extracted_filters.extend(extract_sql_filters(v["content"]))
                    source_controller = v["rel_path"]

            if matched_tables:
                primary_table = choose_primary_table(matched_tables, headers=v["headers"])
                headers_str = ", ".join(v["headers"]) if v["headers"] else ""
                filter_str = " AND ".join(list(set(extracted_filters))) if extracted_filters else ""
                joins_str = " ".join(list(set(extracted_joins))) if extracted_joins else ""
                parts = [f"SELECT * FROM {primary_table}"]
                if joins_str: parts.append(joins_str)
                if filter_str: parts.append(f"WHERE {filter_str}")
                base_query_str = " ".join(parts).strip() if (joins_str or filter_str) else None
                
                if use_ai:
                    code_to_parse = None
                    lbl = v.get("view_base", "unknown")
                    if source_controller and '::' in source_controller:
                        fn_k = source_controller.split('::')[-1]
                        if fn_k in controller_methods:
                            code_to_parse = controller_methods[fn_k].get("raw_code")
                            lbl = fn_k
                    else:
                        code_to_parse = v.get("content")
                        
                    if code_to_parse:
                        print(f"🧠 Using AI to extract SQL for Semantic View: {lbl}...")
                        ai_query = extract_base_query_with_ai(code_to_parse, amoeba_host, client_api_key)
                        if ai_query: base_query_str = ai_query

                ui_cols_str = f"{headers_str} [Filter: {filter_str}]".strip() if filter_str else (headers_str or None)
                
                def add_semantic_entry(label_text):
                    key = (label_text.lower(), primary_table)
                    if key not in seen and len(label_text) >= 3:
                        semantics.append({
                            "ui_label": label_text,
                            "database_table": primary_table,
                            "source_file": f"{v['rel_path']} -> {source_controller}" if source_controller else v["rel_path"],
                            "ui_columns": ui_cols_str,
                            "default_filter": filter_str or None,
                            "base_query": base_query_str or None,
                            "required_joins": joins_str or None
                        })
                        seen.add(key)
                
                add_semantic_entry(v["ui_label"])
                base_label = re.sub(r'\b(Pending|Completed|List|View|Report|Details|Master|Management|Index)\b', '', v["ui_label"], flags=re.IGNORECASE).strip()
                if base_label and base_label.lower() != v["ui_label"].lower():
                    add_semantic_entry(base_label)
                    
                file_label = simple_title_case(v["file"])
                if file_label.lower() not in [v["ui_label"].lower(), base_label.lower()]:
                    add_semantic_entry(file_label)

    # --- PHASE 3B: Controller Action-Driven Semantic Profiler ---
    # Many modern MVC apps (CodeIgniter, Laravel, Django, Rails) route actions directly to methods,
    # and each method executes a specific query (reports, lists, summaries, stages) and loads a view.
    # We correlate EVERY controller public action method to ensure no report or list is lost!
    for cn, c_info in controller_files.items():
        ctrl_file = c_info.get("file", "")
        methods = c_info.get("methods", {})
        
        for m_name, m_data in methods.items():
            if m_name.startswith('_') or m_name in ['construct', '__construct', 'get_instance']:
                continue
            
            action_tables = m_data.get("tables", [])
            action_from = m_data.get("from_tables", [])
            if not action_tables and c_info.get("default_tables"):
                action_tables = list(c_info["default_tables"])
                
            if not action_tables:
                continue
                
            method_views = m_data.get("views", [])
            matched_view = None
            for v in views:
                for mv in method_views:
                    if mv in v["view_key"] or v["view_base"] in mv or mv.replace('/', '_') in v["view_base"]:
                        matched_view = v
                        break
                if matched_view:
                    break
                    
            if not matched_view:
                for v in views:
                    if v["view_base"] == m_name or v["view_base"] == f"{cn}_{m_name}" or v["view_base"] == f"{cn}/{m_name}":
                        matched_view = v
                        break
                        
            v_headers = matched_view.get("headers", []) if matched_view else []
            v_title = matched_view.get("ui_label") if matched_view else None
            
            target_tbl = choose_primary_table(action_tables, headers=v_headers, from_tables=action_from)
            if not target_tbl:
                continue
                
            headers_str = ", ".join(v_headers) if v_headers else ""
            filters_list = m_data.get("filters", [])
            filter_str = " AND ".join(dict.fromkeys(filters_list)) if filters_list else ""
            ui_cols_str = f"{headers_str} [Filter: {filter_str}]".strip() if filter_str else (headers_str or None)
            
            joins_list = m_data.get("joins", [])
            joins_str = " ".join(dict.fromkeys(joins_list)) if joins_list else ""
            group_by_list = m_data.get("group_by", [])
            order_by_list = m_data.get("order_by", [])
            
            if m_data.get("queries"):
                base_query_str = m_data["queries"][0]
            else:
                parts = [f"SELECT * FROM {target_tbl}"]
                if joins_str: parts.append(joins_str)
                if filter_str: parts.append(f"WHERE {filter_str}")
                if group_by_list: parts.append(f"GROUP BY {', '.join(dict.fromkeys(group_by_list))}")
                if order_by_list: parts.append(f"ORDER BY {', '.join(dict.fromkeys(order_by_list))}")
                base_query_str = " ".join(parts).strip() if (joins_str or filter_str or group_by_list or order_by_list) else None
                if use_ai and m_data.get("raw_code"):
                    print(f"🧠 Using AI to extract SQL for Node route...")
                    ai_query = extract_base_query_with_ai(m_data["raw_code"], amoeba_host, client_api_key)
                    if ai_query: base_query_str = ai_query

                
            ctrl_label = simple_title_case(cn)
            m_label = simple_title_case(m_name)
            source_spec = f"{ctrl_file}::{cn}/{m_name}"
            
            action_labels = []
            if v_title and len(v_title) > 2 and v_title.lower() not in ['home', 'index', 'view']:
                action_labels.append(v_title)
                
            combined_label = f"{ctrl_label} {m_label}".strip()
            action_labels.append(combined_label)
            if m_label.lower() not in ['index', 'list', 'main', 'view', 'data']:
                action_labels.append(m_label)
                if not any(m_label.lower().endswith(sfx) for sfx in ['list', 'report', 'details', 'log', 'logs', 'history']):
                    action_labels.append(f"{m_label} List")
                    action_labels.append(f"{combined_label} List")
            elif m_label.lower() in ['index', 'list']:
                action_labels.append(f"{ctrl_label} List")
                
            tab_group_name = ctrl_label
            
            for al in action_labels:
                key = (al.lower(), target_tbl)
                if key not in seen and len(al) >= 3:
                    semantics.append({
                        "ui_label": al,
                        "database_table": target_tbl,
                        "source_file": source_spec,
                        "ui_columns": ui_cols_str,
                        "default_filter": filter_str or None,
                        "base_query": base_query_str or None,
                        "required_joins": joins_str or None,
                        "tab_group": tab_group_name
                    })
                    seen.add(key)

    print(f"🧠 Correlated {len(semantics)} Fullstack UI-to-Database Semantic Mappings!")
    return semantics

# =========================================================================
# 3. ENUM SCANNER (<select> inputs & CASE WHEN mappings)
# =========================================================================

def scan_codebase_for_enums(root_path):
    print("🕵️  Profiling codebase for automated Enum mappings (<select> tags & CASE statements)...")
    enums = {} # table_name -> column_name -> {val: label}
    
    select_regex = re.compile(r'<select[^>]*name=["\']([^"\']+)["\'][^>]*>(.*?)</select>', re.IGNORECASE | re.DOTALL)
    option_regex = re.compile(r'<option[^>]*value=["\']([^"\']+)["\'][^>]*>(.*?)</option>', re.IGNORECASE)
    case_regex = re.compile(r'CASE\s+WHEN\s+(?:[a-zA-Z0-9_]+\.)?([a-zA-Z0-9_]+)\s*=\s*([0-9]+|\'[^\']+\')\s+THEN\s+[\'"]([^\'"]+)[\'"]\s+ELSE\s+[\'"]([^\'"]+)[\'"]\s+END', re.IGNORECASE)

    for subdir, dirs, files in os.walk(root_path):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for file in files:
            if not file.endswith(('.php', '.html', '.jsx', '.tsx', '.vue', '.js')): continue
            file_path = os.path.join(subdir, file)
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    
                # A. Detect from <select> HTML
                selects = select_regex.findall(content)
                for select_name, select_inner in selects:
                    column_name = select_name.replace('[]', '').strip()
                    # Match any column containing status/type/state/mode/stage/category keywords
                    ENUM_KEYWORDS = ['status', 'type', 'category', 'role', 'state', 'active', 'gender', 'urgency', 'priority', 'mode', 'stage', 'grade', 'level', 'class']
                    if not any(kw in column_name.lower() for kw in ENUM_KEYWORDS):
                        continue
                    options = option_regex.findall(select_inner)
                    mapping = {}
                    for val, text in options:
                        val = clean_ui_text(val)
                        text = clean_ui_text(text)
                        if val and text and not val.startswith('<') and not val.startswith('{') and len(val) < 20:
                            mapping[val] = text
                    if mapping:
                        table_name = os.path.splitext(file)[0].lower()
                        table_name = re.sub(r'(_list|_add|_view|_edit|_pending|_completed)$', '', table_name)
                        if table_name not in enums: enums[table_name] = {}
                        if column_name not in enums[table_name]: enums[table_name][column_name] = mapping
                        
                # B. Detect from SQL CASE WHEN in queries
                case_matches = case_regex.findall(content)
                for col_name, val1, label1, label0 in case_matches:
                    val1 = val1.strip("'\"")
                    table_name = os.path.splitext(file)[0].lower()
                    table_name = re.sub(r'(_list|_add|_view|_edit|_pending|_completed)$', '', table_name)
                    if table_name not in enums: enums[table_name] = {}
                    if col_name not in enums[table_name]:
                        enums[table_name][col_name] = {val1: label1, "0": label0}
            except Exception: pass
            
    print(f"🧠 Auto-discovered enum mappings across {len(enums)} tables.")
    return enums

# =========================================================================
# 4. SYNC DISCOVERIES WITH AMOEBA BACKEND
# =========================================================================

def sync_with_amoeba(routes, base_api_url, api_key):
    url = f"{base_api_url}/api/routes/learn?api_key={api_key}"
    print(f"🚀 Syncing {len(routes)} routes with Amoeba ({url})...")
    try:
        data = json.dumps(routes).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={
            'Content-Type': 'application/json',
            'User-Agent': 'AmoebaConnector/3.0'
        })
        with urllib.request.urlopen(req) as response:
            print(f"✅ Route Sync Success: {response.read().decode('utf-8')}")
    except Exception as e:
        print(f"❌ Route sync failed: {e}")

def sync_semantics_with_amoeba(semantics, base_api_url, api_key):
    url = f"{base_api_url}/api/semantic/sync?api_key={api_key}"
    print(f"🚀 Syncing {len(semantics)} fullstack semantic mappings with Amoeba ({url})...")
    try:
        data = json.dumps(semantics).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={
            'Content-Type': 'application/json',
            'User-Agent': 'AmoebaConnector/3.0'
        })
        with urllib.request.urlopen(req) as response:
            print(f"✅ Semantic Sync Success: {response.read().decode('utf-8')}")
    except Exception as e:
        print(f"❌ Semantic sync failed: {e}")

def sync_enums_with_amoeba(enums, base_api_url, api_key):
    url = f"{base_api_url}/api/enums/learn?api_key={api_key}"
    print(f"🚀 Syncing enum mappings with Amoeba ({url})...")
    try:
        data = json.dumps(enums).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={
            'Content-Type': 'application/json',
            'User-Agent': 'AmoebaConnector/3.0'
        })
        with urllib.request.urlopen(req) as response:
            print(f"✅ Enum Sync Success: {response.read().decode('utf-8')}")
    except Exception as e:
        print(f"❌ Enum sync failed: {e}")

# =========================================================================
# 5. DYNAMIC LIVE WEB APPLICATION CRAWLER
# =========================================================================

def scan_live_web_application(base_url):
    """
    Crawls a live web application URL dynamically to discover routes, views,
    table columns, tabs, forms, and enums when source code files are remote or unavailable.
    Works for ANY web application (PHP, Python, Node, Java, Ruby, .NET).
    """
    import urllib.request
    import ssl
    from urllib.parse import urljoin, urlparse
    
    print(f"🌐 Initiating Dynamic Live Web Crawler for: {base_url}")
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    parsed_base = urlparse(base_url)
    domain = parsed_base.netloc
    
    routes = []
    semantics = []
    enums = {}
    
    visited_urls = set()
    to_visit = [base_url]
    seen_paths = set()
    seen_sem_keys = set()
    
    th_regex = re.compile(r'<th[^>]*>(.*?)</th>', re.IGNORECASE | re.DOTALL)
    title_regex = re.compile(r'<(?:h[1-4]|title)[^>]*>(.*?)</(?:h[1-4]|title)>|<div[^>]*class=["\'][^"\']*(?:card-title|box-title|page-title|page-header)[^"\']*["\'][^>]*>(.*?)</div>', re.IGNORECASE | re.DOTALL)
    link_regex = re.compile(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
    tab_regex = re.compile(r'<(?:a|button|li)[^>]+(?:data-toggle=["\']tab["\']|role=["\']tab["\']|href=["\']#[^"\']+["\'])[^>]*>(.*?)</(?:a|button|li)>', re.IGNORECASE | re.DOTALL)
    select_regex = re.compile(r'<select[^>]*name=["\']([^"\']+)["\'][^>]*>(.*?)</select>', re.IGNORECASE | re.DOTALL)
    option_regex = re.compile(r'<option[^>]*value=["\']([^"\']*)["\'][^>]*>(.*?)</option>', re.IGNORECASE)
    ajax_regex = re.compile(r'(?:url|sAjaxSource)\s*:\s*["\']([^"\']+)["\']', re.IGNORECASE)
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AmoebaConnector/3.5'
    }
    
    max_pages = 100
    while to_visit and len(visited_urls) < max_pages:
        current_url = to_visit.pop(0)
        norm_current = current_url.split('#')[0].rstrip('/')
        if norm_current in visited_urls:
            continue
        visited_urls.add(norm_current)
        
        try:
            req = urllib.request.Request(current_url, headers=headers)
            with urllib.request.urlopen(req, context=ctx, timeout=8) as response:
                content_type = response.headers.get('Content-Type', '')
                if 'text/html' not in content_type:
                    continue
                html = response.read().decode('utf-8', errors='ignore')
        except Exception:
            continue
            
        # Parse Page Title and Headings
        titles = []
        for match in title_regex.findall(html):
            t = match[0] or match[1]
            ct = clean_ui_text(t)
            if ct and len(ct) > 2 and len(ct) < 70 and not ct.startswith('$'):
                titles.append(ct)
                
        page_title = titles[0] if titles else ""
        clean_title = re.sub(r'^(?:newlook|company|admin|app|dashboard)[\s\-:]+', '', page_title, flags=re.IGNORECASE).strip()
        if not clean_title:
            clean_title = page_title
            
        path_only = urlparse(current_url).path
        if not path_only: path_only = "/"
        
        # Add Route
        if clean_title and path_only not in seen_paths:
            seen_paths.add(path_only)
            routes.append({
                "label": clean_title,
                "path": path_only,
                "keywords": clean_title.lower().split() + [p for p in path_only.split('/') if p]
            })
            
        # Extract Table Headers
        raw_ths = th_regex.findall(html)
        page_headers = []
        for th in raw_ths:
            cth = clean_ui_text(th)
            if cth and len(cth) > 1 and cth.lower() not in ['s.no', 'sno', 'sl.no', 'slno', 'action', 'actions', '#', 'edit', 'delete']:
                page_headers.append(cth)
                
        # Extract Tabs
        page_tabs = []
        for t in tab_regex.findall(html):
            ct = clean_ui_text(t)
            if ct and len(ct) > 2 and len(ct) < 50:
                page_tabs.append(ct)
                
        # Extract AJAX endpoints
        ajax_eps = ajax_regex.findall(html)
        
        # Extract Enums from selects
        for select_name, select_inner in select_regex.findall(html):
            col_name = select_name.replace('[]', '').strip()
            ENUM_KEYWORDS_LIVE = ['status', 'type', 'category', 'role', 'state', 'gender', 'urgency', 'priority', 'mode', 'stage', 'grade', 'level', 'class', 'employee_id']
            if any(kw in col_name.lower() for kw in ENUM_KEYWORDS_LIVE):
                options = option_regex.findall(select_inner)
                mapping = {}
                for val, text in options:
                    val = clean_ui_text(val)
                    text = clean_ui_text(text)
                    if val and text and len(val) < 20 and not val.startswith('<'):
                        mapping[val] = text
                if mapping:
                    tbl_guess = path_only.strip('/').split('/')[0] if path_only.strip('/') else "general"
                    if tbl_guess not in enums: enums[tbl_guess] = {}
                    enums[tbl_guess][col_name] = mapping
                    
        # Synthesize Semantic Mapping if page has a table or headers
        if page_headers or ajax_eps or page_tabs:
            path_parts = [p for p in path_only.strip('/').split('/') if p]
            inferred_table = path_parts[-1] if path_parts else "dashboard"
            inferred_table = re.sub(r'(_list|_report|_view|_index)$', '', inferred_table)
            inferred_module = path_parts[0] if path_parts else "General"
            
            headers_str = ", ".join(page_headers[:15]) if page_headers else None
            
            if clean_title:
                # HARDCODED OVERRIDE: Client 4 stores payment vouchers in expence_details
                if 'voucher' in clean_title.lower() and inferred_table in ['voucher', 'payment_voucher', 'expense_master', 'expense']:
                    inferred_table = 'expence_details'
                    
                # HARDCODED OVERRIDE: Client 4 uses 'product' table for parts setting list view
                if 'parts setting' in clean_title.lower() and inferred_table in ['product_parts_setting', 'parts_setting', 'part_setting', 'partssetting']:
                    inferred_table = 'product'
                    
                sem_key = (clean_title.lower(), inferred_table.lower())
                if sem_key not in seen_sem_keys:
                    seen_sem_keys.add(sem_key)
                    semantics.append({
                        "ui_label": clean_title,
                        "database_table": inferred_table,
                        "source_file": f"HTTP {path_only}",
                        "ui_columns": headers_str,
                        "default_filter": None,
                        "base_query": None,
                        "required_joins": None,
                        "tab_group": simple_title_case(inferred_module)
                    })
                
                # Tab-specific semantics
                for tab in page_tabs:
                    tab_lbl = f"{clean_title} {tab}" if tab.lower() not in clean_title.lower() else tab
                    tab_sem_key = (tab_lbl.lower(), inferred_table.lower())
                    if tab_sem_key not in seen_sem_keys:
                        seen_sem_keys.add(tab_sem_key)
                        semantics.append({
                            "ui_label": tab_lbl,
                            "database_table": inferred_table,
                            "source_file": f"HTTP {path_only}#{tab}",
                            "ui_columns": headers_str,
                            "default_filter": None,
                            "base_query": None,
                            "required_joins": None,
                            "tab_group": clean_title
                        })
                    
        # Discover new links on this page
        for href, link_text in link_regex.findall(html):
            href = href.strip()
            if not href or href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                continue
            if any(bad in href.lower() for bad in ['logout', 'signout', 'delete', 'remove', 'destroy']):
                continue
            full_link = urljoin(current_url, href)
            parsed_link = urlparse(full_link)
            if parsed_link.netloc == domain and full_link not in visited_urls and full_link not in to_visit:
                if not any(parsed_link.path.lower().endswith(ext) for ext in ['.jpg', '.png', '.gif', '.css', '.js', '.pdf', '.svg', '.zip']):
                    to_visit.append(full_link)
                    
    print(f"✅ Live Web Crawl Finished: {len(routes)} routes, {len(semantics)} semantic views, {len(enums)} enum sets.")
    return routes, semantics, enums

# =========================================================================
# 6. ENTRY POINT
# =========================================================================

def scan_project(target_dir, base_url):
    print(f"📂 Scanning target codebase: {target_dir}")
    framework = detect_framework(target_dir)
    print(f"⚡ Detected Framework: {framework}")
    
    if framework == "NEXTJS":
        routes = scan_nextjs_routes(target_dir, base_url)
    elif framework == "JS_SPA":
        routes = scan_generic_spa_routes(target_dir, base_url)
    else:
        routes = scan_php_mvc_routes(target_dir, base_url)
        
    semantics = scan_fullstack_semantics(target_dir)
    enums = scan_codebase_for_enums(target_dir)
    
    return routes, semantics, enums

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("=" * 65)
        print("🧠 AMOEBA UNIVERSAL CONNECTOR v3.5")
        print("=" * 65)
        print("Usage: python universal_connector.py \"<PROJECT_PATH_OR_URL>\" \"<API_KEY>\" [AMOEBA_HOST] [--use-ai]")
        print("Example 1 (Local Codebase): python universal_connector.py \"D:\\xampp\\htdocs\\my_erp\" \"my_key\"")
        print("Example 2 (Live Web App):  python universal_connector.py \"https://my-erp.com\" \"my_key\"")
        print("=" * 65)
        sys.exit(1)
        
    target_path = sys.argv[1]
    client_api_key = sys.argv[2]
    amoeba_host = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_AMOEBA_HOST
    amoeba_host = amoeba_host.rstrip('/')
    use_ai = '--use-ai' in sys.argv

    if target_path.startswith(('http://', 'https://')):
        routes, semantics, enums = scan_live_web_application(target_path)
        folder_name = ""
    else:
        if not os.path.exists(target_path):
            print(f"❌ Error: Directory not found: {target_path}")
            sys.exit(1)

        folder_name = os.path.basename(os.path.abspath(target_path))
        web_base_url = f"http://localhost/{folder_name}/"
        routes, semantics, enums = scan_project(target_path, web_base_url)

    # Prevent massive payload caps if an entire drive was provided
    if len(routes) > 2000:
        print(f"⚠️ Capping routes to 2000 (found {len(routes)})")
        routes = routes[:2000]
        
    if len(semantics) > 3000:
        print(f"⚠️ Capping semantics to 3000 (found {len(semantics)})")
        semantics = semantics[:3000]

    # 1. Sync Routes (Normalize paths to clean root-relative ERP paths)
    if routes:
        cleaned_routes = []
        seen_norm = set()
        
        # Dynamic base path detection: find the common prefix folder from all route paths
        all_paths = [r.get("path", "") for r in routes]
        parsed_paths = []
        for p in all_paths:
            if "://" in p:
                try: p = urllib.parse.urlparse(p).path
                except: pass
            parsed_paths.append(p)
        
        # Find common base prefix (e.g. /newlook/ or /sterling_company/)
        common_base = "/"
        if parsed_paths and folder_name:
            # Use the folder_name as the primary prefix to strip
            common_base_pattern = rf"^/(?:{re.escape(folder_name)})/"
        else:
            # Auto-detect: find the most common first path segment
            first_segments = []
            for p in parsed_paths:
                parts = [x for x in p.strip('/').split('/') if x]
                if len(parts) >= 2:
                    first_segments.append(parts[0].lower())
            if first_segments:
                from collections import Counter as PathCounter
                most_common_seg = PathCounter(first_segments).most_common(1)
                if most_common_seg and most_common_seg[0][1] > len(first_segments) * 0.5:
                    common_base_pattern = rf"^/{re.escape(most_common_seg[0][0])}/"
                else:
                    common_base_pattern = None
            else:
                common_base_pattern = None
        
        for r in routes:
            p = r.get("path", "")
            if "://" in p:
                try:
                    p = urllib.parse.urlparse(p).path
                except:
                    pass
            if common_base_pattern:
                p = re.sub(common_base_pattern, "/", p, flags=re.IGNORECASE)
            if not p.startswith("/"):
                p = "/" + p
            
            key = (r.get("label", "").strip().lower(), p.lower())
            if key not in seen_norm:
                seen_norm.add(key)
                r_clean = r.copy()
                r_clean["path"] = p
                cleaned_routes.append(r_clean)
                
        sync_with_amoeba(cleaned_routes, amoeba_host, client_api_key)
    else:
        print("ℹ️ No navigation routes found.")

    # 2. Sync Fullstack Semantics
    if semantics:
        sync_semantics_with_amoeba(semantics, amoeba_host, client_api_key)
    else:
        print("ℹ️ No semantic mappings found.")

    # 3. Sync Enums
    if enums:
        sync_enums_with_amoeba(enums, amoeba_host, client_api_key)
    else:
        print("ℹ️ No enum mappings found.")

    print("\n🎉 Universal Connector completed successfully!")
