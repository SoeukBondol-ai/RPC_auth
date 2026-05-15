"""
Authentication Service — XML-RPC server on port 8001
Endpoints:
  authenticate_symmetric(encrypted_credentials: str) -> str  (session token)
  authenticate_asymmetric(encrypted_credentials: str) -> str (session token)
  get_public_key()                                   -> str  (PEM)
"""

import sys
import json
import xmlrpc.server
sys.path.insert(0, "..")

from common.encryption import AESCipher, RSACipher
from common.token_utils import create_token

# ── Pre-shared AES key (hex) – in real life distribute via secure channel ──
_SHARED_KEY_HEX = "fb28d431bde358571a1dcb7a364f0428f5fc57574f2f51e4fe2181d9044be439"
_SHARED_KEY     = AESCipher.key_from_hex(_SHARED_KEY_HEX)

# ── RSA keypair owned by auth service ──
_PRIVATE_KEY, _PUBLIC_KEY = RSACipher.generate_keypair()
_PUBLIC_KEY_PEM = RSACipher.serialize_public_key(_PUBLIC_KEY)

# ── User store (password hashes in production!) ──
USER_DB = {
    "alice": "secret123",
    "bob":   "pass456",
    "admin": "admin789",
}


def _validate_credentials(username: str, password: str) -> bool:
    return USER_DB.get(username) == password


class AuthService:

    # ── Symmetric path ─────────────────────────────────────────────────────
    def authenticate_symmetric(self, encrypted_creds: str) -> str:
        """
        Client sends JSON credentials encrypted with the shared AES key.
        Returns a session token on success, raises Fault on failure.
        """
        try:
            raw   = AESCipher.decrypt(_SHARED_KEY, encrypted_creds)
            creds = json.loads(raw)
        except Exception as exc:
            raise xmlrpc.client.Fault(401, f"Decryption failed: {exc}")

        username = creds.get("username", "")
        password = creds.get("password", "")
        method   = creds.get("method", "unknown")

        print(f"[AuthService] SYMMETRIC — user='{username}' method='{method}'")

        if not _validate_credentials(username, password):
            raise xmlrpc.client.Fault(403, "Invalid credentials")

        token = create_token(username, method, "symmetric")
        print(f"[AuthService] Token issued for '{username}'")
        return token

    # ── Asymmetric path ────────────────────────────────────────────────────
    def authenticate_asymmetric(self, encrypted_creds: str) -> str:
        """
        Client encrypts JSON credentials with the auth service's public key.
        Returns a session token on success.
        """
        try:
            raw   = RSACipher.decrypt(_PRIVATE_KEY, encrypted_creds)
            creds = json.loads(raw)
        except Exception as exc:
            raise xmlrpc.client.Fault(401, f"Decryption failed: {exc}")

        username = creds.get("username", "")
        password = creds.get("password", "")
        method   = creds.get("method", "unknown")

        print(f"[AuthService] ASYMMETRIC — user='{username}' method='{method}'")

        if not _validate_credentials(username, password):
            raise xmlrpc.client.Fault(403, "Invalid credentials")

        token = create_token(username, method, "asymmetric")
        print(f"[AuthService] Token issued for '{username}'")
        return token

    # ── Key exchange ───────────────────────────────────────────────────────
    def get_public_key(self) -> str:
        """Return the RSA public key (PEM) so clients can encrypt credentials."""
        return _PUBLIC_KEY_PEM

    def get_shared_key_hex(self) -> str:
        """
        Return the pre-shared AES key hex for demo purposes.
        (In production, distribute this out-of-band!)
        """
        return _SHARED_KEY_HEX


if __name__ == "__main__":
    import xmlrpc.client  # noqa – needed for Fault
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
