"""WiFi hotspot management — cross-platform (Linux via nmcli, Windows via netsh)."""

import os
import platform
import re
import subprocess
import time
from io import BytesIO

import qrcode

import config

IS_WINDOWS = platform.system() == "Windows"


def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a command. On Linux, try without sudo first, then with sudo if needed."""
    if IS_WINDOWS:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    else:
        # Linux: try without sudo first
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0 and config.HOTSPOT_USE_SUDO:
            # Permission denied or similar — retry with sudo
            sudo_result = subprocess.run(
                ["sudo", "-n"] + cmd, capture_output=True, text=True, check=False
            )
            # Prefer sudo result if it succeeded or failed for a different reason
            if sudo_result.returncode == 0:
                result = sudo_result
            elif (
                "password" not in sudo_result.stderr.lower()
                and sudo_result.returncode != 0
            ):
                # sudo ran but command still failed (better error than perm denied)
                result = sudo_result

    if check and result.returncode != 0:
        stderr = result.stderr.strip()
        if "password" in stderr.lower() and "sudo" in stderr.lower():
            raise RuntimeError(
                "Hotspot commands need elevated privileges.\n"
                "Options:\n"
                "  1. Run as root: sudo uv run python gateway.py\n"
                "  2. Add passwordless sudo for nmcli:\n"
                f"     echo '{os.getlogin()} ALL=(root) NOPASSWD: /usr/bin/nmcli' "
                "| sudo tee /etc/sudoers.d/rpc-auth-nmcli\n"
                "  3. Set RPC_AUTH_HOTSPOT_USE_SUDO=false in .env if running as root"
            )
        raise RuntimeError(stderr or f"Command failed: {' '.join(cmd)}")
    return result


def _detect_internet_source() -> str:
    """Detect how the machine connects to the internet. Returns 'ethernet', 'wifi', or 'unknown'."""
    if IS_WINDOWS:
        try:
            result = subprocess.run(
                ["netsh", "interface", "ipv4", "show", "route"],
                capture_output=True,
                text=True,
                check=False,
            )
            if "Ethernet" in result.stdout or "Local Area" in result.stdout:
                return "ethernet"
            return "unknown"
        except Exception:
            return "unknown"
    else:
        try:
            # Check default route interface
            result = subprocess.run(
                ["ip", "route", "show", "default"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if "dev" in line:
                        iface = line.split("dev")[1].split()[0]
                        # Check if that interface is wifi
                        type_result = subprocess.run(
                            ["nmcli", "-t", "-f", "DEVICE,TYPE", "device"],
                            capture_output=True,
                            text=True,
                            check=False,
                        )
                        if type_result.returncode == 0:
                            for tline in type_result.stdout.splitlines():
                                parts = tline.split(":")
                                if len(parts) >= 2 and parts[0] == iface:
                                    return "wifi" if parts[1] == "wifi" else "ethernet"
            return "unknown"
        except Exception:
            return "unknown"


# ── Linux (nmcli) ─────────────────────────────────────────────────────────────


def _start_linux(
    ssid: str | None = None,
    password: str | None = None,
    iface: str | None = None,
    con_name: str | None = None,
    band: str | None = None,
    channel: int | None = None,
) -> dict:
    ssid = ssid or config.HOTSPOT_SSID
    password = password or config.HOTSPOT_PASSWORD
    iface = iface or config.HOTSPOT_IFACE or None
    con_name = con_name or config.HOTSPOT_CON_NAME
    band = band or config.HOTSPOT_BAND
    channel = channel or config.HOTSPOT_CHANNEL

    # Detect if internet comes through WiFi (one-adapter limitation)
    internet_source = _detect_internet_source()
    warnings = []
    if internet_source == "wifi":
        warnings.append(
            "Internet is coming through WiFi. On Linux, most WiFi adapters "
            "cannot simultaneously connect to WiFi and host a hotspot. "
            "Connect via ethernet for reliable hotspot + internet sharing."
        )

    cmd = [
        "nmcli",
        "dev",
        "wifi",
        "hotspot",
        "ssid",
        ssid,
        "password",
        password,
        "con-name",
        con_name,
    ]
    if iface:
        cmd.extend(["ifname", iface])
    if band:
        cmd.extend(["band", band])
    if channel:
        cmd.extend(["channel", str(channel)])

    try:
        _run(cmd)
    except RuntimeError as e:
        return {"ok": False, "error": str(e), "warnings": warnings}

    time.sleep(2)
    status = _status_linux(con_name)
    if warnings:
        status["warnings"] = warnings
    return status


def _stop_linux(con_name: str | None = None) -> dict:
    con_name = con_name or config.HOTSPOT_CON_NAME
    try:
        _run(["nmcli", "connection", "down", con_name])
        return {"ok": True}
    except RuntimeError as e:
        return {"ok": False, "error": str(e)}


def _status_linux(con_name: str | None = None) -> dict:
    con_name = con_name or config.HOTSPOT_CON_NAME

    result = _run(["nmcli", "-t", "connection", "show", "--active"], check=False)
    active_lines = result.stdout.strip().splitlines() if result.stdout.strip() else []

    hotspot_line = None
    for line in active_lines:
        parts = line.split(":")
        if parts and parts[0] == con_name:
            hotspot_line = parts
            break

    if not hotspot_line:
        return {"ok": True, "active": False, "con_name": con_name, "platform": "linux"}

    iface = hotspot_line[1] if len(hotspot_line) > 1 else ""

    ssid = ""
    ssid_result = _run(
        ["nmcli", "-t", "-f", "802-11-wireless.ssid", "connection", "show", con_name],
        check=False,
    )
    if ssid_result.returncode == 0 and ssid_result.stdout.strip():
        ssid = ssid_result.stdout.strip().split(":", 1)[-1]

    # Try to get password — fall back to config value if access denied
    password = config.HOTSPOT_PASSWORD
    pw_result = _run(
        [
            "nmcli",
            "--show-secrets",
            "-t",
            "-f",
            "802-11-wireless-psk",
            "connection",
            "show",
            con_name,
        ],
        check=False,
    )
    if pw_result.returncode == 0 and pw_result.stdout.strip():
        pw = pw_result.stdout.strip().split(":", 1)[-1]
        if pw:
            password = pw

    ip_address = ""
    ip_result = _run(["ip", "-4", "addr", "show", iface], check=False)
    if ip_result.returncode == 0:
        match = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)", ip_result.stdout)
        if match:
            ip_address = match.group(1)

    return {
        "ok": True,
        "active": True,
        "ssid": ssid,
        "password": password,
        "iface": iface,
        "con_name": con_name,
        "ip_address": ip_address,
        "platform": "linux",
    }


def _devices_linux(iface: str | None = None) -> list[dict]:
    if not iface:
        status = _status_linux()
        iface = status.get("iface") or config.HOTSPOT_IFACE
    if not iface:
        return []

    devices: dict[str, dict] = {}

    # Source 1: ARP table (doesn't need special permissions)
    neigh_result = _run(["ip", "neigh", "show", "dev", iface], check=False)
    if neigh_result.returncode == 0:
        for line in neigh_result.stdout.strip().splitlines():
            parts = line.split()
            if len(parts) >= 4 and "lladdr" in parts:
                ip = parts[0]
                mac_idx = parts.index("lladdr") + 1
                mac = parts[mac_idx].upper() if mac_idx < len(parts) else ""
                if mac and mac != "00:00:00:00:00:00":
                    key = mac.replace(":", "")
                    devices[key] = {"ip": ip, "mac": mac, "hostname": ""}

    # Source 2: dnsmasq lease files for hostnames (may need permissions)
    lease_paths = [
        f"/var/lib/NetworkManager/dnsmasq-{iface}.leases",
        "/var/lib/NetworkManager/dnsmasq-*.leases",
        "/var/lib/misc/dnsmasq.leases",
    ]
    for lease_path in lease_paths:
        import glob

        for resolved_path in glob.glob(lease_path):
            try:
                with open(resolved_path) as f:
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) >= 4:
                            mac = parts[1].upper()
                            ip = parts[2]
                            hostname = parts[3] if parts[3] != "*" else ""
                            key = mac.replace(":", "")
                            if key in devices:
                                devices[key]["hostname"] = hostname
                            else:
                                devices[key] = {
                                    "ip": ip,
                                    "mac": mac,
                                    "hostname": hostname,
                                }
            except (FileNotFoundError, PermissionError):
                # Try with sudo for permission-denied files
                try:
                    sudo_result = _run(["cat", resolved_path], check=False)
                    if sudo_result.returncode == 0:
                        for line in sudo_result.stdout.splitlines():
                            parts = line.strip().split()
                            if len(parts) >= 4:
                                mac = parts[1].upper()
                                ip = parts[2]
                                hostname = parts[3] if parts[3] != "*" else ""
                                key = mac.replace(":", "")
                                if key in devices:
                                    devices[key]["hostname"] = hostname
                                else:
                                    devices[key] = {
                                        "ip": ip,
                                        "mac": mac,
                                        "hostname": hostname,
                                    }
                except Exception:
                    continue

    return list(devices.values())


def _interfaces_linux() -> list[str]:
    result = _run(["nmcli", "-t", "-f", "DEVICE,TYPE", "device"], check=False)
    interfaces = []
    if result.returncode == 0:
        for line in result.stdout.strip().splitlines():
            parts = line.split(":")
            if len(parts) >= 2 and parts[1] == "wifi":
                interfaces.append(parts[0])
    return interfaces


# ── Windows (netsh) ────────────────────────────────────────────────────────────


def _start_windows(
    ssid: str | None = None,
    password: str | None = None,
    iface: str | None = None,
    **kwargs,
) -> dict:
    ssid = ssid or config.HOTSPOT_SSID
    password = password or config.HOTSPOT_PASSWORD

    try:
        _run(
            [
                "netsh",
                "wlan",
                "set",
                "hostednetwork",
                f"ssid={ssid}",
                f"key={password}",
                "mode=allow",
            ]
        )
        _run(["netsh", "wlan", "start", "hostednetwork"])
    except RuntimeError as e:
        return {"ok": False, "error": str(e)}

    time.sleep(2)
    return _status_windows()


def _stop_windows(**kwargs) -> dict:
    try:
        _run(["netsh", "wlan", "stop", "hostednetwork"])
        return {"ok": True}
    except RuntimeError as e:
        return {"ok": False, "error": str(e)}


def _status_windows(**kwargs) -> dict:
    result = _run(["netsh", "wlan", "show", "hostednetwork"], check=False)
    output = result.stdout

    if "Not started" in output or result.returncode != 0:
        return {
            "ok": True,
            "active": False,
            "con_name": "hostednetwork",
            "platform": "windows",
        }

    ssid = ""
    status_line = ""
    for line in output.splitlines():
        line = line.strip()
        if "SSID name" in line:
            ssid = line.split(":", 1)[-1].strip().strip('"')
        if "Status" in line:
            status_line = line.split(":", 1)[-1].strip()

    # Get IP of the hosted network adapter
    ip_address = ""
    for adapter_name in ["Local Area Connection*", "Wi-Fi"]:
        ip_r = _run(
            ["netsh", "interface", "ipv4", "show", "addr", f"name={adapter_name}"],
            check=False,
        )
        if ip_r.returncode == 0:
            match = re.search(r"(\d+\.\d+\.\d+\.\d+)", ip_r.stdout)
            if match:
                ip_address = match.group(1)
                break

    return {
        "ok": True,
        "active": status_line.lower() == "started",
        "ssid": ssid,
        "password": config.HOTSPOT_PASSWORD,
        "iface": "Microsoft Hosted Network Virtual Adapter",
        "con_name": "hostednetwork",
        "ip_address": ip_address,
        "platform": "windows",
    }


def _devices_windows(**kwargs) -> list[dict]:
    """On Windows, get connected devices from ARP table."""
    devices: dict[str, dict] = {}
    result = _run(["arp", "-a"], check=False)
    if result.returncode == 0:
        for line in result.stdout.splitlines():
            mac_match = re.search(
                r"([0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-][0-9a-fA-F]{2})",
                line,
            )
            ip_match = re.match(r"\s*(\d+\.\d+\.\d+\.\d+)", line)
            if mac_match and ip_match:
                ip = ip_match.group(1)
                mac = mac_match.group(1).upper().replace("-", ":")
                if mac != "FF:FF:FF:FF:FF:FF" and not ip.startswith("224."):
                    key = mac.replace(":", "")
                    devices[key] = {"ip": ip, "mac": mac, "hostname": ""}

    return list(devices.values())


def _interfaces_windows() -> list[str]:
    """Get WiFi interface names on Windows."""
    interfaces = []
    result = _run(["netsh", "wlan", "show", "interfaces"], check=False)
    if result.returncode == 0:
        for line in result.stdout.splitlines():
            if "Name" in line and ":" in line:
                interfaces.append(line.split(":", 1)[-1].strip())
    return interfaces


# ── Platform dispatcher ────────────────────────────────────────────────────────


def start_hotspot(
    ssid: str | None = None,
    password: str | None = None,
    iface: str | None = None,
    con_name: str | None = None,
    band: str | None = None,
    channel: int | None = None,
) -> dict:
    """Start a WiFi hotspot. Returns status dict."""
    # Check if already active
    status = get_hotspot_status(con_name)
    if status.get("active"):
        return status

    if IS_WINDOWS:
        return _start_windows(ssid=ssid, password=password, iface=iface)
    return _start_linux(
        ssid=ssid,
        password=password,
        iface=iface,
        con_name=con_name,
        band=band,
        channel=channel,
    )


def stop_hotspot(con_name: str | None = None) -> dict:
    """Stop the WiFi hotspot."""
    if IS_WINDOWS:
        return _stop_windows()
    return _stop_linux(con_name)


def get_hotspot_status(con_name: str | None = None) -> dict:
    """Return current hotspot status."""
    if IS_WINDOWS:
        return _status_windows()
    return _status_linux(con_name)


def get_connected_devices(iface: str | None = None) -> list[dict]:
    """Return connected devices with ip, mac, hostname."""
    if IS_WINDOWS:
        return _devices_windows()
    return _devices_linux(iface)


def generate_wifi_qr(ssid: str, password: str, encryption: str = "WPA") -> bytes:
    """Generate a WiFi QR code as PNG bytes."""
    qr_string = f"WIFI:T:{encryption};S:{ssid};P:{password};;"
    img = qrcode.make(qr_string)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def get_wifi_interfaces() -> list[str]:
    """Return available WiFi interface names."""
    if IS_WINDOWS:
        return _interfaces_windows()
    return _interfaces_linux()
