import sys
import time
import xmlrpc.server
import xmlrpc.client

sys.path.insert(0, "..")

from common.token_utils import verify_token


def _require_auth(token: str) -> dict:
    """Verify token; raise Fault if invalid or expired."""
    payload = verify_token(token)
    if payload is None:
        raise xmlrpc.client.Fault(401, "Invalid or expired session token")
    return payload


class RPCServer:
    def getData(self, token: str) -> dict:
        payload = _require_auth(token)
        print(f"[RPCServer] getData() called by '{payload['sub']}'")
        return {
            "status": "ok",
            "user": payload["sub"],
            "records": [
                {"id": 1, "value": "record_alpha"},
                {"id": 2, "value": "record_beta"},
                {"id": 3, "value": "record_gamma"},
            ],
        }

    def writeRecord(self, token: str, data: str) -> dict:
        payload = _require_auth(token)
        new_id = int(time.time()) % 100000
        print(f"[RPCServer] writeRecord() by '{payload['sub']}': {data}")
        return {"status": "written", "id": new_id, "data": data}

    def deleteItem(self, token: str, item_id: int) -> dict:
        payload = _require_auth(token)
        print(f"[RPCServer] deleteItem({item_id}) by '{payload['sub']}'")
        return {"status": "deleted", "item_id": item_id, "affected": 1}

    def ping(self, token: str) -> dict:
        payload = _require_auth(token)
        return {"pong": True, "user": payload["sub"], "server_time": time.time()}


if __name__ == "__main__":
    HOST, PORT = "localhost", 8002
    server = xmlrpc.server.SimpleXMLRPCServer(
        (HOST, PORT), logRequests=False, allow_none=True
    )
    server.register_instance(RPCServer())
    server.register_introspection_functions()
    print(f"[RPCServer] Listening on {HOST}:{PORT} ...")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[RPCServer] Shutting down.")
