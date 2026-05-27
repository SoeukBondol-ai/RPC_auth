"""WiFi hotspot management — cross-platform (Linux via nmcli, Windows via WinRT Mobile Hotspot)."""

import json
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


# ── Windows (WinRT Mobile Hotspot via PowerShell) ──────────────────────────────

_PS_WINRT_PROLOGUE = """
[Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager, Windows.Networking.NetworkOperators, ContentType=WindowsRuntime] | Out-Null
[Windows.Networking.Connectivity.NetworkInformation, Windows.Networking.Connectivity, ContentType=WindowsRuntime] | Out-Null
$ErrorActionPreference = "Stop"
$profile = [Windows.Networking.Connectivity.NetworkInformation]::GetInternetConnectionProfile()
if ($null -eq $profile) { throw "No active internet connection profile found" }
$manager = [Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager]::CreateFromConnectionProfile($profile)
""".strip()

_PS_TETHERING_POLL = """
$count = 0
while ($manager.TetheringOperationalState -ne '__TARGET__' -and $count -lt 30) {
    Start-Sleep -Milliseconds 500
    $count++
}
if ($manager.TetheringOperationalState -ne '__TARGET__') {
    throw "Hotspot did not reach state '__TARGET__' within 15 seconds"
}
""".strip()


def _run_ps(script: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run a PowerShell script and return the result."""
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        stderr = result.stderr.strip()
        if "access is denied" in stderr.lower() or "elevation" in stderr.lower():
            raise RuntimeError(
                "Mobile Hotspot requires Administrator privileges.\n"
                "Run the gateway as Administrator:\n"
                "  Right-click terminal → Run as Administrator → python gateway.py"
            )
        raise RuntimeError(stderr or f"PowerShell command failed (exit code {result.returncode})")
    return result


def _start_windows(
    ssid: str | None = None,
    password: str | None = None,
    iface: str | None = None,
    **kwargs,
) -> dict:
    ssid = ssid or config.HOTSPOT_SSID
    password = password or config.HOTSPOT_PASSWORD

    script = _PS_WINRT_PROLOGUE + f"""
$config = $manager.GetCurrentAccessPointConfiguration()
$config.Ssid = "{ssid}"
$config.Passphrase = "{password}"
$manager.ConfigureAccessPointAsync($config) | Out-Null
$manager.StartTetheringAsync() | Out-Null
""" + _PS_TETHERING_POLL.replace("__TARGET__", "On")
    try:
        _run_ps(script)
    except RuntimeError as e:
        return {"ok": False, "error": str(e)}

    return _status_windows()


def _stop_windows(**kwargs) -> dict:
    script = _PS_WINRT_PROLOGUE + """
$manager.StopTetheringAsync() | Out-Null
""" + _PS_TETHERING_POLL.replace("__TARGET__", "Off")
    try:
        _run_ps(script)
        return {"ok": True}
    except RuntimeError as e:
        return {"ok": False, "error": str(e)}


def _status_windows(**kwargs) -> dict:
    script = _PS_WINRT_PROLOGUE + """
$config = $manager.GetCurrentAccessPointConfiguration()
@{
    active = ($manager.TetheringOperationalState -eq "On")
    ssid = $config.Ssid
    password = $config.Passphrase
} | ConvertTo-Json -Compress
"""
    result = _run_ps(script, check=False)

    if result.returncode != 0:
        return {
            "ok": True,
            "active": False,
            "con_name": "mobile_hotspot",
            "platform": "windows",
        }

    try:
        data = json.loads(result.stdout.strip())
    except (json.JSONDecodeError, ValueError):
        return {
            "ok": True,
            "active": False,
            "con_name": "mobile_hotspot",
            "platform": "windows",
        }

    # Get IP of the Wi-Fi Direct (tethering) adapter
    ip_address = ""
    ip_r = _run_ps(
        "Get-NetAdapter | Where-Object { $_.InterfaceDescription -like '*Wi-Fi Direct*' } "
        "| Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue "
        "| Select-Object -First 1 -ExpandProperty IPAddress",
        check=False,
    )
    if ip_r.returncode == 0 and ip_r.stdout.strip():
        ip_address = ip_r.stdout.strip()

    return {
        "ok": True,
        "active": data.get("active", False),
        "ssid": data.get("ssid", ""),
        "password": data.get("password", config.HOTSPOT_PASSWORD),
        "iface": "Microsoft Wi-Fi Direct Virtual Adapter",
        "con_name": "mobile_hotspot",
        "ip_address": ip_address,
        "platform": "windows",
    }


def _hotspot_adapter_index() -> int | None:
    """Find the interface index of the Wi-Fi Direct (hotspot) adapter."""
    result = _run_ps(
        "Get-NetAdapter | Where-Object { $_.InterfaceDescription -like '*Wi-Fi Direct*' } "
        "| Select-Object -First 1 -ExpandProperty InterfaceIndex",
        check=False,
    )
    if result.returncode == 0 and result.stdout.strip().isdigit():
        return int(result.stdout.strip())
    return None


def _devices_windows(**kwargs) -> list[dict]:
    """On Windows, get devices connected to the Mobile Hotspot only."""
    iface_idx = _hotspot_adapter_index()
    if iface_idx is None:
        return []

    # Query neighbor table on the hotspot adapter (fast, no DNS resolution)
    ps_script = """
$neighbors = Get-NetNeighbor -InterfaceIndex """ + str(iface_idx) + """
$result = @()
foreach ($n in $neighbors) {
    $result += @{
        ip = $n.IPAddress
        mac = ($n.LinkLayerAddress -replace '-',':').ToUpper()
    }
}
$result | ConvertTo-Json -Compress
"""
    result = _run_ps(ps_script, check=False)
    if result.returncode != 0 or not result.stdout.strip():
        return []

    try:
        data = json.loads(result.stdout.strip())
        if isinstance(data, dict):
            data = [data]
    except (json.JSONDecodeError, ValueError):
        return []

    # Filter out broadcast, multicast, and zero-MAC entries, then resolve hostnames in Python
    import socket
    filtered = []
    for d in data:
        ip = d.get("ip", "")
        mac = d.get("mac", "")
        if mac == "00:00:00:00:00:00" or mac.startswith("FF:FF"):
            continue
        if ip.startswith(("224.", "239.", "255.")):
            continue
        if ip.endswith(".255"):
            continue
        hostname = ""
        try:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as exc:
                fut = exc.submit(socket.gethostbyaddr, ip)
                hostname = fut.result(timeout=2)[0]
            if hostname.endswith(".mshome.net"):
                hostname = hostname[: -len(".mshome.net")]
        except Exception:
            pass
        d["hostname"] = hostname
        filtered.append(d)
    return filtered


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
