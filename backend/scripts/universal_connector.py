import os
import re
import json
import sys
import urllib.request
import urllib.parse
from urllib.error import URLError

# ==========================================
# 🧠 AMOEBA UNIVERSAL CONNECTOR AGENT v2.0
# ==========================================
# Supports: PHP, HTML, Next.js, React, Vue, Angular
# ==========================================

AMOEBA_API_URL = "https://amoeba.space/api/routes/learn" 
AMOEBA_SEMANTIC_URL = "https://amoeba.space/api/semantic/sync"
AMOEBA_ENUMS_URL = "https://amoeba.space/api/enums/learn"
AMOEBA_API_KEY = "thermosen_api_key" # Replace with actual key in production
IGNORE_DIRS = {'.git', 'node_modules', 'vendor', '__pycache__', 'dist', 'build', '.next', 'coverage'}

def simple_title_case(s):
    """Converts 'user-profile' or 'user_profile' to 'User Profile'"""
    s = os.path.splitext(s)[0] # remove ext
    s = s.replace("_", " ").replace("-", " ")
    # Handle dynamic routes like [id]
    s = re.sub(r'\[.*?\]', 'Detail', s)
    return s.title()

def detect_framework(root_path):
    """Detects the likely framework used in the project."""
    if os.path.exists(os.path.join(root_path, 'next.config.js')) or os.path.exists(os.path.join(root_path, 'next.config.mjs')):
        return "NEXTJS"
    if os.path.exists(os.path.join(root_path, 'artisan')):
        return "LARAVEL" # (PHP)
    if os.path.exists(os.path.join(root_path, 'composer.json')):
         # Fallback check for PHP if not Laravel
        return "PHP"
    if os.path.exists(os.path.join(root_path, 'package.json')):
        # Could be React/Vue/Angular. We'll Generic JS Scan.
        return "JS_SPA"
    return "LEGACY_PHP_HTML"

def scan_nextjs(root_path, base_url):
    print("⚡ Deteced Next.js Project")
    routes = []
    
    # Next.js uses 'pages' or 'app' directory
    target_dirs = ['pages', 'app', 'src/pages', 'src/app']
    
    for relative_dir in target_dirs:
        scan_dir = os.path.join(root_path, relative_dir)
        if not os.path.exists(scan_dir):
            continue
            
        print(f"   Scanning directory: {relative_dir}")
        for subdir, dirs, files in os.walk(scan_dir):
            for file in files:
                if file.startswith('_') or file.startswith('.'): continue
                if not file.endswith(('.js', '.jsx', '.ts', '.tsx')): continue
                
                # Convert File Path to Route Path
                # pages/users/[id].tsx -> /users/:id
                
                full_path = os.path.join(subdir, file)
                rel_from_pages = os.path.relpath(full_path, scan_dir)
                
                # Remove extension
                route_path = os.path.splitext(rel_from_pages)[0]
                
                # Handle 'index'
                if route_path.endswith('index'):
                    route_path = route_path[:-5] # remove 'index'
                
                # Cleanup slashes
                route_path = route_path.replace("\\", "/")
                if not route_path.startswith('/'):
                    route_path = '/' + route_path
                
                # Handle Dynamic Routes [id] -> :id (optional, for readability)
                # But keep it as is or clean it up for the label
                
                label = simple_title_case(os.path.basename(file))
                if not label: label = "Home"
                
                full_url = urllib.parse.urljoin(base_url, route_path)
                
                routes.append({
                    "label": label,
                    "path": full_url,
                    "keywords": label.lower().split() + ["nextjs"]
                })
    return routes

def scan_generic_spa(root_path, base_url):
    print("⚛️  Detected Single Page Application (React/Vue/Angular)")
    routes = []
    seen_paths = set()
    
    # For SPAs, we look for Router definitions in code
    # Matches: path="/about" or path: '/about'
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
                            # Guess Label from path: /user-settings -> User Settings
                            label = simple_title_case(match.split('/')[-1])
                            if not label: label = "Home"
                            
                            full_url = urllib.parse.urljoin(base_url, match)
                            
                            routes.append({
                                "label": label,
                                "path": full_url,
                                "keywords": label.lower().split()
                            })
                            seen_paths.add(match)
            except: pass
            
    return routes

