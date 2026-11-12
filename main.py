import subprocess
import sys
import webbrowser
import tkinter as tk

py = sys.executable
procs = {"server": None, "relay": None, "clients": []}


def start_launcher():
    root = tk.Tk()
    root.title("DaemonDM // Control Deck")
    root.geometry("500x430")
    root.configure(bg="#0d0f12")
    root.resizable(False, False)

    #top title banner
    tk.Label(
        root, text="DAEMON_DM :: CONTROL DECK",
        bg="#14171d", fg="#50fa7b", font=("Consolas", 12, "bold"),
        anchor="w", padx=14, pady=10
    ).pack(fill="x")

    body = tk.Frame(root, bg="#0d0f12", padx=16, pady=12)
    body.pack(fill="both", expand=True)

    #server&web monitor section
    srv_frame = tk.Frame(body, bg="#14171d", padx=12, pady=10)
    srv_frame.pack(fill="x", pady=(0, 10))

    srv_status = tk.Label(
        srv_frame, text="SERVER DAEMON: OFFLINE",
        bg="#14171d", fg="#ff5555", font=("Consolas", 10, "bold"), anchor="w"
    )
    srv_status.pack(fill="x", pady=(0, 8))

    srv_btns = tk.Frame(srv_frame, bg="#14171d")
    srv_btns.pack(fill="x")

    def toggle_server():
        if procs["server"] and procs["server"].poll() is None:
            procs["server"].terminate()
            procs["server"] = None
            srv_status.config(text="SERVER DAEMON: OFFLINE", fg="#ff5555")
            btn_srv.config(text="START SERVER", bg="#50fa7b", fg="#0b0c10")
        else:
            procs["server"] = subprocess.Popen([py, "chat_server.py"])
            srv_status.config(text="SERVER DAEMON: ONLINE (TCP:5000 / WS:8765)", fg="#50fa7b")
            btn_srv.config(text="STOP SERVER", bg="#ff5555", fg="#f8f8f2")

    def open_monitor():
        webbrowser.open("http://127.0.0.1:8000")

    btn_srv = tk.Button(
        srv_btns, text="START SERVER", command=toggle_server,
        bg="#50fa7b", fg="#0b0c10", font=("Consolas", 9, "bold"),
        relief="flat", padx=12, pady=5
    )
    btn_srv.pack(side="left", padx=(0, 8))

    tk.Button(
        srv_btns, text="OPEN WEB MONITOR (8000)", command=open_monitor,
        bg="#8be9fd", fg="#0b0c10", font=("Consolas", 9, "bold"),
        relief="flat", padx=12, pady=5
    ).pack(side="left")

    #optional relay section
    relay_frame = tk.Frame(body, bg="#14171d", padx=12, pady=10)
    relay_frame.pack(fill="x", pady=(0, 10))

    relay_status = tk.Label(
        relay_frame, text="CHAT RELAY (* prefix): OFFLINE",
        bg="#14171d", fg="#6272a4", font=("Consolas", 10, "bold"), anchor="w"
    )
    relay_status.pack(fill="x", pady=(0, 8))

    def toggle_relay():
        if procs["relay"] and procs["relay"].poll() is None:
            procs["relay"].terminate()
            procs["relay"] = None
            relay_status.config(text="CHAT RELAY (* prefix): OFFLINE", fg="#6272a4")
            btn_relay.config(text="START RELAY (6000)", bg="#ffb86c", fg="#0b0c10")
        else:
            procs["relay"] = subprocess.Popen([py, "chat_relay.py"])
            relay_status.config(text="CHAT RELAY (* prefix): ONLINE (PORT 6000)", fg="#ffb86c")
            btn_relay.config(text="STOP RELAY", bg="#ff5555", fg="#f8f8f2")

    btn_relay = tk.Button(
        relay_frame, text="START RELAY (6000)", command=toggle_relay,
        bg="#ffb86c", fg="#0b0c10", font=("Consolas", 9, "bold"),
        relief="flat", padx=12, pady=5
    )
    btn_relay.pack(anchor="w")

    #spawn client section
    cli_frame = tk.Frame(body, bg="#14171d", padx=12, pady=10)
    cli_frame.pack(fill="x")

    tk.Label(
        cli_frame, text="SPAWN CLIENT SESSION",
        bg="#14171d", fg="#f1fa8c", font=("Consolas", 10, "bold"), anchor="w"
    ).pack(fill="x", pady=(0, 8))

    row1 = tk.Frame(cli_frame, bg="#14171d")
    row1.pack(fill="x", pady=(0, 8))

    tk.Label(row1, text="Nickname:", bg="#14171d", fg="#c5c8c6", font=("Consolas", 10)).pack(side="left")
    nick_entry = tk.Entry(
        row1, bg="#0d0f12", fg="#50fa7b", insertbackground="#50fa7b",
        font=("Consolas", 10), relief="flat", width=18
    )
    nick_entry.insert(0, "user1")
    nick_entry.pack(side="left", padx=8, ipady=4)

    use_relay_var = tk.BooleanVar(value=False)
    tk.Checkbutton(
        row1, text="Via Relay (6000)", variable=use_relay_var,
        bg="#14171d", fg="#ffb86c", selectcolor="#0d0f12",
        activebackground="#14171d", activeforeground="#ffb86c",
        font=("Consolas", 9)
    ).pack(side="left")

    def spawn_gui_client():
        name = nick_entry.get().strip() or "user"
        port = "6000" if use_relay_var.get() else "5000"
        p = subprocess.Popen([py, "chat_client.py", "--name", name, "--port", port, "--gui"])
        procs["clients"].append(p)

    tk.Button(
        cli_frame, text="LAUNCH DARK GUI CLIENT", command=spawn_gui_client,
        bg="#ff79c6", fg="#0b0c10", font=("Consolas", 9, "bold"),
        relief="flat", padx=12, pady=6
    ).pack(fill="x")

    def on_exit():
        for key in ("server", "relay"):
            if procs[key] and procs[key].poll() is None:
                procs[key].terminate()
        for c in procs["clients"]:
            if c.poll() is None:
                c.terminate()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_exit)
    root.mainloop()


if __name__ == "__main__":
    start_launcher()