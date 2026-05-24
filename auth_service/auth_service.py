import sys
import json
import xmlrpc.server

sys.path.insert(0, "..")

from auth_service import db
from common.encryption import AESCipher, RSACipher
from common.token_utils import create_token

# ── Pre-shared AES key (hex) – in real life distribute via secure channel ──
_SHARED_KEY_HEX = "fb28d431bde358571a1dcb7a364f0428f5fc57574f2f51e4fe2181d9044be439"
_SHARED_KEY = AESCipher.key_from_hex(_SHARED_KEY_HEX)

# ── RSA keypair owned by auth service ──
_PRIVATE_KEY, _PUBLIC_KEY = RSACipher.generate_keypair()
_PUBLIC_KEY_PEM = RSACipher.serialize_public_key(_PUBLIC_KEY)


class AuthService:
    # ── Symmetric path ─────────────────────────────────────────────────────
    def authenticate_symmetric(self, encrypted_creds: str) -> str:
        try:
            raw = AESCipher.decrypt(_SHARED_KEY, encrypted_creds)
            creds = json.loads(raw)
        except Exception as exc:
            raise xmlrpc.client.Fault(401, f"Decryption failed: {exc}")

        username = creds.get("username", "")
        password = creds.get("password", "")
        method = creds.get("method", "unknown")

        print(f"[AuthService] SYMMETRIC — user='{username}' method='{method}'")

        if not db.verify_password(username, password):
            raise xmlrpc.client.Fault(403, "Invalid credentials")

        token = create_token(username, method, "symmetric")
        print(f"[AuthService] Token issued for '{username}'")
        return token

    # ── Asymmetric path ────────────────────────────────────────────────────
    def authenticate_asymmetric(self, encrypted_creds: str) -> str:
        try:
            raw = RSACipher.decrypt(_PRIVATE_KEY, encrypted_creds)
            creds = json.loads(raw)
        except Exception as exc:
            raise xmlrpc.client.Fault(401, f"Decryption failed: {exc}")

        username = creds.get("username", "")
        password = creds.get("password", "")
        method = creds.get("method", "unknown")

        print(f"[AuthService] ASYMMETRIC — user='{username}' method='{method}'")

        if not db.verify_password(username, password):
            raise xmlrpc.client.Fault(403, "Invalid credentials")

        token = create_token(username, method, "asymmetric")
        print(f"[AuthService] Token issued for '{username}'")
        return token

    # ── Registration ───────────────────────────────────────────────────────
    def register_symmetric(self, encrypted_creds: str) -> str:
        try:
            raw = AESCipher.decrypt(_SHARED_KEY, encrypted_creds)
            creds = json.loads(raw)
        except Exception as exc:
            raise xmlrpc.client.Fault(401, f"Decryption failed: {exc}")

        username = creds.get("username", "").strip()
        password = creds.get("password", "")

        print(f"[AuthService] REGISTER SYMMETRIC — user='{username}'")

        if not username or not password:
            raise xmlrpc.client.Fault(400, "Username and password are required")
        if db.user_exists(username):
            raise xmlrpc.client.Fault(409, f"User '{username}' already exists")

        db.create_user(username, password)
        print(f"[AuthService] User '{username}' registered (symmetric)")
        return json.dumps({"status": "registered", "username": username})

    def register_asymmetric(self, encrypted_creds: str) -> str:
        try:
            raw = RSACipher.decrypt(_PRIVATE_KEY, encrypted_creds)
            creds = json.loads(raw)
        except Exception as exc:
            raise xmlrpc.client.Fault(401, f"Decryption failed: {exc}")

        username = creds.get("username", "").strip()
        password = creds.get("password", "")

        print(f"[AuthService] REGISTER ASYMMETRIC — user='{username}'")

        if not username or not password:
            raise xmlrpc.client.Fault(400, "Username and password are required")
        if db.user_exists(username):
            raise xmlrpc.client.Fault(409, f"User '{username}' already exists")

        db.create_user(username, password)
        print(f"[AuthService] User '{username}' registered (asymmetric)")
        return json.dumps({"status": "registered", "username": username})

    # ── Password reset ────────────────────────────────────────────────────
    def reset_password_symmetric(self, encrypted_creds: str) -> str:
        try:
            raw = AESCipher.decrypt(_SHARED_KEY, encrypted_creds)
            creds = json.loads(raw)
        except Exception as exc:
            raise xmlrpc.client.Fault(401, f"Decryption failed: {exc}")

        username = creds.get("username", "").strip()
        new_password = creds.get("new_password", "")

        print(f"[AuthService] RESET PASSWORD SYMMETRIC — user='{username}'")

        if not username or not new_password:
            raise xmlrpc.client.Fault(400, "Username and new password are required")
        if not db.reset_password(username, new_password):
            raise xmlrpc.client.Fault(404, f"User '{username}' not found")

        print(f"[AuthService] Password reset for '{username}' (symmetric)")
        return json.dumps({"status": "password_reset", "username": username})

    def reset_password_asymmetric(self, encrypted_creds: str) -> str:
        try:
            raw = RSACipher.decrypt(_PRIVATE_KEY, encrypted_creds)
            creds = json.loads(raw)
        except Exception as exc:
            raise xmlrpc.client.Fault(401, f"Decryption failed: {exc}")

        username = creds.get("username", "").strip()
        new_password = creds.get("new_password", "")

        print(f"[AuthService] RESET PASSWORD ASYMMETRIC — user='{username}'")

        if not username or not new_password:
            raise xmlrpc.client.Fault(400, "Username and new password are required")
        if not db.reset_password(username, new_password):
            raise xmlrpc.client.Fault(404, f"User '{username}' not found")

        print(f"[AuthService] Password reset for '{username}' (asymmetric)")
        return json.dumps({"status": "password_reset", "username": username})

    # ── Key exchange ───────────────────────────────────────────────────────
    def get_public_key(self) -> str:
        return _PUBLIC_KEY_PEM

    def get_shared_key_hex(self) -> str:
        return _SHARED_KEY_HEX


if __name__ == "__main__":
    import xmlrpc.client  # noqa – needed for Fault

    db.init_db()
    HOST, PORT = "localhost", 8001
    server = xmlrpc.server.SimpleXMLRPCServer(
        (HOST, PORT), logRequests=False, allow_none=True
    )
    server.register_instance(AuthService())
    server.register_introspection_functions()
    print(f"[AuthService] Listening on {HOST}:{PORT} ...")
    print(f"[AuthService] Shared AES key: {_SHARED_KEY_HEX}")
    print(f"[AuthService] RSA public key:\n{_PUBLIC_KEY_PEM}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[AuthService] Shutting down.")
