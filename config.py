import os

from dotenv import load_dotenv

load_dotenv()

# ── Database ──────────────────────────────────────────────────────────────────
DB_PATH = os.environ.get("RPC_AUTH_DB_PATH", "users.db")

# ── Cryptographic secrets ─────────────────────────────────────────────────────
SHARED_KEY_HEX = os.environ.get(
    "RPC_AUTH_AES_KEY_HEX",
    "fb28d431bde358571a1dcb7a364f0428f5fc57574f2f51e4fe2181d9044be439",
)
SECRET_KEY = os.environ.get("RPC_AUTH_SECRET_KEY", "rpc_auth_super_secret_2024")

# ── Service URLs / ports ──────────────────────────────────────────────────────
AUTH_HOST = os.environ.get("RPC_AUTH_AUTH_HOST", "localhost")
AUTH_PORT = int(os.environ.get("RPC_AUTH_AUTH_PORT", "8001"))
RPC_HOST = os.environ.get("RPC_AUTH_RPC_HOST", "localhost")
RPC_PORT = int(os.environ.get("RPC_AUTH_RPC_PORT", "8002"))
GATEWAY_HOST = os.environ.get("RPC_AUTH_GATEWAY_HOST", "localhost")
GATEWAY_PORT = int(os.environ.get("RPC_AUTH_GATEWAY_PORT", "8000"))

AUTH_URL = f"http://{AUTH_HOST}:{AUTH_PORT}"
SERVER_URL = f"http://{RPC_HOST}:{RPC_PORT}"

# ── Seed users (comma-separated user:password pairs) ─────────────────────────
_SEED_USERS_RAW = os.environ.get(
    "RPC_AUTH_SEED_USERS", "alice:secret123,bob:pass456,admin:admin789"
)


def get_seed_users() -> list[tuple[str, str]]:
    pairs = []
    for entry in _SEED_USERS_RAW.split(","):
        entry = entry.strip()
        if ":" in entry:
            user, pwd = entry.split(":", 1)
            pairs.append((user.strip(), pwd.strip()))
    return pairs