def scan_legacy_php(root_path, base_url):
    print("🐘 Detected Legacy PHP/HTML Project")
    routes = []
    seen_paths = set()
    
    for subdir, dirs, files in os.walk(root_path):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for file in files:
            if file.lower().endswith(('.php', '.html', '.htm')):
                file_path = os.path.join(subdir, file)
                rel_path = os.path.relpath(file_path, root_path)
                web_path = rel_path.replace("\\", "/")
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

def scan_codebase_for_semantics(root_path):
    print("🕵️  Profiling codebase for semantic UI-to-Database mappings...")
    semantics = []
    
    # Very generic heuristic: finding SELECT FROM or $table = '...' in files
    table_regex = re.compile(r'(?:FROM|INTO|UPDATE|JOIN|\$table\s*=\s*[\'"])\s*([a-zA-Z0-9_]+)', re.IGNORECASE)
    
    for subdir, dirs, files in os.walk(root_path):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for file in files:
            if not file.endswith(('.php', '.js', '.ts', '.py')): continue
            if file.endswith('.min.js') or file.lower() in ['jquery.js', 'bootstrap.js', 'vue.js', 'react.js']: continue
            
            file_path = os.path.join(subdir, file)
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    raw_tables = table_regex.findall(content)
                    valid_tables = [t.lower() for t in raw_tables if len(t) > 2 and t.lower() not in ['this', 'select', 'where', 'set']]
                    
                    if valid_tables:
                        from collections import Counter
                        # Only take the most frequently referenced table as the primary mapping for this UI page
                        most_common_table = Counter(valid_tables).most_common(1)[0][0]
                        label = simple_title_case(file)
                        
                        # Extract HTML table headers (<th>) to give the AI context on what is physically displayed
                        th_regex = re.compile(r'<th[^>]*>(.*?)</th>', re.IGNORECASE | re.DOTALL)
                        headers_found = th_regex.findall(content)
                        clean_headers = []
                        for h in headers_found:
                            clean_h = re.sub(r'<[^>]+>', '', h).strip()
                            if clean_h and len(clean_h) > 1:
                                clean_headers.append(clean_h)
                                
                        ui_columns_str = ", ".join(clean_headers[:15]) if clean_headers else None
                        
                        semantics.append({
                            "ui_label": label,
                            "database_table": most_common_table,
                            "source_file": file,
                            "ui_columns": ui_columns_str
                        })
            except Exception:
                pass
                
    print(f"🧠 Found {len(semantics)} potential semantic mappings in code.")
    return semantics

def scan_codebase_for_enums(root_path):
    print("🕵️  Profiling codebase for automated Enum mappings (<select> tags)...")
    enums = {} # table_name -> column_name -> {val: label}
    
    select_regex = re.compile(r'<select[^>]*name=["\']([^"\']+)["\'][^>]*>(.*?)</select>', re.IGNORECASE | re.DOTALL)
    option_regex = re.compile(r'<option[^>]*value=["\']([^"\']+)["\'][^>]*>(.*?)</option>', re.IGNORECASE)
    
    for subdir, dirs, files in os.walk(root_path):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for file in files:
            if not file.endswith(('.php', '.html', '.jsx', '.tsx', '.vue')): continue
            
            file_path = os.path.join(subdir, file)
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    selects = select_regex.findall(content)
                    
                    for select_name, select_inner in selects:
                        # Clean up column name (remove [] for array inputs like status[])
                        column_name = select_name.replace('[]', '').strip()
                        
                        # Only care about common enum columns
                        if column_name.lower() not in ['status', 'type', 'category', 'role', 'state', 'is_active']:
                            continue
                            
                        options = option_regex.findall(select_inner)
                        mapping = {}
                        for val, text in options:
                            val = val.strip()
                            text = text.strip()
                            # Ignore empty values or template variables
                            if val and text and not val.startswith('<') and not val.startswith('{') and not text.startswith('<'):
                                mapping[val] = text
                                
                        if mapping:
                            # Guess table name from filename
                            table_name = os.path.splitext(file)[0].replace('_list', '').replace('_add', '').replace('view_', '').replace('add_', '')
                            table_name = table_name.lower()
                            
                            if table_name not in enums:
                                enums[table_name] = {}
                            if column_name not in enums[table_name]:
                                enums[table_name][column_name] = mapping
            except Exception:
                pass
                
    print(f"🧠 Auto-discovered enum mappings for {len(enums)} tables.")
    return enums

