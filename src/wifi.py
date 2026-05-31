import network
import time
import secrets

_wlan = network.WLAN(network.STA_IF)
is_connected = False


def _load_override():
    try:
        import ujson
        with open("/sd/wifi_override.json") as f:
            d = ujson.load(f)
        return (d["ssid"].strip(), d["password"])
    except Exception:
        return None


def _load_learned():
    try:
        import ujson
        with open("/sd/wifi_learned.json") as f:
            entries = ujson.load(f)
        return [(e["ssid"], e["password"]) for e in entries if e.get("ssid")]
    except Exception:
        return []


def _networks():
    """Return ordered list: override → learned → secrets.WIFI_NETWORKS (deduped)."""
    override = _load_override()
    learned = _load_learned()
    base = list(secrets.WIFI_NETWORKS)

    result = []
    seen = set()

    if override:
        result.append(override)
        seen.add(override[0])

    for ssid, password in learned:
        if ssid not in seen:
            result.append((ssid, password))
            seen.add(ssid)

    for ssid, password in base:
        if ssid not in seen:
            result.append((ssid, password))
            seen.add(ssid)

    return result


def _promote_override(connected_ssid):
    """
    If we connected via the override network, add it to wifi_learned.json
    and delete the override file so it does not need to be re-entered.
    """
    override = _load_override()
    if not override or override[0] != connected_ssid:
        return

    ssid, password = override
    try:
        import ujson, os
        learned = []
        try:
            with open("/sd/wifi_learned.json") as f:
                learned = ujson.load(f)
        except Exception:
            pass

        if not any(e.get("ssid") == ssid for e in learned):
            learned.append({"ssid": ssid, "password": password})
            with open("/sd/wifi_learned.json", "w") as f:
                ujson.dump(learned, f)
            print("Wi-Fi: '{}' added to learned networks".format(ssid))

        os.remove("/sd/wifi_override.json")
        print("Wi-Fi: override file removed")
    except Exception as e:
        print("Wi-Fi: promote error:", e)


def connect():
    """Scan and connect to the best available known network. Blocking."""
    global is_connected
    _wlan.active(True)
    networks = _networks()

    try:
        visible = {net[0].decode() if isinstance(net[0], bytes) else net[0]
                   for net in _wlan.scan()}
        ordered = [n for n in networks if n[0] in visible]
        ordered += [n for n in networks if n[0] not in visible]
    except Exception:
        ordered = networks

    for ssid, password in ordered:
        print("Wi-Fi: trying", ssid)
        try:
            if _wlan.isconnected():
                _wlan.disconnect()
                time.sleep_ms(300)
            _wlan.connect(ssid, password)
            deadline = time.ticks_add(time.ticks_ms(), 15000)
            while not _wlan.isconnected():
                if time.ticks_diff(deadline, time.ticks_ms()) <= 0:
                    break
                time.sleep_ms(200)
            if _wlan.isconnected():
                is_connected = True
                print("Wi-Fi: connected to", ssid)
                _promote_override(ssid)
                return True
            print("Wi-Fi: timed out on", ssid)
        except Exception as e:
            print("Wi-Fi: error on", ssid, ":", e)

    is_connected = False
    print("Wi-Fi: no networks available")
    return False


def ensure_connected():
    """Non-blocking check; triggers reconnect if dropped."""
    global is_connected
    connected = _wlan.isconnected()
    is_connected = connected
    if not connected:
        connect()
    return _wlan.isconnected()
