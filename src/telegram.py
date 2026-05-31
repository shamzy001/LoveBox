import ssl
import socket
import ujson
import os
import asyncio
import utime
import gc

import state
import wifi
import secrets

_HOST = "api.telegram.org"
_PORT = 443
_BASE = "/bot" + secrets.BOT_TOKEN
_PHOTO_SIZE_LIMIT = 5 * 1024 * 1024
_CHUNK = 4096


_HOST_ADDR = None   # cached after first successful DNS lookup
_seen_ids = set()      # dedup on update_id
_seen_msg_ids = set()  # dedup on message_id — catches message + edited_message pairs


def _open_ssl(timeout=15):
    global _HOST_ADDR
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.verify_mode = ssl.CERT_NONE
    if _HOST_ADDR is None:
        _HOST_ADDR = socket.getaddrinfo(_HOST, _PORT)[0][-1]
        print("dns resolved:", _HOST_ADDR)
    sock = socket.socket()
    sock.settimeout(timeout)
    try:
        sock.connect(_HOST_ADDR)
        return ctx.wrap_socket(sock, server_hostname=_HOST)
    except Exception:
        # Explicitly close the raw socket so the CYW43 slot is freed immediately
        # rather than waiting for GC. Without this, repeated failures exhaust the
        # chip's socket pool and subsequent allocations raise ENOMEM.
        try:
            sock.close()
        except Exception:
            pass
        _HOST_ADDR = None  # force fresh DNS on next attempt
        raise


def _recv_all(s):
    buf = bytearray()
    while True:
        try:
            c = s.read(512)
        except OSError:
            break
        if not c:
            break
        buf.extend(c)
    return bytes(buf)


def _decode_chunked(data):
    out = bytearray()
    i = 0
    while i < len(data):
        j = data.find(b"\r\n", i)
        if j < 0:
            break
        try:
            size = int(data[i:j].split(b";")[0].strip(), 16)
        except ValueError:
            break
        if size == 0:
            break
        i = j + 2
        out.extend(data[i:i + size])
        i += size + 2
    return bytes(out)


def _split_response(raw):
    sep = raw.find(b"\r\n\r\n")
    if sep < 0:
        return False, raw
    headers = raw[:sep].decode("utf-8", "ignore").lower()
    body = raw[sep + 4:]
    return "transfer-encoding: chunked" in headers, body


def _get(path, timeout=15):
    s = None
    try:
        s = _open_ssl(timeout)
        s.write(("GET {} HTTP/1.1\r\nHost: {}\r\nConnection: close\r\n\r\n"
                 .format(path, _HOST)).encode())
        raw = _recv_all(s)
        chunked, body = _split_response(raw)
        if chunked:
            body = _decode_chunked(body)
        return ujson.loads(body)
    except Exception as e:
        print("GET error:", e)
        gc.collect()
        return None
    finally:
        if s:
            try: s.close()
            except: pass


def _post(path, payload, timeout=15):
    s = None
    try:
        s = _open_ssl(timeout)
        hdr = ("POST {} HTTP/1.1\r\nHost: {}\r\n"
               "Content-Type: application/json\r\n"
               "Content-Length: {}\r\nConnection: close\r\n\r\n"
               .format(path, _HOST, len(payload))).encode()
        s.write(hdr)
        s.write(payload)
        raw = _recv_all(s)
        chunked, body = _split_response(raw)
        if chunked:
            body = _decode_chunked(body)
        return ujson.loads(body)
    except Exception as e:
        print("POST error:", e)
        gc.collect()
        return None
    finally:
        if s:
            try: s.close()
            except: pass


def get_updates(offset):
    """Poll getUpdates. Returns list of updates or []."""
    data = _get("{}/getUpdates?offset={}&timeout=0&limit=10".format(_BASE, offset))
    return data["result"] if data and data.get("ok") else []


def send_message(chat_id, text):
    """Send a text message. Returns True on success."""
    payload = ujson.dumps({"chat_id": chat_id, "text": text}).encode()
    data = _post("{}/sendMessage".format(_BASE), payload)
    return bool(data and data.get("ok"))


