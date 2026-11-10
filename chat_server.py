import socket
import struct
import threading
import argparse
import time

SERVER_HOST = '127.0.0.1'
BUF_SIZE = 4096
LOG_FILE = 'daemondm.log'

#rate limit settings: max 5 messages per 5 seconds, 10s mute
RATE_LIMIT_COUNT = 5
RATE_LIMIT_WINDOW = 5.0
MUTE_SECONDS = 10.0

#sharedstate
state_lock = threading.Lock()
clientmap = {}       # nick -> {"sock": sock, "addr": addr, "lock": Lock, "times": [], "muted": 0}
msg_counter = 0


#framing utilities
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


def log_event(tag, text):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = "[%s] [%s] %s" % (ts, tag, text)
    with state_lock:
        print(line)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def broadcast_chat(msg_str):
    with state_lock:
        targets = [(info["sock"], info["lock"]) for info in clientmap.values()]
    for sock, lock in targets:
        try:
            send(sock, msg_str, lock)
        except socket.error:
            pass


def sync_user_list():
    with state_lock:
        names = ",".join(sorted(clientmap.keys()))
    broadcast_chat("USERS: " + names)


def check_rate_limit(cname):
    now = time.time()
    with state_lock:
        info = clientmap.get(cname)
        if not info:
            return False, "Not connected"
        if now < info["muted"]:
            left = int(info["muted"] - now) + 1
            return False, "Rate limited! Muted for %ds." % left

        info["times"] = [t for t in info["times"] if now - t < RATE_LIMIT_WINDOW]
        if len(info["times"]) >= RATE_LIMIT_COUNT:
            info["muted"] = now + MUTE_SECONDS
            return False, "Spam detected (%d msgs/%ds). Muted for %ds." % (
                RATE_LIMIT_COUNT, int(RATE_LIMIT_WINDOW), int(MUTE_SECONDS)
            )
        info["times"].append(now)
        return True, ""


def handle_chat_client(client, address, is_relay=False):
    global msg_counter
    cname = None
    c_lock = threading.Lock()

    try:
        raw_reg = receive(client)
        if not raw_reg or not raw_reg.startswith("NAME: "):
            send(client, "ERROR: Invalid registration header", c_lock)
            log_event("ERROR", "Bad registration from %s:%s" % (address[0], address[1]))
            client.close()
            return

        req_name = raw_reg.split("NAME: ", 1)[1].strip()
        if not req_name or " " in req_name or len(req_name) > 24:
            send(client, "ERROR: Nickname must be 1-24 chars without spaces.", c_lock)
            log_event("REJECT", "Invalid nickname '%s' from %s" % (req_name, address[0]))
            client.close()
            return

        #enforce * rule
        if not is_relay and req_name.startswith("*"):
            send(client, "ERROR: Prefix '*' is reserved for relay clients.", c_lock)
            log_event("REJECT", "Direct client %s tried using '*' prefix (%s)" % (address[0], req_name))
            client.close()
            return
        if is_relay and (not req_name.startswith("*") or len(req_name) < 2 or req_name[1:].startswith("*")):
            send(client, "ERROR: Relay client must have single '*' prefix.", c_lock)
            log_event("REJECT", "Malformed relay prefix '%s'" % req_name)
            client.close()
            return

        #atomic nickname check & suffix assignment
        with state_lock:
            candidate = req_name
            suffix = 1
            while candidate in clientmap:
                candidate = "%s%d" % (req_name, suffix)
                suffix += 1
            cname = candidate
            clientmap[cname] = {
                "sock": client,
                "addr": address,
                "lock": c_lock,
                "times": [],
                "muted": 0.0
            }

        send(client, "CLIENT: " + cname, c_lock)
        mode_str = "relay" if is_relay else "direct"
        log_event("JOIN", "%s connected (%s) from %s:%s" % (cname, mode_str, address[0], address[1]))

        broadcast_chat("SYS: [%s] * %s joined DaemonDM" % (get_timestamp(), cname))
        sync_user_list()

        while True:
            data = receive(client)
            if not data or data == "EXIT":
                break

            if data.startswith("PUBLIC: ") or data.startswith("PRIVATE: "):
                ok, reason = check_rate_limit(cname)
                if not ok:
                    log_event("RATELIMIT", "%s -> %s" % (cname, reason))
                    send(client, "ERROR: " + reason, c_lock)
                    continue

            if data.startswith("PUBLIC: "):
                text = data.split("PUBLIC: ", 1)[1].strip()
                if not text:
                    continue
                with state_lock:
                    msg_counter += 1
                ts = get_timestamp()
                log_event("PUBLIC", "[%s -> ALL] %s" % (cname, text))
                broadcast_chat("PUBLIC: [%s] <%s> %s" % (ts, cname, text))

            elif data.startswith("PRIVATE: "):
                body = data.split("PRIVATE: ", 1)[1]
                if "|" not in body:
                    send(client, "ERROR: Malformed DM format", c_lock)
                    continue
                target, text = body.split("|", 1)
                target = target.strip()
                text = text.strip()
                if not text:
                    continue

                with state_lock:
                    target_info = clientmap.get(target)
                    if target_info:
                        msg_counter += 1

                ts = get_timestamp()
                if not target_info:
                    log_event("ERROR", "DM failed: %s -> %s (offline)" % (cname, target))
                    send(client, "ERROR: User '%s' is not online." % target, c_lock)
                else:
                    log_event("PRIVATE", "[%s -> %s] %s" % (cname, target, text))
                    send(target_info["sock"], "PRIVATE: [%s] [DM from %s] %s" % (ts, cname, text), target_info["lock"])
                    if target != cname:
                        send(client, "PRIVATE: [%s] [DM to %s] %s" % (ts, target, text), c_lock)
            else:
                send(client, "ERROR: Unknown command", c_lock)
                log_event("ERROR", "Unknown packet from %s: %s" % (cname, data[:40]))

    except ValueError as ve:
        log_event("ERROR", "Protocol error from %s: %s" % (cname or address, ve))
    except socket.error as e:
        log_event("ERROR", "Socket error for %s: %s" % (cname or address, e))
    finally:
        if cname:
            with state_lock:
                clientmap.pop(cname, None)
            log_event("LEAVE", "%s disconnected" % cname)
            broadcast_chat("SYS: [%s] * %s left DaemonDM" % (get_timestamp(), cname))
            sync_user_list()
        try:
            client.close()
        except:
            pass


def tcp_listener(host, port, is_relay=False):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.listen(10)
    print("Chat listener started on %s port %s" % (host, port))
    while True:
        client, address = sock.accept()
        t = threading.Thread(target=handle_chat_client, args=(client, address, is_relay), daemon=True)
        t.start()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='DaemonDM Server')
    parser.add_argument('--host', action="store", dest="host", default=SERVER_HOST)
    parser.add_argument('--port', action="store", dest="port", type=int, default=5000)
    given_args = parser.parse_args()

    try:
        tcp_listener(given_args.host, given_args.port, False)
    except KeyboardInterrupt:
        print("\nShutting down DaemonDM...")