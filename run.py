"""
run.py — Start all services in a single terminal.
Starts Auth Service (8001), RPC Server (8002), and Gateway (8000) together.
Press Ctrl+C to stop all.
"""

import sys
import threading
import xmlrpc.server

sys.path.insert(0, ".")

import config
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
            args=(AuthService(), config.AUTH_HOST, config.AUTH_PORT, "AuthService"),
            daemon=True,
        ),
        threading.Thread(
            target=start_xmlrpc,
            args=(RPCServer(), config.RPC_HOST, config.RPC_PORT, "RPCServer"),
            daemon=True,
        ),
    ]

    for t in threads:
        t.start()

    print(f"[Auth Service]  http://{config.AUTH_HOST}:{config.AUTH_PORT}")
    print(f"[RPC Server]    http://{config.RPC_HOST}:{config.RPC_PORT}")

    from gateway import app

    print(f"[Gateway]       http://{config.GATEWAY_HOST}:{config.GATEWAY_PORT}")
    print(
        f"\nOpen http://{config.GATEWAY_HOST}:{config.GATEWAY_PORT} in your browser.\n"
    )
    try:
        app.run(host=config.GATEWAY_HOST, port=config.GATEWAY_PORT, debug=False)
    except KeyboardInterrupt:
        print("\nShutting down.")