def _get_file_path(file_id):
    """Resolve file_id to (file_path, file_size). Returns (None, 0) on error."""
    data = _get("{}/getFile?file_id={}".format(_BASE, file_id))
    if data and data.get("ok"):
        f = data["result"]
        return f.get("file_path"), f.get("file_size", 0)
    return None, 0


def _stream_to_file(s, dest_path, chunked, leftover):
    """Write HTTP body from SSL socket to dest_path, handling chunked encoding."""
    with open(dest_path, "wb") as f:
        if not chunked:
            if leftover:
                f.write(leftover)
            while True:
                c = s.read(_CHUNK)
                if not c:
                    break
                f.write(c)
            return True

        buf = bytearray(leftover)
        while True:
            # Accumulate until we have a complete chunk-size line
            while b"\r\n" not in buf:
                c = s.read(128)
                if not c:
                    return True
                buf.extend(c)
            eol = buf.find(b"\r\n")
            try:
                size = int(bytes(buf[:eol]).split(b";")[0].strip(), 16)
            except ValueError:
                return False
            buf = buf[eol + 2:]
            if size == 0:
                return True
            # Write exactly `size` bytes
            remaining = size
            while remaining > 0:
                if buf:
                    take = min(len(buf), remaining)
                    f.write(buf[:take])
                    remaining -= take
                    buf = buf[take:]
                else:
                    c = s.read(min(_CHUNK, remaining))
                    if not c:
                        return True
                    buf.extend(c)
            # Skip trailing CRLF after chunk data
            while len(buf) < 2:
                c = s.read(2)
                if not c:
                    return True
                buf.extend(c)
            buf = buf[2:]
    return True


def download_file(file_id, dest_path):
    """Stream-download a Telegram file to dest_path. Returns True on success."""
    file_path, _ = _get_file_path(file_id)
    if file_path is None:
        return False
    s = None
    try:
        s = _open_ssl(timeout=60)
        path = "/file/bot{}/{}".format(secrets.BOT_TOKEN, file_path)
        s.write(("GET {} HTTP/1.1\r\nHost: {}\r\nConnection: close\r\n\r\n"
                 .format(path, _HOST)).encode())
        # Read until end of headers
        hdr_buf = bytearray()
        while b"\r\n\r\n" not in hdr_buf:
            c = s.read(128)
            if not c:
                return False
            hdr_buf.extend(c)
        sep = hdr_buf.find(b"\r\n\r\n")
        hdrs = bytes(hdr_buf[:sep]).decode("utf-8", "ignore").lower()
        chunked = "transfer-encoding: chunked" in hdrs
        leftover = bytes(hdr_buf[sep + 4:])
        return _stream_to_file(s, dest_path, chunked, leftover)
    except Exception as e:
        print("download_file error:", e)
        try: os.remove(dest_path)
        except OSError: pass
        return False
    finally:
        if s:
            try: s.close()
            except: pass


def check_photo_size(photo_array):
    """Pick best photo variant under the size limit. Returns file_id or None.
    Prefers variants <= 320px — Telegram uses baseline JPEG for those,
    which jpegdec can decode. Larger variants are progressive JPEG and will fail."""
    candidates = [p for p in photo_array
                  if p.get("width", 0) <= 320 and p.get("height", 0) <= 320]
    if not candidates:
        candidates = photo_array
    largest = max(candidates, key=lambda p: p.get("file_size", 0))
    if largest.get("file_size", 0) > _PHOTO_SIZE_LIMIT:
        send_message(secrets.SHAH_CHAT_ID, "Photo too large (>5 MB) — send a smaller version.")
        return None
    return largest["file_id"]


_MOODS = {
    "rose":     (255, 100, 130),
    "red":      (255,  40,  40),
    "orange":   (255, 120,  10),
    "yellow":   (255, 200,  40),
    "green":    ( 40, 210,  80),
    "mint":     ( 80, 255, 170),
    "teal":     (  0, 200, 180),
    "blue":     ( 80, 140, 255),
    "purple":   (150,  50, 255),
    "lavender": (190, 120, 255),
}

