# RPC Authentication System — Python

A clean RPC system built with Python's built-in `xmlrpc` module and the
`cryptography` library.  Matches the whiteboard architecture:

```
Client ──encrypt──► Auth Service ──token──► Server
```

## Project Structure

```
rpc_auth_project/
├── common/
│   ├── encryption.py      # AESCipher (symmetric) + RSACipher (asymmetric)
│   └── token_utils.py     # JWT-like session token (HMAC-SHA256)
├── auth_service/
│   └── auth_service.py    # XML-RPC server on port 8001
├── server/
│   └── rpc_server.py      # XML-RPC server on port 8002
├── client/
│   └── client.py          # Command-line RPC client
├── demo.py                # All-in-one demo (no extra terminals needed)
└── requirements.txt
```

## Install

```bash
pip install -r requirements.txt
```

## Quick Start (single terminal)

```bash
python demo.py
```

This starts both servers in background threads and runs 5 demo calls (symmetric, asymmetric, expected failure).

---

## Manual Start (3 terminals)

**Terminal 1 — Auth Service**
```bash
python auth_service/auth_service.py
```

**Terminal 2 — RPC Server**
```bash
python server/rpc_server.py
```

**Terminal 3 — Client**
```bash
# Symmetric (AES-256)
python client/client.py --user alice --password secret123 --method getData --enc symmetric

# Asymmetric (RSA-2048)
python client/client.py --user bob --password pass456 --method ping --enc asymmetric

# Write a record
python client/client.py --user alice --password secret123 --method writeRecord --enc symmetric --data "my_payload"

# Wrong password (expect rejection)
python client/client.py --user alice --password wrong --method getData --enc symmetric
```

---

## Encryption Modes

| Mode | Algorithm | How it works |
|---|---|---|
| **Symmetric** | AES-256-CBC | Client + Auth Service share a pre-distributed 256-bit key. Credentials are encrypted with AES before sending. |
| **Asymmetric** | RSA-2048 OAEP | Client fetches Auth Service's public key. Credentials are encrypted with it. Auth Service decrypts with its private key. |

## Flow

1. Client encrypts credentials → sends to **Auth Service**
2. Auth Service decrypts, validates against user DB, issues a **session token** (HMAC-SHA256 signed)
3. Client calls method on **RPC Server** with the token
4. RPC Server verifies the token signature + expiry before executing
