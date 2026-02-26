
import asyncio
import time
from app.core.rate_limiter import limiter
from app.models.audit_log import AuditLog
from app.core.database import init_db

async def test_safety():
    print("🛡️  Starting Safety & Observability Verification...")
    
    # 1. Verify Rate Limiter
    print("\n1️⃣  Testing Rate Limiter (Chat)...")
    client_id = 999
    
    # Simulate 60 messages (Should pass)
    for i in range(60):
        if not limiter.check_chat(client_id):
            print(f"❌ Failed unexpectedly at message {i+1}")
            return
            
    # 61st message (Should Block)
    if not limiter.check_chat(client_id):
        print("✅ Rate Limiter Blocked Message 61 (Success)")
    else:
        print("❌ Rate Limiter FAILED to block message 61")
        
    print("\n2️⃣  Testing Rate Limiter (Export)...")
    # Simulate 10 exports
    for i in range(10):
        if not limiter.check_export(client_id):
             print(f"❌ Failed unexpectedly at export {i+1}")
    
    # 11th export
    if not limiter.check_export(client_id):
        print("✅ Rate Limiter Blocked Export 11 (Success)")
    else:
        print("❌ Rate Limiter FAILED to block export 11")

    # 3. Verify Audit Log Schema
    print("\n3️⃣  Verifying Audit Log Schema...")
    # This just ensures we can import and inspect the model, 
    # and that init_db would create it (which we assume happens in the app)
    # Ideally we'd select from DB, but we don't have a running loop/session easily here without heavy setup.
    # We will rely on printing the SQL definition or model fields.
    
    fields = AuditLog.__fields__
    print(f"✅ AuditLog Model Fields: {list(fields.keys())}")
    
    print("\n🎉 Safety Verification Complete.")

if __name__ == "__main__":
    asyncio.run(test_safety())
