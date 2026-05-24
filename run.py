"""
run.py — Start all services in a single terminal.
Starts Auth Service (8001), RPC Server (8002), and Gateway (8000) together.
Press Ctrl+C to stop all.
"""

import sys
import threading
import xmlrpc.server

sys.path.insert(0, ".")

from auth_service import db
from auth_service.auth_service import AuthService
from server.rpc_server import RPCServer


def start_xmlrpc(instance, host, port, name):
    srv = xmlrpc.server.SimpleXMLRPCServer(
        (host, port), logRequests=False, allow_none=True
    )
    srv.register_instance(instance)
    srv.serve_forever()


if __name__ == "__main__":
    db.init_db()

    threads = [
        threading.Thread(
            target=start_xmlrpc,
            args=(AuthService(), "localhost", 8001, "AuthService"),
            daemon=True,
        ),
        threading.Thread(
            target=start_xmlrpc,
            args=(RPCServer(), "localhost", 8002, "RPCServer"),
            daemon=True,
        ),
    ]

    for t in threads:
        t.start()

    print("[Auth Service]  http://localhost:8001")
    print("[RPC Server]    http://localhost:8002")

    from gateway import app

    print("[Gateway]       http://localhost:8000")
    print("\nOpen http://localhost:8000 in your browser.\n")
    try:
        app.run(host="localhost", port=8000, debug=False)
    except KeyboardInterrupt:
        print("\nShutting down.")
