# RPC Authentication System — Python

A complete RPC system with authentication, built with Python's `xmlrpc` module, `cryptography`, `SQLAlchemy`, and `Flask`. Demonstrates both symmetric (AES-256) and asymmetric (RSA-2048) encryption for credential transport, with a real database and web frontend.

## Architecture

```
┌──────────┐    encrypt     ┌───────────────┐    token     ┌────────────┐
│  Client   │ ─────────────► │ Auth Service  │ ◄──────────► │  Database   │
│ (Browser/ │  AES or RSA   │  (port 8001)  │  SQLAlchemy  │  (SQLite)   │
│   CLI)    │               └───────┬───────┘              └────────────┘
│           │                       │
│           │         token          │
│           └───────────────────────┘
│           │                       │
│           │    token + args       ▼
│           └────────────────► ┌────────────┐
│                             │ RPC Server  │
│                             │ (port 8002) │
│                             └────────────┘

┌──────────┐     REST API      ┌──────────────┐    XML-RPC     ┌───────────────┐
│  Browser  │ ──────────────► │   Gateway     │ ─────────────► │  Auth Service  │
│           │  /api/login     │  (port 8000)  │                │  + RPC Server  │
│           │  /api/register  │   Flask       │                └───────────────┘
│           │  /api/rpc       └──────────────┘
└──────────┘
```

### Service Breakdown

| Service | Port | Purpose |
|---|---|---|
| **Auth Service** | 8001 | XML-RPC server — register, login, password reset (AES/RSA encrypted) |
| **RPC Server** | 8002 | XML-RPC server — data methods gated by session token |
| **Gateway** | 8000 | Flask REST API — translates browser JSON calls to XML-RPC, serves frontend |

### Data Flow

1. **Register** — Client encrypts `{username, password}` with AES or RSA → Auth Service decrypts → stores hashed password in SQLite → returns success
2. **Login** — Client encrypts `{username, password, method}` → Auth Service decrypts → verifies password hash → issues JWT-like token (HMAC-SHA256 signed, 1-hour TTL)
3. **RPC Call** — Client sends token to RPC Server → server verifies token signature + expiry → executes method → returns result
4. **Password Reset** — Client encrypts `{username, new_password}` → Auth Service decrypts → updates password hash in SQLite

## Project Structure

```
rpc_auth_project/
├── common/
│   ├── encryption.py       # AESCipher (symmetric) + RSACipher (asymmetric)
│   └── token_utils.py      # JWT-like session token (HMAC-SHA256)
├── auth_service/
│   ├── __init__.py
│   ├── db.py               # SQLAlchemy models + helpers (User table, password hashing)
│   └── auth_service.py     # XML-RPC server on port 8001
├── server/
│   ├── __init__.py
│   └── rpc_server.py       # XML-RPC server on port 8002
├── client/
│   ├── __init__.py
│   └── client.py           # Command-line RPC client
├── frontend/
│   ├── index.html           # Browser UI (Register / Login / Reset / RPC)
│   ├── app.js               # Frontend logic (fetch calls to Gateway)
│   └── style.css            # Styles
├── gateway.py               # Flask REST gateway on port 8000
├── run.py                   # Start all 3 services in one terminal
├── seed.py                  # Create default test users
├── demo.py                  # All-in-one CLI demo (single terminal)
├── Makefile                 # make seed / make run / make demo
└── pyproject.toml           # Dependencies + ruff config
```

## Tech Stack

| Layer | Technology |
|---|---|
| RPC Transport | Python `xmlrpc` (built-in) |
| Symmetric Encryption | AES-256-CBC with PKCS7 padding |
| Asymmetric Encryption | RSA-2048 with OAEP+SHA256 |
| Token Signing | HMAC-SHA256 (JWT-like format) |
| Password Hashing | scrypt (via `werkzeug.security`) |
| Database | SQLite via SQLAlchemy 2.0 |
| Web Frontend | Vanilla JS + CSS, served by Flask |
| REST Gateway | Flask |
| Linting/Formatting | Ruff |

## Install

```bash
uv sync
```

Or with pip:

```bash
pip install cryptography flask sqlalchemy
```

## Quick Start

```bash
make install   # install dependencies
make seed      # create test users (alice, bob, admin)
make run       # start all services in one terminal
```

Then open **http://localhost:8000** in your browser. Press Ctrl+C to stop.

### Other commands

```bash
make demo      # run the all-in-one CLI demo (no servers needed)
make clean     # remove the database file
```

### Manual start (3 terminals)

**Terminal 1 — Auth Service**
```bash
uv run python -m auth_service.auth_service
```

**Terminal 2 — RPC Server**
```bash
uv run python -m server.rpc_server
```

**Terminal 3 — Gateway + Frontend**
```bash
uv run python gateway.py
```

**CLI Client** (optional, separate terminal):
```bash
# Symmetric (AES-256)
uv run python client/client.py --user alice --password secret123 --method getData --enc symmetric

# Asymmetric (RSA-2048)
uv run python client/client.py --user bob --password pass456 --method ping --enc asymmetric

# Wrong password (expect rejection)
uv run python client/client.py --user alice --password wrong --method getData --enc symmetric
```

## Encryption Modes

| Mode | Algorithm | How it works |
|---|---|---|
| **Symmetric** | AES-256-CBC | Client + Auth Service share a pre-distributed 256-bit key. Credentials are encrypted with AES before sending. |
| **Asymmetric** | RSA-2048 OAEP | Client fetches Auth Service's public key. Credentials are encrypted with it. Auth Service decrypts with its private key. |

## API Endpoints (Gateway)

| Endpoint | Method | Body | Description |
|---|---|---|---|
| `/api/register` | POST | `{username, password, mode}` | Create a new account |
| `/api/login` | POST | `{username, password, mode, method}` | Authenticate and get a token |
| `/api/reset-password` | POST | `{username, new_password, mode}` | Reset password |
| `/api/rpc` | POST | `{method, token, data?, item_id?}` | Call an RPC method |
| `/api/shared-key` | GET | — | Get AES shared key (hex) |
| `/api/public-key` | GET | — | Get RSA public key (PEM) |

`mode` is `"symmetric"` or `"asymmetric"`.

## Default Users

| Username | Password |
|---|---|
| alice | secret123 |
| bob | pass456 |
| admin | admin789 |

These are seeded automatically on first run. New users can be created via the Register endpoint.

## Database

User data is stored in `users.db` (SQLite). Passwords are hashed with scrypt — never stored in plaintext. The database is created automatically on first run.

## Linting

```bash
uv run --group dev ruff check .
uv run --group dev ruff format .
```