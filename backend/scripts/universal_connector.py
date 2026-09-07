import os
import re
import json
import sys
import urllib.request
import urllib.parse
from urllib.error import URLError
from collections import Counter

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
                    for m in methods:
                        if m.startswith('_') or m in ['construct', '__construct', 'get_instance']: continue
                        route_rel = f"{controller_name}/{m}"
                        full_url = urllib.parse.urljoin(base_url, route_rel)
                        if full_url not in seen_paths:
                            label = simple_title_case(m)
                            routes.append({
                                "label": f"{simple_title_case(controller_name)} - {label}",
                                "path": full_url,
                                "keywords": label.lower().split() + [controller_name]
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

def scan_fullstack_semantics(root_path):
    """
    Cross-correlates Frontend UI Screens (Views, titles, displayed columns)
    with the Backend Controllers/Models and physical Database Tables they actually query.
    """
    print("🕵️  Executing Fullstack MVC Cross-Correlation Profiler...")
    
    # --- PHASE 1: Index Controllers, Models & Database Queries ---
    controller_methods = {} # key -> { tables, views, subcalls, file }
    controller_files = {}   # class_name -> { file, methods }
    
    method_regex = re.compile(r'(?:public\s+)?function\s+([a-zA-Z0-9_]+)\s*\([^)]*\)\s*\{(.*?)(?=(?:public\s+)?function|\Z)', re.DOTALL | re.IGNORECASE)
    # Match Active Record, Eloquent, raw SQL queries, and table assignments
    table_regex = re.compile(r'(?:\$table\s*=\s*[\'"]|->(?:from|get|join|table)\s*\(\s*[\'"]|DB::table\s*\(\s*[\'"]|(?:FROM|JOIN)\s+`?)([a-zA-Z0-9_]+)', re.IGNORECASE)
    view_regex = re.compile(r'(?:load->view|view|render)\s*\(\s*[\'"]([^\'"]+)[\'"]', re.IGNORECASE)
    subcall_regex = re.compile(r'->([a-zA-Z0-9_]+Query|[a-zA-Z0-9_]+_Query|[a-zA-Z0-9_]+_data|[a-zA-Z0-9_]+DB|[a-zA-Z0-9_]+_DB)\s*\(', re.IGNORECASE)

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
                    
                    for match in method_regex.finditer(content):
                        fn_name = match.group(1).lower()
                        fn_body = match.group(2)
                        
                        raw_tables = table_regex.findall(fn_body)
                        clean_tables = [t.lower() for t in raw_tables if len(t) > 2 and t.lower() not in SQL_STOP_WORDS]
                        
                        loaded_views = [v.replace('\\', '/').lower() for v in view_regex.findall(fn_body)]
                        subcalls = [s.lower() for s in subcall_regex.findall(fn_body)]
                        
                        methods_in_file[fn_name] = {
                            "tables": clean_tables,
                            "views": loaded_views,
                            "subcalls": subcalls,
                            "file": rel_path
                        }
                        
                        controller_methods[f"{class_name}/{fn_name}"] = methods_in_file[fn_name]
                        controller_methods[fn_name] = methods_in_file[fn_name]
                        
                    controller_files[class_name] = {
                        "file": rel_path,
                        "methods": methods_in_file
                    }
                except Exception: pass

    # Trace helper subcalls (e.g. controller method calling a query helper)
    for fn_key, data in list(controller_methods.items()):
        for sc in data.get("subcalls", []):
            if sc in controller_methods:
                data["tables"].extend(controller_methods[sc]["tables"])

    print(f"📊 Indexed {len(controller_files)} backend controllers/models ({len(controller_methods)} methods).")

    # --- PHASE 2: Index Frontend Views, Headers & AJAX Data Sources ---
    views = []
    th_regex = re.compile(r'<th[^>]*>(.*?)</th>', re.IGNORECASE | re.DOTALL)
    title_regex = re.compile(r'<(?:h[1-4]|title)[^>]*>(.*?)</(?:h[1-4]|title)>|<div[^>]*class=["\'][^"\']*(?:card-title|box-title|page-title|page-header)[^"\']*["\'][^>]*>(.*?)</div>', re.IGNORECASE | re.DOTALL)
    # Extracts DataTables ajax endpoint or fetch URL: e.g. "url": "Inventory/purchase_order_pending_json"
    ajax_regex = re.compile(r'["\']?url["\']?\s*:\s*["\']?(?:<\?=[^>]*\?>)?/?([a-zA-Z0-9_]+)/([a-zA-Z0-9_]+)', re.IGNORECASE)

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
                        
                # Extract Screen Titles
                titles = []
                for match in title_regex.findall(content):
                    t = match[0] or match[1]
                    ct = clean_ui_text(t)
                    if ct and len(ct) > 2 and len(ct) < 60 and not ct.startswith('$') and not ct.startswith('<?'):
                        titles.append(ct)
                        
                # Extract AJAX endpoints
                ajax_endpoints = []
                for c_name, m_name in ajax_regex.findall(content):
                    ajax_endpoints.append(f"{c_name.lower()}/{m_name.lower()}")
                    
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
                    "ajax_endpoints": ajax_endpoints,
                    "content": content
                })
            except Exception: pass

    print(f"📊 Indexed {len(views)} UI views/templates.")

    # --- PHASE 3: Cross-Correlate Views to Database Tables ---
    semantics = []
    seen = set()

    for v in views:
        matched_tables = []
        source_controller = None
        
        # Link 1: AJAX Endpoint correlation (highest precision for DataTables / async pages)
        for ep in v["ajax_endpoints"]:
            if ep in controller_methods:
                c_data = controller_methods[ep]
                if c_data["tables"]:
                    matched_tables.extend(c_data["tables"])
                    source_controller = f"{c_data['file']}::{ep}"
                    break
            m_only = ep.split('/')[-1]
            if m_only in controller_methods:
                c_data = controller_methods[m_only]
                if c_data["tables"]:
                    matched_tables.extend(c_data["tables"])
                    source_controller = f"{c_data['file']}::{m_only}"
                    break
                    
        # Link 2: Controller load->view() correlation
        if not matched_tables:
            for fn_key, c_data in controller_methods.items():
                for loaded_view in c_data["views"]:
                    if v["view_base"] in loaded_view or loaded_view in v["view_key"]:
                        if c_data["tables"]:
                            matched_tables.extend(c_data["tables"])
                            source_controller = f"{c_data['file']}::{fn_key}"
                            break
                if matched_tables:
                    break

        # Link 3: Controller naming convention match
        if not matched_tables:
            for c_name, c_info in controller_files.items():
                if c_name in v["view_base"] or v["view_base"] in c_name:
                    all_c_tables = []
                    for m in c_info["methods"].values():
                        all_c_tables.extend(m["tables"])
                    if all_c_tables:
                        matched_tables.extend(all_c_tables)
                        source_controller = c_info["file"]
                        break

        # Link 4: Direct query inside view (for procedural / standalone PHP scripts)
        if not matched_tables:
            direct_tables = table_regex.findall(v["content"])
            clean_direct = [t.lower() for t in direct_tables if len(t) > 2 and t.lower() not in SQL_STOP_WORDS]
            if clean_direct:
                matched_tables.extend(clean_direct)
                source_controller = v["rel_path"]

        # Build Semantic Mappings
        if matched_tables:
            # Filter out common user/employee lookup tables to find the core business table
            core_tables = [t for t in matched_tables if t not in ['users', 'user', 'employee', 'branch', 'city', 'state']]
            table_pool = core_tables if core_tables else matched_tables
            
            # Prioritize header / master tables over detail / items tables
            header_tables = [t for t in table_pool if not any(t.endswith(sfx) for sfx in ['_detail', '_details', '_items', '_item', '_history'])]
            chosen_pool = header_tables if header_tables else table_pool
            
            primary_table = Counter(chosen_pool).most_common(1)[0][0]
            ui_cols_str = ", ".join(v["headers"]) if v["headers"] else None
            
            def add_semantic_entry(label_text):
                key = (label_text.lower(), primary_table)
                if key not in seen and len(label_text) >= 3:
                    semantics.append({
                        "ui_label": label_text,
                        "database_table": primary_table,
                        "source_file": f"{v['rel_path']} -> {source_controller}" if source_controller else v["rel_path"],
                        "ui_columns": ui_cols_str
                    })
                    seen.add(key)
            
            # 1. Full Screen Title (e.g. "Grn Inspection Pending List")
            add_semantic_entry(v["ui_label"])
            
            # 2. Normalized Base Term (e.g. "Grn Inspection")
            base_label = re.sub(r'\b(Pending|Completed|List|View|Report|Details|Master|Management|Index)\b', '', v["ui_label"], flags=re.IGNORECASE).strip()
            if base_label and base_label.lower() != v["ui_label"].lower():
                add_semantic_entry(base_label)
                
            # 3. Clean Filename Label if distinct
            file_label = simple_title_case(v["file"])
            if file_label.lower() not in [v["ui_label"].lower(), base_label.lower()]:
                add_semantic_entry(file_label)

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
                    if column_name.lower() not in ['status', 'type', 'category', 'role', 'state', 'is_active', 'gender', 'urgency', 'priority']:
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
# 5. ENTRY POINT
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
        print("🧠 AMOEBA UNIVERSAL CONNECTOR v3.0")
        print("=" * 65)
        print("Usage: python universal_connector.py \"<PROJECT_PATH>\" \"<API_KEY>\" [AMOEBA_HOST]")
        print("Example: python universal_connector.py \"D:\\xampp\\htdocs\\my_erp\" \"my_key\" \"http://localhost:8000\"")
        print("=" * 65)
        sys.exit(1)
        
    target_path = sys.argv[1]
    client_api_key = sys.argv[2]
    amoeba_host = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_AMOEBA_HOST
    amoeba_host = amoeba_host.rstrip('/')

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

    # 1. Sync Routes
    if routes:
        sync_with_amoeba(routes, amoeba_host, client_api_key)
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
