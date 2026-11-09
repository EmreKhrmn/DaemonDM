import socket
import struct
import threading
import argparse
import time

SERVER_HOST = '127.0.0.1'
BUF_SIZE = 4096

#sharedstate
state_lock = threading.Lock()
clientmap = {}



#framing utilites
def send(channel, message, lock=None):
    buffer = message.encode('utf-8')
    value = socket.htonl(len(buffer))
    size = struct.pack("!I", value)
    if lock:
        with lock:
            channel.sendall(size + buffer)
    else:
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

    if size <= 0 or size > BUF_SIZE:
        raise ValueError("Invalid message size: %d" % size)

    buf = b""
    while len(buf) < size:
        chunk = channel.recv(size - len(buf))
        if not chunk:
            return ''
        buf += chunk
    return buf.decode('utf-8', errors='replace')


def get_timestamp():
    return time.strftime("%H:%M:%S")


def broadcast_chat(msg_str):
    with state_lock:
        targets = [(info["sock"], info["lock"]) for info in clientmap.values()]
    for sock, lock in targets:
        try:
            send(sock, msg_str, lock)
        except socket.error:
            pass


def handle_chat_client(client, address):
    cname = None
    c_lock = threading.Lock()

    try:
        raw_reg = receive(client)
        if not raw_reg or not raw_reg.startswith("NAME: "):
            send(client, "ERROR: Invalid registration header", c_lock)
            client.close()
            return

        cname = raw_reg.split("NAME: ", 1)[1].strip()
        with state_lock:
            clientmap[cname] = {
                "sock": client,
                "addr": address,
                "lock": c_lock
            }

        send(client, "CLIENT: " + cname, c_lock)
        print("Chat server: got connection %s from %s" % (cname, address))
        broadcast_chat("SYS: [%s] * %s joined DaemonDM" % (get_timestamp(), cname))

        while True:
            data = receive(client)
            if not data or data == "EXIT":
                break

            if data.startswith("PUBLIC: "):
                text = data.split("PUBLIC: ", 1)[1].strip()
                if text:
                    broadcast_chat("PUBLIC: [%s] <%s> %s" % (get_timestamp(), cname, text))
    except socket.error as e:
        print("Socket error: %s" % e)
    finally:
        if cname:
            with state_lock:
                clientmap.pop(cname, None)
            broadcast_chat("SYS: [%s] * %s left DaemonDM" % (get_timestamp(), cname))
        client.close()


def tcp_listener(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.listen(10)
    print("Chat listener started on %s port %s" % (host, port))
    while True:
        client, address = sock.accept()
        t = threading.Thread(target=handle_chat_client, args=(client, address), daemon=True)
        t.start()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='DaemonDM Server')
    parser.add_argument('--host', action="store", dest="host", default=SERVER_HOST)
    parser.add_argument('--port', action="store", dest="port", type=int, default=5000)
    given_args = parser.parse_args()

    try:
        tcp_listener(given_args.host, given_args.port)
    except KeyboardInterrupt:
        print("\nShutting down DaemonDM...")