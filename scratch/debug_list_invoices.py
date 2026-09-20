import asyncio
import json
import uuid
import websockets
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

API_KEY = "am_live_1iorVmBSbL3STz7UqFBO6BvUDUpaLUrfULNuUXuWHjA"
WS_URL = f"wss://amoeba.space/api/ws/chat?api_key={API_KEY}"

async def main():
    async with websockets.connect(WS_URL) as ws:
        payload = {
            "text": "List invoices",
            "mode": "operations",
            "session_id": f"sess_debug_{uuid.uuid4().hex[:8]}"
        }
        await ws.send(json.dumps(payload))
        try:
            while True:
                msg_raw = await asyncio.wait_for(ws.recv(), timeout=20.0)
                msg = json.loads(msg_raw)
                print("Received msg type:", msg.get("type"))
                if msg.get("type") == "chat_response":
                    print("AI Text:", msg.get("text"))
                    print("Actions:", msg.get("actions"))
                elif msg.get("type") == "done":
                    print("Done received!")
                    break
        except Exception as e:
            print("Exception while reading ws:", type(e), e)

asyncio.run(main())
