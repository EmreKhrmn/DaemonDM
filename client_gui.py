import threading
import tkinter as tk


def run_gui(client, send_fn, recv_fn):
    root = tk.Tk()
    root.title(f"DaemonDM // {client.name}@{client.host}:{client.port}")
    root.geometry("760x480")
    root.configure(bg="#111317")

    header = tk.Label(
        root, text=f" DAEMON_DM :: SESSION [{client.name}] // {client.host}:{client.port}",
        bg="#1a1d24", fg="#50fa7b", font=("Consolas", 10, "bold"), anchor="w", padx=8, pady=6
    )
    header.pack(fill="x")

    main_frame = tk.Frame(root, bg="#111317")
    main_frame.pack(fill="both", expand=True, padx=8, pady=6)

    chat_box = tk.Text(
        main_frame, bg="#0b0c10", fg="#d8dee9", font=("Consolas", 10),
        state="disabled", wrap="word", relief="flat", padx=8, pady=8
    )
    chat_box.tag_config("PUB", foreground="#8be9fd")
    chat_box.tag_config("DM", foreground="#ff79c6")
    chat_box.tag_config("SYS", foreground="#f1fa8c")
    chat_box.tag_config("ERR", foreground="#ff5555")
    chat_box.pack(side="left", fill="both", expand=True)

    side_frame = tk.Frame(main_frame, bg="#161920", width=180)
    side_frame.pack(side="right", fill="y", padx=(8, 0))
    tk.Label(
        side_frame, text="ONLINE PEERS\n(double-click to DM)",
        bg="#161920", fg="#ffb86c", font=("Consolas", 9, "bold"), pady=6
    ).pack(fill="x")

    user_list = tk.Listbox(
        side_frame, bg="#0b0c10", fg="#50fa7b", font=("Consolas", 10),
        selectbackground="#44475a", relief="flat", width=20
    )
    user_list.pack(fill="both", expand=True, padx=4, pady=4)

    bottom = tk.Frame(root, bg="#111317")
    bottom.pack(fill="x", padx=8, pady=(0, 8))

    entry = tk.Entry(
        bottom, bg="#1a1d24", fg="#f8f8f2", insertbackground="#50fa7b",
        font=("Consolas", 10), relief="flat"
    )
    entry.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 6))

    def append_log(text, tag="PUB"):
        chat_box.configure(state="normal")
        chat_box.insert("end", text + "\n", tag)
        chat_box.see("end")
        chat_box.configure(state="disabled")

    def on_close():
        if client.connected:
            try:
                send_fn(client.sock, "EXIT")
            except:
                pass
            client.connected = False
        try:
            client.sock.close()
        except:
            pass
        root.destroy()

    def on_send(event=None):
        txt = entry.get().strip()
        entry.delete(0, "end")
        if not txt:
            return
        if txt.lower() in ("exit", "/exit"):
            on_close()
            return
        try:
            client.handle_command(txt)
        except Exception as e:
            append_log(f"[!] Send failed: {e}", "ERR")

    def on_user_dblclick(event):
        sel = user_list.curselection()
        if sel:
            target = user_list.get(sel[0])
            entry.delete(0, "end")
            entry.insert(0, f"/msg {target} ")
            entry.focus_set()

    user_list.bind("<Double-Button-1>", on_user_dblclick)
    entry.bind("<Return>", on_send)

    tk.Button(
        bottom, text="SEND", command=on_send, bg="#50fa7b", fg="#0b0c10",
        font=("Consolas", 9, "bold"), relief="flat", padx=12
    ).pack(side="left", padx=(0, 4))

    tk.Button(
        bottom, text="EXIT", command=on_close, bg="#ff5555", fg="#f8f8f2",
        font=("Consolas", 9, "bold"), relief="flat", padx=10
    ).pack(side="left")

    def gui_recv_loop():
        while client.connected:
            try:
                data = recv_fn(client.sock)
            except:
                data = ''
            if not data:
                client.connected = False
                root.after(0, append_log, "[!] Server connection closed.", "ERR")
                break

            if data.startswith("USERS: "):
                raw_u = data.split("USERS: ", 1)[1]
                client.users = [u for u in raw_u.split(",") if u]
                def refresh_users():
                    user_list.delete(0, "end")
                    for u in client.users:
                        user_list.insert("end", u)
                root.after(0, refresh_users)
            elif data.startswith("PRIVATE: "):
                root.after(0, append_log, data.split("PRIVATE: ", 1)[1], "DM")
            elif data.startswith("PUBLIC: "):
                root.after(0, append_log, data.split("PUBLIC: ", 1)[1], "PUB")
            elif data.startswith("SYS: "):
                root.after(0, append_log, data.split("SYS: ", 1)[1], "SYS")
            elif data.startswith("ERROR: "):
                root.after(0, append_log, "[!] " + data, "ERR")

    threading.Thread(target=gui_recv_loop, daemon=True).start()
    root.protocol("WM_DELETE_WINDOW", on_close)
    entry.focus_set()
    root.mainloop()