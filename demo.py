"""
demo.py — Run a full end-to-end demo in a single process (no separate terminals needed).
Starts auth service + RPC server in background threads, then fires several client calls.
"""

import sys
import json
import time
import threading
import xmlrpc.server
import xmlrpc.client
sys.path.insert(0, ".")

from common.encryption import AESCipher, RSACipher
from common.token_utils import create_token, verify_token

# ─────────────── Inline servers (same as standalone files) ───────────────
from auth_service.auth_service import AuthService
from server.rpc_server import RPCServer


def start_server(instance, host, port, name):
    srv = xmlrpc.server.SimpleXMLRPCServer((host, port), logRequests=False, allow_none=True)
    srv.register_instance(instance)
    print(f"[{name}] started on {host}:{port}")
    srv.serve_forever()


# ─────────────── Demo calls ───────────────────────────────────────────────

def demo():
    AUTH_URL   = "http://localhost:8001"
    SERVER_URL = "http://localhost:8002"

    print("\n" + "="*60)
    print("  RPC + Authentication Demo  (Python XML-RPC)")
    print("="*60 + "\n")

    auth = xmlrpc.client.ServerProxy(AUTH_URL)
    srv  = xmlrpc.client.ServerProxy(SERVER_URL)

    scenarios = [
        ("alice",  "secret123", "getData",      "symmetric"),
        ("bob",    "pass456",   "ping",          "asymmetric"),
        ("alice",  "secret123", "writeRecord",   "asymmetric"),
        ("admin",  "admin789",  "deleteItem",    "symmetric"),
        ("hacker", "wrong",     "getData",       "symmetric"),   # should fail
    ]

    for user, pwd, method, enc in scenarios:
        print(f"─── {method}() | user={user} | enc={enc} " + "─"*20)
        try:
            if enc == "symmetric":
                key_hex = auth.get_shared_key_hex()
                key     = AESCipher.key_from_hex(key_hex)
                payload = json.dumps({"username": user, "password": pwd, "method": method})
                token   = auth.authenticate_symmetric(AESCipher.encrypt(key, payload))
            else:
                pub_key = RSACipher.load_public_key(auth.get_public_key())
                payload = json.dumps({"username": user, "password": pwd, "method": method})
                token   = auth.authenticate_asymmetric(RSACipher.encrypt(pub_key, payload))

            print(f"  ✓ Token issued: {token[:55]}...")

            if method == "getData":
                result = srv.getData(token)
            elif method == "writeRecord":
                result = srv.writeRecord(token, "demo_record_payload")
            elif method == "deleteItem":
                result = srv.deleteItem(token, 99)
            elif method == "ping":
                result = srv.ping(token)

            print(f"  ✓ Response: {json.dumps(result)[:80]}")

        except xmlrpc.client.Fault as e:
            print(f"  ✗ Fault {e.faultCode}: {e.faultString}")
        print()


if __name__ == "__main__":
    # Start servers in daemon threads
    t1 = threading.Thread(target=start_server, args=(AuthService(), "localhost", 8001, "AuthService"), daemon=True)
    t2 = threading.Thread(target=start_server, args=(RPCServer(),   "localhost", 8002, "RPCServer"),   daemon=True)
    t1.start(); t2.start()
    time.sleep(0.5)   # let servers boot

    demo()
    print("Demo complete.")