_HELP = """OffenherzBox commands:

/status — device info (WiFi, signal, uptime, photos, queue)

/mood <colour> — set LED colour
  rose · red · orange · yellow
  green · mint · teal · blue
  purple · lavender · off

/help — show this message"""


def _send_help():
    send_message(secrets.SHAH_CHAT_ID, _HELP)


def _send_status():
    """Build and send a status reply to Shah."""
    import network as _net
    import time
    import slideshow

    wlan = _net.WLAN(_net.STA_IF)
    cfg = wlan.ifconfig()          # (ip, mask, gateway, dns)
    ip = cfg[0]
    try:
        ssid = wlan.config('ssid')
    except Exception:
        ssid = "unknown"
    try:
        rssi = wlan.status('rssi')
        signal = "{} dBm".format(rssi)
    except Exception:
        signal = "n/a"

    uptime_ms = time.ticks_ms()
    hours = uptime_ms // 3_600_000
    mins  = (uptime_ms % 3_600_000) // 60_000

    lines = [
        "OffenherzBox Status",
        "Network: {}".format(ssid),
        "IP: {}".format(ip),
        "Signal: {}".format(signal),
        "Uptime: {}h {}m".format(hours, mins),
        "Photos: {}".format(slideshow.photo_count()),
        "Queue: {}".format(state.queue_len()),
    ]
    send_message(secrets.SHAH_CHAT_ID, "\n".join(lines))


def classify_message(update):
    """Return a message dict or None."""
    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return None
    from_id = msg.get("from", {}).get("id") or msg.get("chat", {}).get("id")
    if from_id != secrets.SHAH_CHAT_ID:
        return None
    text = msg.get("text", "")
    if text and text.startswith("/status"):
        return {"type": "command", "command": "status"}
    if text and text.startswith("/mood"):
        parts = text.split()
        colour = parts[1].lower() if len(parts) > 1 else ""
        return {"type": "command", "command": "mood", "colour": colour}
    if text and text.startswith("/help"):
        return {"type": "command", "command": "help"}
    if text and not text.startswith("/"):
        return {"type": "text", "body": text}
    if text and text.startswith("/"):
        return {"type": "command", "command": "unknown"}
    if "photo" in msg:
        caption = msg.get("caption", "").strip().lower()
        slideshow = "#slide" in caption
        return {"type": "photo", "photo": msg["photo"], "slideshow": slideshow}
    # Check animation before document — GIF messages carry both fields and we
    # want the animation branch (with its JPEG thumbnail) to win.
    if "animation" in msg:
        anim = msg["animation"]
        thumb = anim.get("thumb") or anim.get("thumbnail")
        if thumb:
            return {"type": "gif", "thumb_id": thumb["file_id"]}
        return {"type": "gif"}
    if "document" in msg:
        doc = msg["document"]
        mime = doc.get("mime_type", "")
        fname = doc.get("file_name", "").lower()
        if mime == "image/jpeg" or fname.endswith(".jpg") or fname.endswith(".jpeg"):
            caption = msg.get("caption", "").strip().lower()
            slideshow = "#slide" in caption
            return {"type": "photo", "document_id": doc["file_id"],
                    "file_size": doc.get("file_size", 0), "slideshow": slideshow}
        # GIF or video sent as a raw file (mime image/gif or video/mp4)
        if mime in ("image/gif", "video/mp4") or fname.endswith(".gif"):
            thumb = doc.get("thumb") or doc.get("thumbnail")
            if thumb:
                return {"type": "gif", "thumb_id": thumb["file_id"]}
            return {"type": "gif"}
    print("classify: unhandled msg keys=", list(msg.keys()))
    return None


