import asyncio
import websockets
import json

async def test_websocket():
    # Replace these values with your actual token and quiz code
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJuZ2hpYWhzZ3NAZ21haWwuY29tIiwiaWQiOiIxIiwiZXhwIjoxNzM1MDE2MDk0fQ.GxUBuz-TAoTmscCVpkScjWMx_RigEHUG2lnivdzJ4OA"

    quiz_code = "TYR690"
    
    uri = f"wss://elsa-be-production.up.railway.app/api/quiz/{quiz_code}?token={token}"
    
    print(f"Connecting to {uri}")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected to WebSocket server!")
            
            # Keep the connection alive and listen for messages
            while True:
                try:
                    message = await websocket.recv()
                    print(f"Received message: {message}")
                except websockets.exceptions.ConnectionClosed:
                    print("Connection closed")
                    break
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket())
