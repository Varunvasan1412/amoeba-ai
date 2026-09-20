import asyncio
import json
import uuid
import websockets
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

async def test():
    async with websockets.connect('wss://amoeba.space/api/ws/chat?api_key=am_live_1iorVmBSbL3STz7UqFBO6BvUDUpaLUrfULNuUXuWHjA') as ws:
        await ws.send(json.dumps({
            'text': 'List invoices',
            'mode': 'operations',
            'session_id': 'sess_' + uuid.uuid4().hex[:8]
        }))
        while True:
            raw = await ws.recv()
            msg = json.loads(raw)
            if msg.get('type') == 'chat_response':
                print('Response text:', msg.get('text'))
                for a in msg.get('actions', []):
                    if a.get('type') == 'CHOICE':
                        print('Choices:', [opt.get('label') for opt in a.get('payload', [])])
            elif msg.get('type') == 'done':
                break

asyncio.run(test())
