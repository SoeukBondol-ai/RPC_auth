import sys
import json
import time
import xmlrpc.client
from flask import (
    Flask,
    request,
    jsonify,
    send_from_directory,
    Response,
    stream_with_context,
)

sys.path.insert(0, ".")

import config
import hotspot

from common.encryption import AESCipher, RSACipher

app = Flask(__name__, static_folder="frontend", static_url_path="")


def _get_auth_proxy():
    return xmlrpc.client.ServerProxy(config.AUTH_URL)


def _get_server_proxy():
    return xmlrpc.client.ServerProxy(config.SERVER_URL)


@app.route("/")
def index():
    return send_from_directory("frontend", "index.html")


@app.route("/<path:path>")
def static_files(path):
    return send_from_directory("frontend", path)


# ── Key exchange ───────────────────────────────────────────────────────────


@app.route("/api/shared-key")
def shared_key():
    auth = _get_auth_proxy()
    return jsonify({"key": auth.get_shared_key_hex()})


@app.route("/api/public-key")
def public_key():
    auth = _get_auth_proxy()
    return jsonify({"key": auth.get_public_key()})


# ── Register ───────────────────────────────────────────────────────────────


@app.route("/api/register", methods=["POST"])
def register():
    body = request.get_json()
    username = body.get("username", "")
    password = body.get("password", "")
    mode = body.get("mode", "symmetric")

    payload = json.dumps(
        {"username": username, "password": password, "method": "register"}
    )

    auth = _get_auth_proxy()
    try:
        if mode == "symmetric":
            key_hex = auth.get_shared_key_hex()
            key = AESCipher.key_from_hex(key_hex)
            enc = AESCipher.encrypt(key, payload)
            result = auth.register_symmetric(enc)
        else:
            pub_pem = auth.get_public_key()
            public_key = RSACipher.load_public_key(pub_pem)
            enc = RSACipher.encrypt(public_key, payload)
            result = auth.register_asymmetric(enc)

        return jsonify({"ok": True, "message": json.loads(result)})
    except xmlrpc.client.Fault as e:
        return jsonify({"ok": False, "error": e.faultString, "code": e.faultCode}), 400


# ── Login ──────────────────────────────────────────────────────────────────


@app.route("/api/login", methods=["POST"])
def login():
    body = request.get_json()
    username = body.get("username", "")
    password = body.get("password", "")
    mode = body.get("mode", "symmetric")
    method = body.get("method", "getData")

    payload = json.dumps({"username": username, "password": password, "method": method})

    auth = _get_auth_proxy()
    try:
        if mode == "symmetric":
            key_hex = auth.get_shared_key_hex()
            key = AESCipher.key_from_hex(key_hex)
            enc = AESCipher.encrypt(key, payload)
            token = auth.authenticate_symmetric(enc)
        else:
            pub_pem = auth.get_public_key()
            public_key = RSACipher.load_public_key(pub_pem)
            enc = RSACipher.encrypt(public_key, payload)
            token = auth.authenticate_asymmetric(enc)

        return jsonify({"ok": True, "token": token})
    except xmlrpc.client.Fault as e:
        return jsonify({"ok": False, "error": e.faultString, "code": e.faultCode}), 401


# ── RPC calls ──────────────────────────────────────────────────────────────


@app.route("/api/rpc", methods=["POST"])
def rpc():
    body = request.get_json()
    method = body.get("method", "getData")
    token = body.get("token", "")

    srv = _get_server_proxy()
    try:
        if method == "getData":
            result = srv.getData(token)
        elif method == "writeRecord":
            data = body.get("data", "")
            result = srv.writeRecord(token, data)
        elif method == "deleteItem":
            item_id = int(body.get("item_id", 0))
            result = srv.deleteItem(token, item_id)
        elif method == "ping":
            result = srv.ping(token)
        else:
            return jsonify({"ok": False, "error": f"Unknown method: {method}"}), 400

        return jsonify({"ok": True, "result": result})
    except xmlrpc.client.Fault as e:
        return jsonify({"ok": False, "error": e.faultString, "code": e.faultCode}), 401


# ── Password reset ────────────────────────────────────────────────────────


@app.route("/api/reset-password", methods=["POST"])
def reset_password():
    body = request.get_json()
    username = body.get("username", "")
    new_password = body.get("new_password", "")
    mode = body.get("mode", "symmetric")

    payload = json.dumps({"username": username, "new_password": new_password})

    auth = _get_auth_proxy()
    try:
        if mode == "symmetric":
            key_hex = auth.get_shared_key_hex()
            key = AESCipher.key_from_hex(key_hex)
            enc = AESCipher.encrypt(key, payload)
            result = auth.reset_password_symmetric(enc)
        else:
            pub_pem = auth.get_public_key()
            public_key = RSACipher.load_public_key(pub_pem)
            enc = RSACipher.encrypt(public_key, payload)
            result = auth.reset_password_asymmetric(enc)

        return jsonify({"ok": True, "message": json.loads(result)})
    except xmlrpc.client.Fault as e:
        return jsonify({"ok": False, "error": e.faultString, "code": e.faultCode}), 400


# ── WiFi Hotspot ─────────────────────────────────────────────────────────────


@app.route("/api/hotspot/start", methods=["POST"])
def hotspot_start():
    body = request.get_json(silent=True) or {}
    result = hotspot.start_hotspot(
        ssid=body.get("ssid") or None,
        password=body.get("password") or None,
        iface=body.get("iface") or None,
    )
    if not result.get("ok", True):
        return jsonify(result), 500
    return jsonify(result)


@app.route("/api/hotspot/stop", methods=["POST"])
def hotspot_stop():
    result = hotspot.stop_hotspot()
    if not result["ok"]:
        return jsonify(result), 500
    return jsonify(result)


@app.route("/api/hotspot/status")
def hotspot_status():
    return jsonify(hotspot.get_hotspot_status())


@app.route("/api/hotspot/devices")
def hotspot_devices():
    return jsonify(hotspot.get_connected_devices())


@app.route("/api/hotspot/qr")
def hotspot_qr():
    status = hotspot.get_hotspot_status()
    if not status.get("active"):
        return jsonify({"error": "Hotspot not active"}), 400
    png_bytes = hotspot.generate_wifi_qr(
        ssid=status["ssid"],
        password=status["password"],
    )
    return Response(png_bytes, mimetype="image/png")


@app.route("/api/hotspot/devices/stream")
def hotspot_devices_stream():
    """SSE endpoint: pushes connected-device updates every N seconds."""

    def generate():
        last_json = ""
        while True:
            try:
                devices = hotspot.get_connected_devices()
                current_json = json.dumps(devices, sort_keys=True)
            except Exception:
                devices = []
                current_json = "[]"
            if current_json != last_json:
                last_json = current_json
                yield f"data: {current_json}\n\n"
            else:
                yield ": heartbeat\n\n"
            time.sleep(config.HOTSPOT_DEVICE_POLL_INTERVAL)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/api/hotspot/interfaces")
def hotspot_interfaces():
    return jsonify(hotspot.get_wifi_interfaces())


if __name__ == "__main__":
    print(f"[Gateway] Starting on http://{config.GATEWAY_HOST}:{config.GATEWAY_PORT}")
    app.run(host=config.GATEWAY_HOST, port=config.GATEWAY_PORT, debug=False)
