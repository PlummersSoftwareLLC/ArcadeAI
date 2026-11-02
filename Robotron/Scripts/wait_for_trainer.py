import socket,time
for _ in range(600):
    try:
        with socket.create_connection(("127.0.0.1",9998),1):
            break
    except OSError:
        time.sleep(1)
else:
    raise SystemExit("Trainer did not start listening")
