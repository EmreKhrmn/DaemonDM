import asyncio
import threading
import http.server
import socketserver
import json
import time
import websockets

ws_clients = set()
ws_loop = None
last_state = {"users": 0, "messages": 0}


#http server
class CustomHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path.startswith("/index.html") or self.path.startswith("/monitor.html"):
            self.path = "/monitor.html"
        return super().do_GET()

    def log_message(self, format, *args):
        pass


def start_http_server(host, port):
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer((host, port), CustomHandler) as httpd:
        print(f"HTTP server running at http://{host}:{port}")
        httpd.serve_forever()


#websocket server
async def ws_handler(websocket):
    ws_clients.add(websocket)
    try:
        init_payload = json.dumps({
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "tag": "SYNC",
            "text": "watchd attached to DaemonDM server",
            "users": last_state["users"],
            "messages": last_state["messages"]
        })
        await websocket.send(init_payload)
        async for _ in websocket:
            pass
    except:
        pass
    finally:
        ws_clients.discard(websocket)


async def broadcast_ws(data):
    if ws_clients:
        await asyncio.gather(*(ws.send(data) for ws in list(ws_clients)), return_exceptions=True)


def push_event(ts, tag, text, users, messages):
    last_state["users"] = users
    last_state["messages"] = messages
    if ws_loop and ws_loop.is_running():
        data = json.dumps({
            "time": ts,
            "tag": tag,
            "text": text,
            "users": users,
            "messages": messages
        })
        asyncio.run_coroutine_threadsafe(broadcast_ws(data), ws_loop)


async def start_ws_server(host, ws_port):
    global ws_loop
    ws_loop = asyncio.get_running_loop()
    async with websockets.serve(lambda ws: ws_handler(ws), host, ws_port):
        print(f"WebSocket server running at ws://{host}:{ws_port}")
        await asyncio.Future()  #run forever


def start_monitoring(host, http_port, ws_port):
    threading.Thread(target=start_http_server, args=(host, http_port), daemon=True).start()
    asyncio.run(start_ws_server(host, ws_port))