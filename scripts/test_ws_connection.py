
import asyncio
import websockets
import json

async def test_websocket():
    uri = "ws://localhost:8000/api/ws/chat?api_key=test_client_key_123"
    print(f"🔌 Connecting to {uri}...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connected!")
            
            # Send a message
            await websocket.send("Hello, Amoeba!")
            print("📨 Sent: Hello, Amoeba!")
            
            # Wait for response
            response = await websocket.recv()
            print(f"📩 Received: {response}")
            
            # Wait a bit to ensure logs are flushed
            await asyncio.sleep(1)
            
    except Exception as e:
        print(f"❌ Connection Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket())