async def polling_loop():
    """Asyncio task — polls Telegram every 30 seconds."""
    # Wait for DHCP to assign a real IP before attempting any network calls.
    # presto.connect() returns on WiFi association, before DHCP finishes.
    import network as _net
    _wlan = _net.WLAN(_net.STA_IF)
    dhcp_wait = 0
    while True:
        cfg = _wlan.ifconfig()  # (ip, mask, gateway, dns)
        if cfg[0] != '0.0.0.0' and cfg[2] != '0.0.0.0':
            break  # both IP and gateway are set — routing table is ready
        dhcp_wait += 1
        if dhcp_wait % 5 == 0:
            print("poll: waiting for DHCP ({} s)... cfg={}".format(dhcp_wait * 2, cfg))
        if dhcp_wait >= 30:  # 60 s — give up and retry
            print("poll: DHCP timeout, reconnecting...")
            wifi.connect()
            dhcp_wait = 0
        await asyncio.sleep(2)
    cfg = _wlan.ifconfig()
    print("poll: ip={} gw={} dns={}".format(cfg[0], cfg[2], cfg[3]))
    await asyncio.sleep(2)  # brief settle after gateway route is injected
    offset = 0
    updates = get_updates(0)
    for u in updates:
        offset = max(offset, u["update_id"] + 1)
    print("poll: starting at offset", offset)
    while True:
        try:
            if not wifi.ensure_connected():
                await asyncio.sleep(15)
                continue
            updates = get_updates(offset)
            for update in updates:
                uid = update["update_id"]
                offset = max(offset, uid + 1)
                if uid in _seen_ids:
                    continue
                _seen_ids.add(uid)
                if len(_seen_ids) > 200:
                    _seen_ids.clear()
                # Also dedup on message_id: Telegram can send both a `message`
                # and an `edited_message` update for the same message (e.g. when
                # it finishes attaching a GIF thumbnail after initial delivery).
                raw = update.get("message") or update.get("edited_message") or {}
                mid = raw.get("message_id")
                if mid:
                    if mid in _seen_msg_ids:
                        continue
                    _seen_msg_ids.add(mid)
                    if len(_seen_msg_ids) > 200:
                        _seen_msg_ids.clear()
                msg = classify_message(update)
                if msg is None:
                    continue
                if msg["type"] == "command":
                    if msg["command"] == "status":
                        _send_status()
                    elif msg["command"] == "help":
                        _send_help()
                    elif msg["command"] == "mood":
                        import led_manager
                        colour = msg.get("colour", "")
                        if colour == "off":
                            led_manager.clear_mood()
                            send_message(secrets.SHAH_CHAT_ID,
                                "Mood cleared — back to warm amber.")
                        elif colour in _MOODS:
                            r, g, b = _MOODS[colour]
                            led_manager.set_mood(r, g, b)
                            send_message(secrets.SHAH_CHAT_ID,
                                "Mood set to {}.".format(colour))
                        else:
                            send_message(secrets.SHAH_CHAT_ID,
                                "Unknown mood. Try: rose, calm, happy, red, off")
                    elif msg["command"] == "unknown":
                        send_message(secrets.SHAH_CHAT_ID,
                            "Unknown command. Try /help")
                    continue
                if msg["type"] == "photo":
                    if "document_id" in msg:
                        if msg.get("file_size", 0) > _PHOTO_SIZE_LIMIT:
                            send_message(secrets.SHAH_CHAT_ID, "File too large (>5 MB) — send a smaller version.")
                            continue
                        file_id = msg["document_id"]
                    else:
                        file_id = check_photo_size(msg["photo"])
                    if file_id is None:
                        continue
                    dest = "/sd/cache/p{}.jpg".format(utime.ticks_ms())
                    if download_file(file_id, dest):
                        state.queue_push({"type": "photo", "path": dest, "slideshow": msg.get("slideshow", False)})
                    else:
                        print("Photo download failed, skipping")
                elif msg["type"] == "gif":
                    thumb_id = msg.get("thumb_id")
                    if thumb_id:
                        dest = "/sd/cache/p{}.jpg".format(utime.ticks_ms())
                        if download_file(thumb_id, dest):
                            state.queue_push({"type": "gif", "path": dest})
                        else:
                            state.queue_push({"type": "gif"})
                    else:
                        state.queue_push({"type": "gif"})
                elif msg["type"] == "text":
                    state.queue_push({"type": "text", "body": msg["body"]})
        except Exception as e:
            print("polling_loop error:", e)
            gc.collect()
        await asyncio.sleep(15)
