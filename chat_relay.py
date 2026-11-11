import socket
import struct
import threading
import argparse

PROXY_HOST = '127.0.0.1'
PROXY_PORT = 6000  #relay listens on port 6000
SERVER_HOST = '127.0.0.1'
SERVER_PORT = 5001  #relay connects to server relay port 5001
BUF_SIZE = 4096


#framing utilities 
def send(channel, message):
    buffer = message.encode('utf-8')
    value = socket.htonl(len(buffer))
    size = struct.pack("!I", value)
    channel.sendall(size + buffer)


def receive(channel):
    size_len = struct.calcsize("!I")
    size_data = b""
    while len(size_data) < size_len:
        chunk = channel.recv(size_len - len(size_data))
        if not chunk:
            return ''
        size_data += chunk
    try:
        size = socket.ntohl(struct.unpack("!I", size_data)[0])
    except struct.error:
        return ''
    buf = b""
    while len(buf) < size:
        chunk = channel.recv(size - len(buf))
        if not chunk:
            return ''
        buf += chunk
    return buf.decode('utf-8', errors='replace')


def forward_stream(src, dst):
    try:
        while True:
            data = src.recv(BUF_SIZE)
            if not data:
                break
            dst.sendall(data)
    except socket.error:
        pass
    finally:
        for s in (src, dst):
            try:
                s.shutdown(socket.SHUT_RDWR)
            except:
                pass
            try:
                s.close()
            except:
                pass


def handle_client(client_conn, addr, srv_host, srv_port):
    server_sock = None
    try:
        reg = receive(client_conn)
        if not reg or not reg.startswith("NAME: "):
            send(client_conn, "ERROR: Expected NAME registration")
            client_conn.close()
            return

        cname = reg.split("NAME: ", 1)[1].strip()
        if not cname or cname.startswith("*"):
            send(client_conn, "ERROR: Relay rejects nicknames starting with '*'")
            print(f"[Relay] Rejected '*' nickname '{cname}' from {addr}")
            client_conn.close()
            return

        relayed_name = "*" + cname
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.connect((srv_host, srv_port))

        send(server_sock, "NAME: " + relayed_name)
        print(f"[Relay] Forwarding {addr} as '{relayed_name}' -> {srv_host}:{srv_port}")

        t1 = threading.Thread(target=forward_stream, args=(client_conn, server_sock), daemon=True)
        t2 = threading.Thread(target=forward_stream, args=(server_sock, client_conn), daemon=True)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        print(f"[Relay] Session closed for {relayed_name}")
    except socket.error as e:
        print(f"[Relay] Socket error: {e}")
        if client_conn:
            client_conn.close()
        if server_sock:
            server_sock.close()


def start_proxy(proxy_host, proxy_port, srv_host, srv_port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((proxy_host, proxy_port))
        s.listen(10)
        print(f"Proxy listening on {proxy_host}:{proxy_port} -> {srv_host}:{srv_port}")
        while True:
            client_conn, addr = s.accept()
            print(f"Proxy accepted connection from {addr}")
            threading.Thread(
                target=handle_client,
                args=(client_conn, addr, srv_host, srv_port),
                daemon=True
            ).start()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='DaemonDM Relay Proxy')
    parser.add_argument('--host', action="store", dest="host", default=PROXY_HOST)
    parser.add_argument('--port', action="store", dest="port", type=int, default=PROXY_PORT)
    parser.add_argument('--server-host', action="store", dest="server_host", default=SERVER_HOST)
    parser.add_argument('--server-port', action="store", dest="server_port", type=int, default=SERVER_PORT)
    given_args = parser.parse_args()

    try:
        start_proxy(given_args.host, given_args.port, given_args.server_host, given_args.server_port)
    except KeyboardInterrupt:
        print("\nRelay stopped.")