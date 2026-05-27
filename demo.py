import sys
import json
import time
import threading
import xmlrpc.server
import xmlrpc.client

sys.path.insert(0, ".")

import config
from auth_service import db
from common.encryption import AESCipher, RSACipher

from auth_service.auth_service import AuthService
from server.rpc_server import RPCServer


def start_server(instance, host, port, name):
    srv = xmlrpc.server.SimpleXMLRPCServer(
        (host, port), logRequests=False, allow_none=True
    )
    srv.register_instance(instance)
    print(f"[{name}] started on {host}:{port}")
    srv.serve_forever()


# ─────────────── Demo calls ───────────────────────────────────────────────


def demo():
    AUTH_URL = config.AUTH_URL
    SERVER_URL = config.SERVER_URL

    print("\n" + "=" * 60)
    print("  RPC + Authentication Demo  (Python XML-RPC)")
    print("=" * 60 + "\n")

    auth = xmlrpc.client.ServerProxy(AUTH_URL)
    srv = xmlrpc.client.ServerProxy(SERVER_URL)

    # ── 1. Register a new user ───────────────────────────────────────────
    print("─── REGISTER | user=charlie | enc=symmetric " + "─" * 20)
    try:
        key_hex = auth.get_shared_key_hex()
        key = AESCipher.key_from_hex(key_hex)
        payload = json.dumps(
            {"username": "charlie", "password": "charlie789", "method": "register"}
        )
        result = auth.register_symmetric(AESCipher.encrypt(key, payload))
        print(f"  ✓ Registered: {result}")
    except xmlrpc.client.Fault as e:
        print(f"  ✗ Fault {e.faultCode}: {e.faultString}")
    print()

    # ── 2. Register another user (asymmetric) ────────────────────────────
    print("─── REGISTER | user=diana | enc=asymmetric " + "─" * 20)
    try:
        pub_key = RSACipher.load_public_key(auth.get_public_key())
        payload = json.dumps(
            {"username": "diana", "password": "diana321", "method": "register"}
        )
        result = auth.register_asymmetric(RSACipher.encrypt(pub_key, payload))
        print(f"  ✓ Registered: {result}")
    except xmlrpc.client.Fault as e:
        print(f"  ✗ Fault {e.faultCode}: {e.faultString}")
    print()

    # ── 3. Try duplicate registration (should fail) ──────────────────────
    print("─── REGISTER DUPLICATE | user=charlie | enc=symmetric " + "─" * 10)
    try:
        key_hex = auth.get_shared_key_hex()
        key = AESCipher.key_from_hex(key_hex)
        payload = json.dumps(
            {"username": "charlie", "password": "whatever", "method": "register"}
        )
        result = auth.register_symmetric(AESCipher.encrypt(key, payload))
        print(f"  ✗ Unexpected success: {result}")
    except xmlrpc.client.Fault as e:
        print(f"  ✓ Correctly rejected: Fault {e.faultCode}: {e.faultString}")
    print()

    # ── 4. Login with newly registered user ─────────────────────────────
    print("─── getData() | user=charlie (new) | enc=symmetric " + "─" * 10)
    try:
        key_hex = auth.get_shared_key_hex()
        key = AESCipher.key_from_hex(key_hex)
        payload = json.dumps(
            {"username": "charlie", "password": "charlie789", "method": "getData"}
        )
        token = auth.authenticate_symmetric(AESCipher.encrypt(key, payload))
        print(f"  ✓ Token issued: {token[:55]}...")
        result = srv.getData(token)
        print(f"  ✓ Response: {json.dumps(result)[:80]}")
    except xmlrpc.client.Fault as e:
        print(f"  ✗ Fault {e.faultCode}: {e.faultString}")
    print()

    # ── 5. Reset password ──────────────────────────────────────────────
    print("─── RESET PASSWORD | user=charlie | enc=symmetric " + "─" * 10)
    try:
        key_hex = auth.get_shared_key_hex()
        key = AESCipher.key_from_hex(key_hex)
        payload = json.dumps({"username": "charlie", "new_password": "newCharlie999"})
        result = auth.reset_password_symmetric(AESCipher.encrypt(key, payload))
        print(f"  ✓ Password reset: {result}")
    except xmlrpc.client.Fault as e:
        print(f"  ✗ Fault {e.faultCode}: {e.faultString}")
    print()

    # ── 6. Login with new password (should work) ────────────────────────
    print("─── getData() | user=charlie (new pass) | enc=symmetric " + "─" * 5)
    try:
        key_hex = auth.get_shared_key_hex()
        key = AESCipher.key_from_hex(key_hex)
        payload = json.dumps(
            {"username": "charlie", "password": "newCharlie999", "method": "getData"}
        )
        token = auth.authenticate_symmetric(AESCipher.encrypt(key, payload))
        print(f"  ✓ Token issued: {token[:55]}...")
        result = srv.getData(token)
        print(f"  ✓ Response: {json.dumps(result)[:80]}")
    except xmlrpc.client.Fault as e:
        print(f"  ✗ Fault {e.faultCode}: {e.faultString}")
    print()

    # ── 7. Login with old password (should fail) ────────────────────────
    print("─── getData() | user=charlie (old pass) | enc=symmetric " + "─" * 5)
    try:
        key_hex = auth.get_shared_key_hex()
        key = AESCipher.key_from_hex(key_hex)
        payload = json.dumps(
            {"username": "charlie", "password": "charlie789", "method": "getData"}
        )
        token = auth.authenticate_symmetric(AESCipher.encrypt(key, payload))
        print(f"  ✗ Unexpected success: {token[:55]}...")
    except xmlrpc.client.Fault as e:
        print(f"  ✓ Correctly rejected: Fault {e.faultCode}: {e.faultString}")
    print()

    # ── 8. Reset password (asymmetric) ─────────────────────────────────
    print("─── RESET PASSWORD | user=diana | enc=asymmetric " + "─" * 10)
    try:
        pub_key = RSACipher.load_public_key(auth.get_public_key())
        payload = json.dumps({"username": "diana", "new_password": "newDiana777"})
        result = auth.reset_password_asymmetric(RSACipher.encrypt(pub_key, payload))
        print(f"  ✓ Password reset: {result}")
    except xmlrpc.client.Fault as e:
        print(f"  ✗ Fault {e.faultCode}: {e.faultString}")
    print()

    # ── 9. Existing users ───────────────────────────────────────────────
    scenarios = [
        ("alice", "secret123", "getData", "symmetric"),
        ("bob", "pass456", "ping", "asymmetric"),
        ("alice", "secret123", "writeRecord", "asymmetric"),
        ("admin", "admin789", "deleteItem", "symmetric"),
        ("hacker", "wrong", "getData", "symmetric"),
    ]

    for user, pwd, method, enc in scenarios:
        print(f"─── {method}() | user={user} | enc={enc} " + "─" * 20)
        try:
            if enc == "symmetric":
                key_hex = auth.get_shared_key_hex()
                key = AESCipher.key_from_hex(key_hex)
                payload = json.dumps(
                    {"username": user, "password": pwd, "method": method}
                )
                token = auth.authenticate_symmetric(AESCipher.encrypt(key, payload))
            else:
                pub_key = RSACipher.load_public_key(auth.get_public_key())
                payload = json.dumps(
                    {"username": user, "password": pwd, "method": method}
                )
                token = auth.authenticate_asymmetric(
                    RSACipher.encrypt(pub_key, payload)
                )

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
    db.init_db()

    t1 = threading.Thread(
        target=start_server,
        args=(AuthService(), config.AUTH_HOST, config.AUTH_PORT, "AuthService"),
        daemon=True,
    )
    t2 = threading.Thread(
        target=start_server,
        args=(RPCServer(), config.RPC_HOST, config.RPC_PORT, "RPCServer"),
        daemon=True,
    )
    t1.start()
    t2.start()
    time.sleep(0.5)

    demo()
    print("Demo complete.")
