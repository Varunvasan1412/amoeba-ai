import asyncio
import json
import uuid
import websockets
import sys

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

API_KEY = "am_live_1iorVmBSbL3STz7UqFBO6BvUDUpaLUrfULNuUXuWHjA"
WS_URL = f"wss://amoeba.space/api/ws/chat?api_key={API_KEY}"

async def send_query(query: str, session_id: str):
    print(f"\n==========================================")
    print(f"TEST QUERY: '{query}' (Session: {session_id})")
    print(f"==========================================")
    async with websockets.connect(WS_URL) as ws:
        payload = {
            "text": query,
            "mode": "operations",
            "session_id": session_id
        }
        await ws.send(json.dumps(payload))
        
        responses = []
        while True:
            raw = await ws.recv()
            msg = json.loads(raw)
            msg_type = msg.get("type")
            
            if msg_type == "chat_response":
                text = msg.get("text", "")
                actions = msg.get("actions", [])
                print(f"AI Text: {text}")
                for a in actions:
                    a_type = a.get("type")
                    if a_type == "data_table":
                        p = a.get("payload", {})
                        print(f"  [DATA TABLE] Title='{p.get('title')}', Total Rows={p.get('total')}")
                        if p.get("rows"):
                            print(f"  Sample first row: {list(p['rows'][0].items())[:3]}")
                    elif a_type == "NAVIGATE":
                        print(f"  [NAVIGATE ACTION] Destination='{a.get('payload')}'")
                    elif a_type == "CHOICE":
                        print(f"  [CHOICE OPTIONS] {[opt.get('label') for opt in a.get('payload', [])]}")
                    else:
                        print(f"  [ACTION] type='{a_type}', payload={a.get('payload')}")
                responses.append(msg)
                
            elif msg_type == "done":
                break
                
    return responses

async def main():
    # Test 1: List the payroll report -> Must directly return 13 employee records!
    s1 = f"sess_test_{uuid.uuid4().hex[:8]}"
    await send_query("List the payroll report", s1)
    await asyncio.sleep(1)

    # Test 2: List the payroll history -> Must directly return 4 attendance records!
    s2 = f"sess_test_{uuid.uuid4().hex[:8]}"
    await send_query("List the payroll history", s2)
    await asyncio.sleep(1)

    # Test 3: List the payroll (ambiguous) -> Must ask user which tab to view!
    s3 = f"sess_test_{uuid.uuid4().hex[:8]}"
    await send_query("List the payroll", s3)
    await asyncio.sleep(1)

    # Test 4: Navigate to payroll report -> Must navigate to /payroll/report!
    s4 = f"sess_test_{uuid.uuid4().hex[:8]}"
    await send_query("Navigate to payroll report", s4)
    await asyncio.sleep(1)

    # Test 5: Navigate to payroll history -> Must navigate to /payroll/list!
    s5 = f"sess_test_{uuid.uuid4().hex[:8]}"
    await send_query("Navigate to payroll history", s5)
    await asyncio.sleep(1)

    # Test 6: List pending invoices -> Must return pending invoices!
    s6 = f"sess_test_{uuid.uuid4().hex[:8]}"
    await send_query("List pending invoices", s6)
    await asyncio.sleep(1)

    # Test 7: List completed invoices -> Must return 14 completed invoices!
    s7 = f"sess_test_{uuid.uuid4().hex[:8]}"
    await send_query("List completed invoices", s7)
    await asyncio.sleep(1)

    # Test 8: List invoices (ambiguous) -> Must ask user which tab to view!
    s8 = f"sess_test_{uuid.uuid4().hex[:8]}"
    await send_query("List invoices", s8)

asyncio.run(main())
