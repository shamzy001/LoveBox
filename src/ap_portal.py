import network
import usocket
import ujson
import machine
import time

_AP_SSID = "OffenHerz-Setup"
_AP_IP = "192.168.4.1"

_HTML = (
    "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n"
    "<!DOCTYPE html><html><head>"
    "<meta name=viewport content='width=device-width,initial-scale=1'>"
    "<title>OffenHerz WiFi</title>"
    "<style>body{font-family:sans-serif;max-width:400px;margin:40px auto;padding:0 16px}"
    "input{display:block;width:100%;padding:10px;margin:8px 0 20px;font-size:1em;box-sizing:border-box;border:1px solid #ccc;border-radius:4px}"
    "button{padding:14px 28px;font-size:1em;background:#ff6482;color:#fff;border:none;border-radius:4px;width:100%}"
    "label{font-weight:bold}</style>"
    "</head><body>"
    "<h2 style='color:#ff6482'>OffenHerz WiFi Setup</h2>"
    "<p>Enter the WiFi credentials for this location.</p>"
    "<form method=POST>"
    "<label>Network name (SSID)</label>"
    "<input name=ssid autocomplete=off autocapitalize=none spellcheck=false>"
    "<label>Password</label>"
    "<input name=password type=password>"
    "<button type=submit>Save &amp; Restart</button>"
    "</form></body></html>"
)

_OK_HTML = (
    "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n"
    "<html><body style='font-family:sans-serif;text-align:center;margin-top:60px'>"
    "<h2 style='color:#ff6482'>Saved!</h2>"
    "<p>OffenHerz is restarting and connecting...</p>"
    "</body></html>"
)

_REDIRECT = (
    "HTTP/1.1 302 Found\r\n"
    "Location: http://" + _AP_IP + "/\r\n"
    "Content-Length: 0\r\n\r\n"
)


def _url_decode(s):
    out = []
    i = 0
    while i < len(s):
        if s[i] == '+':
            out.append(' ')
            i += 1
        elif s[i] == '%' and i + 2 < len(s):
            try:
                out.append(chr(int(s[i + 1:i + 3], 16)))
            except ValueError:
                out.append(s[i])
            i += 3
        else:
            out.append(s[i])
            i += 1
    return ''.join(out)


def _parse_form(body):
    params = {}
    for pair in body.split('&'):
        if '=' in pair:
            k, v = pair.split('=', 1)
            params[_url_decode(k)] = _url_decode(v)
    return params


def _dns_response(query, ip):
    """Return a DNS A-record response pointing any query hostname to ip."""
    if len(query) < 12:
        return b""
    ip_bytes = bytes([int(x) for x in ip.split('.')])
    return (
        query[:2]               # transaction ID (echo back)
        + b'\x81\x80'           # flags: standard response, no error
        + query[4:6]            # QDCOUNT (echo back)
        + b'\x00\x01'           # ANCOUNT = 1
        + b'\x00\x00'           # NSCOUNT = 0
        + b'\x00\x00'           # ARCOUNT = 0
        + query[12:]            # question section (echo back verbatim)
        + b'\xc0\x0c'           # answer NAME: pointer to offset 12 (the question QNAME)
        + b'\x00\x01'           # TYPE: A
        + b'\x00\x01'           # CLASS: IN
        + b'\x00\x00\x00\x3c'   # TTL: 60 seconds
        + b'\x00\x04'           # RDLENGTH: 4 bytes
        + ip_bytes              # RDATA: IPv4 address
    )


def _read_request(conn):
    """Read a full HTTP request from conn. Returns decoded string."""
    data = b""
    conn.settimeout(3)
    try:
        while True:
            chunk = conn.recv(512)
            if not chunk:
                break
            data += chunk
            if b"\r\n\r\n" in data:
                if data[:4] == b"POST":
                    header_end = data.index(b"\r\n\r\n") + 4
                    cl = 0
                    for line in data[:header_end].split(b"\r\n"):
                        if line.lower().startswith(b"content-length:"):
                            try:
                                cl = int(line.split(b":", 1)[1].strip())
                            except Exception:
                                pass
                    while len(data) - header_end < cl:
                        more = conn.recv(256)
                        if not more:
                            break
                        data += more
                break
    except OSError:
        pass
    return data.decode("utf-8", "ignore")


