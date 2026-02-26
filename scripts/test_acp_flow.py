
import requests
import json

BASE_URL = "http://localhost:8000/api"

def test_acp_flow():
    print("🚀 Starting ACP Flow Verification...")
    
    # 1. Create Client
    print("\n1️⃣ Creating Client...")
    resp = requests.post(f"{BASE_URL}/clients", json={"client_name": "ACP Test Corp"})
    if resp.status_code != 200:
        print(f"❌ Failed to create client: {resp.text}")
        return
        
    data = resp.json()
    client_id = data["data"]["client_id"]
    api_key = data["data"]["api_key"]
    print(f"✅ Client Created! ID: {client_id}, Key: {api_key}")
    
    # 2. Connect Database (Using our local docker DB for testing)
    print("\n2️⃣ Connecting Database...")
    # NOTE: In Docker, 'db' is the hostname of the postgres container.
    # We must ensure this script runs in a context that can reach it, OR we use localhost if port mapped.
    # Assuming script runs on host and can reach mapped port 5432.
    db_payload = {
        "db_type": "postgresql",
        "host": "db", # Internal docker service name
        "port": 5432,
        "database": "amoeba", # Connect to self for test
        "username": "user",
        "password": "password"
    }
    
    resp = requests.post(f"{BASE_URL}/clients/{client_id}/database", json=db_payload)
    if resp.status_code == 200:
        print("✅ Database Connected & Verified!")
    else:
        print(f"❌ DB Connection Failed (Expected if credentials/network differ): {resp.text}")
        # Proceeding strictly might fail if network is an issue, but we want to see the error.
    
    # 3. Discover Tables
    print("\n3️⃣ Discovering Tables...")
    resp = requests.get(f"{BASE_URL}/clients/{client_id}/tables")
    if resp.status_code == 200:
        tables = resp.json()["tables"]
        print(f"✅ Discovered {len(tables)} tables.")
        # print([t["name"] for t in tables])
    else:
        print(f"❌ Discovery Failed: {resp.text}")

    # 4. Register Report (No SQL)
    print("\n4️⃣ Registering Report (report_registry)...")
    report_payload = {
        "client_id": client_id,
        "report_name": "System Reports",
        "base_table": "report_registry", # querying self table as test
        "output_format": "xlsx"
    }
    
    resp = requests.post(f"{BASE_URL}/reports", json=report_payload)
    if resp.status_code == 200:
        print(f"✅ Report Registered! SQL: {resp.json()['data']['sql_generated']}")
    else:
        print(f"❌ Report Registration Failed: {resp.text}")

if __name__ == "__main__":
    test_acp_flow()