def scan_project(root_path):
    print(f"🕵️  Scanning project at: {root_path}")
    
    # 1. Determine Base URL
    folder_name = os.path.basename(root_path)
    base_url = f"http://localhost/{folder_name}/" 
    
    # 2. Detect Framework
    framework = detect_framework(root_path)
    
    routes = []
    if framework == "NEXTJS":
        routes = scan_nextjs(root_path, base_url)
    elif framework == "JS_SPA":
        routes = scan_generic_spa(root_path, base_url)
    else:
        routes = scan_legacy_php(root_path, base_url)
        
    semantics = scan_codebase_for_semantics(root_path)
        
    return routes, semantics

def sync_with_amoeba(routes, api_key):
    print(f"🚀 Syncing {len(routes)} routes with Amoeba Brain...")
    try:
        data = json.dumps(routes).encode('utf-8')
        
        # Append API key to URL query params
        url_with_key = f"{AMOEBA_API_URL}?api_key={api_key}"
        
        req = urllib.request.Request(url_with_key, data=data, headers={
            'Content-Type': 'application/json',
            'User-Agent': 'AmoebaConnector/2.0'
        })
        with urllib.request.urlopen(req) as response:
            print(f"✅ Success! Amoeba responded: {response.read().decode('utf-8')}")
    except Exception as e:
        print(f"❌ Route sync failed: {e}")

def sync_semantics_with_amoeba(semantics, api_key):
    print(f"🚀 Syncing {len(semantics)} semantic mappings with Amoeba Brain...")
    try:
        data = json.dumps(semantics).encode('utf-8')
        url_with_key = f"{AMOEBA_SEMANTIC_URL}?api_key={api_key}"
        
        req = urllib.request.Request(url_with_key, data=data, headers={
            'Content-Type': 'application/json',
            'User-Agent': 'AmoebaConnector/2.0'
        })
        with urllib.request.urlopen(req) as response:
            print(f"✅ Semantic Sync Success! Amoeba responded: {response.read().decode('utf-8')}")
    except Exception as e:
        print(f"⚠️ Semantic sync skipped or failed (API might not exist yet): {e}")

def sync_enums_with_amoeba(enums, api_key):
    print(f"🚀 Syncing auto-discovered Enum mappings with Amoeba Brain...")
    try:
        data = json.dumps(enums).encode('utf-8')
        url_with_key = f"{AMOEBA_ENUMS_URL}?api_key={api_key}"
        
        req = urllib.request.Request(url_with_key, data=data, headers={
            'Content-Type': 'application/json',
            'User-Agent': 'AmoebaConnector/2.0'
        })
        with urllib.request.urlopen(req) as response:
            print(f"✅ Enum Sync Success! Amoeba responded: {response.read().decode('utf-8')}")
    except Exception as e:
        print(f"⚠️ Enum sync skipped or failed: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("❌ Error: Missing arguments.")
        print("Usage: python universal_connector.py \"/path/to/project\" \"YOUR_API_KEY\"")
        sys.exit(1)
        
    target_dir = sys.argv[1]
    api_key = sys.argv[2]
    
    if not os.path.exists(target_dir):
        print(f"❌ Error: Directory not found: {target_dir}")
        sys.exit(1)
        
    routes, semantics = scan_project(target_dir)
    
    # Cap routes to prevent massive payload errors (422) if they scan a huge directory like C:\
    if len(routes) > 2000:
        print(f"⚠️ Warning: Found {len(routes)} routes, capping at 2000 to prevent payload size errors.")
        routes = routes[:2000]
        
    if routes:
        sync_with_amoeba(routes, api_key)
    else:
        print("🤷 No routes found.")
        
    if semantics:
        # Cap semantics too
        if len(semantics) > 5000:
            semantics = semantics[:5000]
        sync_semantics_with_amoeba(semantics, api_key)

    # Auto-discover enums
    enums = scan_codebase_for_enums(target_dir)
    if enums:
        sync_enums_with_amoeba(enums, api_key)
    else:
        print("ℹ️ No enum mappings auto-discovered.")