def _handle_http(conn):
    """
    Handle one HTTP request.
    Returns (ssid, password) when valid credentials are submitted, else None.
    """
    try:
        request = _read_request(conn)
        if not request:
            return None

        if request.startswith("POST"):
            parts = request.split("\r\n\r\n", 1)
            body = parts[1] if len(parts) > 1 else ""
            params = _parse_form(body)
            ssid = params.get("ssid", "").strip()
            password = params.get("password", "")
            if ssid:
                conn.send(_OK_HTML)
                return (ssid, password)
            conn.send(_HTML)
        else:
            # Redirect any path other than "/" so that captive portal checks
            # (e.g. /generate_204, /hotspot-detect.html) land back on our form.
            first_line = request.split("\r\n", 1)[0]
            path = first_line.split(" ")[1] if " " in first_line else "/"
            if path == "/":
                conn.send(_HTML)
            else:
                conn.send(_REDIRECT)
    except Exception as e:
        print("Portal: request error:", e)
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return None


def run_portal(show_status_cb=None, timeout_ms=300_000):
    """
    Start a WiFi AP, a DNS server (UDP 53), and an HTTP server (TCP 80).

    The DNS server answers ALL queries with _AP_IP so that Android/iOS captive
    portal detection fires automatically — no manual URL entry needed.

    On valid credential submission: saves /sd/wifi_override.json and reboots.
    On timeout (default 5 min): returns False so the caller continues without WiFi.

    show_status_cb: callable(line1, line2=None, ok=True)
    """
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(essid=_AP_SSID, security=0)  # open network

    if show_status_cb:
        show_status_cb(_AP_SSID, _AP_IP)
    print("AP portal: SSID=" + _AP_SSID + "  http://" + _AP_IP)

    http_sock = usocket.socket(usocket.AF_INET, usocket.SOCK_STREAM)
    http_sock.setsockopt(usocket.SOL_SOCKET, usocket.SO_REUSEADDR, 1)
    http_sock.bind(("0.0.0.0", 80))
    http_sock.listen(2)
    http_sock.settimeout(0.05)

    dns_sock = usocket.socket(usocket.AF_INET, usocket.SOCK_DGRAM)
    dns_sock.setsockopt(usocket.SOL_SOCKET, usocket.SO_REUSEADDR, 1)
    dns_sock.bind(("0.0.0.0", 53))
    dns_sock.settimeout(0.05)

    deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
    credentials = None

    try:
        while time.ticks_diff(deadline, time.ticks_ms()) > 0:
            # Service DNS — respond to every query with our IP
            try:
                query, addr = dns_sock.recvfrom(512)
                resp = _dns_response(query, _AP_IP)
                if resp:
                    dns_sock.sendto(resp, addr)
            except OSError:
                pass

            # Service HTTP
            try:
                conn, _ = http_sock.accept()
                result = _handle_http(conn)
                if result:
                    credentials = result
                    break
            except OSError:
                pass

    finally:
        try:
            http_sock.close()
        except Exception:
            pass
        try:
            dns_sock.close()
        except Exception:
            pass
        ap.active(False)

    if credentials:
        ssid, password = credentials
        try:
            with open("/sd/wifi_override.json", "w") as f:
                ujson.dump({"ssid": ssid, "password": password}, f)
            print("AP portal: saved override for SSID:", ssid)
        except Exception as e:
            print("AP portal: could not save override:", e)
        time.sleep_ms(800)  # let the OK page render in the browser
        machine.reset()

    print("AP portal: timed out, continuing without WiFi")
    return False
