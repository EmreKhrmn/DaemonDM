import socket
import struct
import sys
import argparse
import threading

SERVER_HOST = '127.0.0.1'
BUF_SIZE = 4096


#some utilities 
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


class ChatClient:
    """A command line chat client using a separate input thread."""
    def __init__(self, name, port, host=SERVER_HOST):
        self.name = name
        self.connected = False
        self.host = host
        self.port = port

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            send(self.sock, 'NAME: ' + self.name)
            data = receive(self.sock)
            if not data or data.startswith("ERROR: "):
                print("Connection refused: %s" % data)
                sys.exit(1)
            if data.startswith("CLIENT: "):
                self.name = data.split("CLIENT: ", 1)[1].strip()
            self.connected = True
            self.prompt = f"[{self.name}@daemondm]> "
            print(f"Now connected to DaemonDM @ {self.host}:{self.port} as '{self.name}'")
        except socket.error as e:
            print(f"Failed to connect to DaemonDM @ {self.host}:{self.port} ({e})")
            sys.exit(1)

    def run_console(self):
        def input_thread():
            while self.connected:
                line = sys.stdin.readline().strip()
                if not line:
                    continue
                if line.lower() in ("exit", "/exit"):
                    send(self.sock, "EXIT")
                    self.connected = False
                    self.sock.close()
                    break
                send(self.sock, "PUBLIC: " + line)

        t = threading.Thread(target=input_thread, daemon=True)
        t.start()

        try:
            while self.connected:
                data = receive(self.sock)
                if not data:
                    print("\nClient shutting down.")
                    self.connected = False
                    break
                sys.stdout.write("\r" + data + "\n" + self.prompt)
                sys.stdout.flush()
        except KeyboardInterrupt:
            print("\nClient interrupted.")
        finally:
            self.sock.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='DaemonDM TCP Client')
    parser.add_argument('--host', action="store", dest="host", default=SERVER_HOST)
    parser.add_argument('--port', action="store", dest="port", type=int, default=5000)
    parser.add_argument('--name', action="store", dest="name", required=True)
    given_args = parser.parse_args()

    client = ChatClient(name=given_args.name, port=given_args.port, host=given_args.host)
    client.run_console()