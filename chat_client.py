import socket
import struct
import sys
import argparse
import threading
import colorama 

try:
    from colorama import init as colorama_init, Fore, Style
    colorama_init()
except ImportError:
    class _Dummy:
        RESET_ALL = RED = GREEN = YELLOW = CYAN = MAGENTA = ""
    Fore = Style = _Dummy()

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
    """DaemonDM TCP client."""
    def __init__(self, name, port, host=SERVER_HOST):
        self.name = name
        self.connected = False
        self.host = host
        self.port = port
        self.users = []

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            send(self.sock, 'NAME: ' + self.name)
            data = receive(self.sock)
            if not data or data.startswith("ERROR: "):
                print(Fore.RED + "Connection refused: %s" % data + Style.RESET_ALL)
                sys.exit(1)
            if data.startswith("CLIENT: "):
                self.name = data.split("CLIENT: ", 1)[1].strip()
            self.connected = True
            self.prompt = f"{Fore.GREEN}[{self.name}@daemondm]>{Style.RESET_ALL} "
            print(Fore.CYAN + f"=== Connected to DaemonDM ({self.host}:{self.port}) as '{self.name}' ===" + Style.RESET_ALL)
            print("Commands: /users | /msg <nick> <text> | /to <num> <text> | exit")
        except socket.error as e:
            print(f"Failed to connect to DaemonDM @ {self.host}:{self.port} ({e})")
            sys.exit(1)

    def handle_command(self, line):
        line = line.strip()
        if not line:
            return
        if line.lower() in ("exit", "/exit"):
            send(self.sock, "EXIT")
            self.connected = False
            self.sock.close()
        elif line.lower() == "/users":
            print(Fore.YELLOW + "Online: " + ", ".join(f"[{i+1}] {u}" for i, u in enumerate(self.users)) + Style.RESET_ALL)
        elif line.startswith("/msg "):
            parts = line.split(" ", 2)
            if len(parts) < 3:
                print("Usage: /msg <nickname> <message>")
                return
            send(self.sock, f"PRIVATE: {parts[1]}|{parts[2]}")
        elif line.startswith("/to "):
            parts = line.split(" ", 2)
            if len(parts) < 3 or not parts[1].isdigit():
                print("Usage: /to <number> <message>")
                return
            idx = int(parts[1]) - 1
            if 0 <= idx < len(self.users):
                send(self.sock, f"PRIVATE: {self.users[idx]}|{parts[2]}")
            else:
                print("Invalid user number. Use /users first.")
        else:
            send(self.sock, "PUBLIC: " + line)

    def run_console(self):
        def input_thread():
            while self.connected:
                try:
                    line = sys.stdin.readline()
                    if not line:
                        break
                    self.handle_command(line)
                except:
                    break

        t = threading.Thread(target=input_thread, daemon=True)
        t.start()

        try:
            while self.connected:
                data = receive(self.sock)
                if not data:
                    print("\n" + Fore.RED + "[!] Disconnected from DaemonDM server." + Style.RESET_ALL)
                    self.connected = False
                    break

                if data.startswith("USERS: "):
                    raw_u = data.split("USERS: ", 1)[1]
                    self.users = [u for u in raw_u.split(",") if u]
                    u_str = ", ".join(f"{i+1}:{u}" for i, u in enumerate(self.users))
                    out = Fore.YELLOW + f"[peers ({len(self.users)})]: {u_str}" + Style.RESET_ALL
                elif data.startswith("PRIVATE: "):
                    out = Fore.MAGENTA + data.split("PRIVATE: ", 1)[1] + Style.RESET_ALL
                elif data.startswith("PUBLIC: "):
                    out = Fore.CYAN + data.split("PUBLIC: ", 1)[1] + Style.RESET_ALL
                elif data.startswith("SYS: "):
                    out = Fore.YELLOW + data.split("SYS: ", 1)[1] + Style.RESET_ALL
                elif data.startswith("ERROR: "):
                    out = Fore.RED + "[!] " + data + Style.RESET_ALL
                else:
                    out = data

                sys.stdout.write("\r" + out + "\n" + self.prompt)
                sys.stdout.flush()
        except KeyboardInterrupt:
            print("\nInterrupted.")
        finally:
            self.sock.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='DaemonDM TCP Client')
    parser.add_argument('--host', action="store", dest="host", default=None)
    parser.add_argument('--port', action="store", dest="port", type=int, default=None)
    parser.add_argument('--name', action="store", dest="name", default=None)
    parser.add_argument('--gui', action="store_true", dest="gui", help="Launch Tkinter dark GUI")
    given_args = parser.parse_args()

    host = given_args.host or input("Server IP [127.0.0.1]: ").strip() or SERVER_HOST
    port = given_args.port or int(input("Port [5000]: ").strip() or "5000")
    name = given_args.name or input("Nickname: ").strip()

    client = ChatClient(name=name, port=port, host=host)
    if given_args.gui:
        import client_gui
        client_gui.run_gui(client, send, receive)
    else:
        client.run_console()