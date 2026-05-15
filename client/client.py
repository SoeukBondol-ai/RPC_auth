"""
RPC Client
Usage:
    python client.py --user alice --password secret123 --method getData --enc symmetric
    python client.py --user bob   --password pass456   --method ping    --enc asymmetric
"""

import sys
import json
import argparse
import xmlrpc.client
sys.path.insert(0, "..")

from common.encryption import AESCipher, RSACipher

AUTH_URL   = "http://localhost:8001"
SERVER_URL = "http://localhost:8002"


def authenticate_symmetric(username: str, password: str, method: str) -> str:
    auth   = xmlrpc.client.ServerProxy(AUTH_URL)
    key_hex = auth.get_shared_key_hex()
    key    = AESCipher.key_from_hex(key_hex)

    payload    = json.dumps({"username": username, "password": password, "method": method})
    enc_creds  = AESCipher.encrypt(key, payload)
    print(f"[Client] AES-encrypted credentials: {enc_creds[:48]}...")

    token = auth.authenticate_symmetric(enc_creds)
    print(f"[Client] Session token (symmetric): {token[:60]}...")
    return token


def authenticate_asymmetric(username: str, password: str, method: str) -> str:
    auth       = xmlrpc.client.ServerProxy(AUTH_URL)
    pub_pem    = auth.get_public_key()
    public_key = RSACipher.load_public_key(pub_pem)

    payload   = json.dumps({"username": username, "password": password, "method": method})
    enc_creds = RSACipher.encrypt(public_key, payload)
    print(f"[Client] RSA-encrypted credentials: {enc_creds[:48]}...")

    token = auth.authenticate_asymmetric(enc_creds)
    print(f"[Client] Session token (asymmetric): {token[:60]}...")
    return token


def call_rpc(method: str, token: str, **kwargs):
    srv = xmlrpc.client.ServerProxy(SERVER_URL)
    rpc = getattr(srv, method)

    if method == "getData":
        return rpc(token)
    elif method == "writeRecord":
        data = kwargs.get("data", "sample_data_payload")
        return rpc(token, data)
    elif method == "deleteItem":
        item_id = int(kwargs.get("item_id", 42))
        return rpc(token, item_id)
    elif method == "ping":
        return rpc(token)
    else:
        raise ValueError(f"Unknown method: {method}")


def main():
    parser = argparse.ArgumentParser(description="RPC Client with Auth")
    parser.add_argument("--user",     default="alice",     help="Username")
    parser.add_argument("--password", default="secret123", help="Password")
    parser.add_argument("--method",   default="getData",
                        choices=["getData", "writeRecord", "deleteItem", "ping"])
    parser.add_argument("--enc",      default="symmetric",
                        choices=["symmetric", "asymmetric"],
                        help="Encryption mode")
    parser.add_argument("--data",     default="hello_world", help="Data for writeRecord")
    parser.add_argument("--item-id",  default="1",           help="Item ID for deleteItem")
    args = parser.parse_args()

    print(f"\n{'='*55}")
    print(f" RPC Call  : {args.method}()")
    print(f" User      : {args.user}")
    print(f" Encryption: {args.enc}")
    print(f"{'='*55}\n")

    try:
        if args.enc == "symmetric":
            token = authenticate_symmetric(args.user, args.password, args.method)
        else:
            token = authenticate_asymmetric(args.user, args.password, args.method)

        result = call_rpc(args.method, token, data=args.data, item_id=args.item_id)
        print(f"\n[Client] ✓ RPC response:\n{json.dumps(result, indent=2)}\n")

    except xmlrpc.client.Fault as e:
        print(f"\n[Client] ✗ RPC Fault {e.faultCode}: {e.faultString}\n")
    except ConnectionRefusedError:
        print("\n[Client] ✗ Connection refused — are auth_service.py and rpc_server.py running?\n")


if __name__ == "__main__":
    main()
