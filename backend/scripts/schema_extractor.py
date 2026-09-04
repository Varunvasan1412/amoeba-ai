import sys
import json
import urllib.request
import urllib.parse
import pymysql
from typing import List, Dict, Any

# CONFIGURATION
AMOEBA_API_URL = "http://localhost:8000/api/schema/learn"

def extract_schema(host, user, password, db_name, port=3306) -> List[Dict[str, Any]]:
    print(f"🕵️ Connecting to database: {db_name} at {host}...")
    try:
        connection = pymysql.connect(
            host=host,
            user=user,
            password=password,
            database=db_name,
            port=int(port),
            cursorclass=pymysql.cursors.DictCursor
        )
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        sys.exit(1)

    schema_data = []

    try:
        with connection.cursor() as cursor:
            # Get all tables
            cursor.execute("SHOW TABLES")
            tables = [list(row.values())[0] for row in cursor.fetchall()]

            print(f"📚 Found {len(tables)} tables. Extracting schema...")

            for table in tables:
                cursor.execute(f"DESCRIBE `{table}`")
                columns = cursor.fetchall()
                
                # Format into a clean string representation for the LLM
                col_defs = []
                for col in columns:
                    col_str = f"{col['Field']} ({col['Type']})"
                    if col['Key'] == 'PRI':
                        col_str += " [PRIMARY KEY]"
                    if col['Key'] == 'MUL':
                        col_str += " [FOREIGN KEY/INDEX]"
                    col_defs.append(col_str)
                
                # Get row count to help LLM know if table is active
                try:
                    cursor.execute(f"SELECT COUNT(*) as cnt FROM `{table}`")
                    row_count = cursor.fetchone()['cnt']
                except Exception:
                    row_count = 0
                
                schema_definition = f"Table: {table} (Row Count: {row_count})\nColumns:\n" + "\n".join([f" - {c}" for c in col_defs])
                
                schema_data.append({
                    "table_name": table,
                    "schema_definition": schema_definition
                })
    finally:
        connection.close()

    return schema_data

def sync_schema_with_amoeba(schema_data: List[Dict[str, Any]], api_key: str):
    print(f"🚀 Syncing {len(schema_data)} table schemas with Amoeba Brain...")
    try:
        data = json.dumps(schema_data).encode('utf-8')
        url_with_key = f"{AMOEBA_API_URL}?api_key={api_key}"
        
        req = urllib.request.Request(url_with_key, data=data, headers={
            'Content-Type': 'application/json',
            'User-Agent': 'AmoebaSchemaExtractor/1.0'
        })
        with urllib.request.urlopen(req) as response:
            print(f"✅ Success! Amoeba responded: {response.read().decode('utf-8')}")
    except Exception as e:
        print(f"❌ Connection failed: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 7:
        print("❌ Error: Missing arguments.")
        print("Usage: python schema_extractor.py <host> <port> <user> <password> <db_name> <api_key>")
        sys.exit(1)
        
    host = sys.argv[1]
    port = sys.argv[2]
    user = sys.argv[3]
    password = "" if sys.argv[4].lower() == "empty" else sys.argv[4]
    db_name = sys.argv[5]
    api_key = sys.argv[6]
    
    schema_data = extract_schema(host, user, password, db_name, port)
    
    if schema_data:
        sync_schema_with_amoeba(schema_data, api_key)
    else:
        print("🤷 No tables found in database.")
