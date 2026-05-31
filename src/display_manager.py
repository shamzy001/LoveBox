import asyncio
import jpegdec

# display and presto are set in init() to avoid circular imports at module level
_display = None
_presto = None
WIDTH = 480
HEIGHT = 480

BLACK  = None
WHITE  = None
GREY   = None
ROSE   = None
DARK   = None
BTN_BG = None

REPLY_LABELS = ["Love it", "Haha", "Call me!"]

BTN_H = 60
REPLY_RECTS = None  # set in init()

_wifi_ok = True

WIFI_BANNER_H = 36
WIFI_BANNER_RECT = None  # set in init()


def init():
    global _display, _presto, WIDTH, HEIGHT
    global BLACK, WHITE, GREY, ROSE, DARK, BTN_BG
    global BTN_H, REPLY_RECTS, WIFI_BANNER_RECT

    from hardware import display, presto, WIDTH as W, HEIGHT as H
    _display = display
    _presto = presto
    WIDTH = W
    HEIGHT = H

    BLACK  = display.create_pen(0,   0,   0)
    WHITE  = display.create_pen(255, 255, 255)
    GREY   = display.create_pen(80,  80,  80)
    ROSE   = display.create_pen(255, 100, 130)
    DARK   = display.create_pen(15,  15,  20)
    BTN_BG = display.create_pen(40,  40,  50)

    BTN_Y = HEIGHT - BTN_H
    BTN_W = WIDTH // 3
    REPLY_RECTS = [(i * BTN_W, BTN_Y, BTN_W, BTN_H) for i in range(3)]

    WIFI_BANNER_RECT = (0, 0, WIDTH, WIFI_BANNER_H)

    # Clear both layers to dark on boot
    for layer in (0, 1):
        display.set_layer(layer)
        display.set_pen(DARK)
        display.clear()
    presto.update()


def set_wifi_indicator(connected):
    global _wifi_ok
    _wifi_ok = connected


def _update():
    _presto.update()


def _draw_wifi_badge():
    if not _wifi_ok:
        _display.set_pen(ROSE)
        _display.rectangle(0, 0, WIDTH, WIFI_BANNER_H)
        _display.set_pen(WHITE)
        _display.set_font("bitmap8")
        msg = "No WiFi  |  tap to restart"
        tw = _display.measure_text(msg, scale=2)
        _display.text(msg, (WIDTH - tw) // 2, (WIFI_BANNER_H - 16) // 2, -1, 2)


def _draw_reply_buttons():
    BTN_W = WIDTH // 3
    BTN_Y = HEIGHT - BTN_H
    _display.set_font("bitmap8")
    for i, (x, y, w, h) in enumerate(REPLY_RECTS):
        _display.set_pen(BTN_BG)
        _display.rectangle(x, y, w, h)
        _display.set_pen(WHITE)
        label = REPLY_LABELS[i]
        tw = _display.measure_text(label, scale=2)
        _display.text(label, x + (w - tw) // 2, y + (h - 16) // 2, -1, 2)
    # Dividers
    _display.set_pen(DARK)
    _display.line(BTN_W,     BTN_Y, BTN_W,     HEIGHT)
    _display.line(BTN_W * 2, BTN_Y, BTN_W * 2, HEIGHT)


# -- Screens -----------------------------------------------------------------

def show_arrived_screen(queue_depth=0):
    _display.set_layer(1)
    _display.set_pen(DARK)
    _display.clear()
    try:
        j = jpegdec.JPEG(_display)
        j.open_file("/sd/arrived.jpg")
        iw, ih = j.get_width(), j.get_height()
        x, y, scale = _fit_jpeg(iw, ih, WIDTH, HEIGHT)
        j.decode(x, y, scale)
    except Exception:
        # Fallback to text if no arrived.jpg
        _display.set_font("cursive")
        _display.set_pen(WHITE)
        line1 = "You have a"
        line2 = "message <3"
        line3 = "Tap to reveal"
        for i, line in enumerate([line1, line2]):
            tw = _display.measure_text(line, scale=3)
            _display.text(line, (WIDTH - tw) // 2, HEIGHT // 2 - 60 + i * 50, -1, 3)
        _display.set_pen(GREY)
        _display.set_font("sans")
        tw = _display.measure_text(line3, scale=2)
        _display.text(line3, (WIDTH - tw) // 2, HEIGHT // 2 + 60, -1, 2)
    if queue_depth > 0:
        _display.set_font("bitmap8")
        label = "+ {} more waiting".format(queue_depth)
        tw = _display.measure_text(label, scale=2)
        pad_x, pad_y = 12, 6
        rx = (WIDTH - tw) // 2 - pad_x
        ry = HEIGHT - 42
        _display.set_pen(ROSE)
        _display.rectangle(rx, ry, tw + pad_x * 2, 16 + pad_y * 2)
        _display.set_pen(WHITE)
        _display.text(label, (WIDTH - tw) // 2, ry + pad_y, WIDTH, 2)
    _draw_wifi_badge()
    _update()


async def show_reveal_transition(steps=20, step_ms=25):
    _display.set_layer(1)
    for i in range(steps + 1):
        v = int(255 * i / steps)
        _display.set_pen(_display.create_pen(v, v, v))
        _display.clear()
        _update()
        await asyncio.sleep_ms(step_ms)


def render_reading_screen(message):
    _display.set_layer(1)
    _display.set_pen(DARK)
    _display.clear()

    content_h = HEIGHT - BTN_H - 8

    if message["type"] == "text":
        _draw_text_content(message["body"], content_h)
    elif message["type"] == "photo":
        _draw_photo_content(message.get("path", "/sd/cache/current.jpg"), content_h)
    elif message["type"] == "gif":
        _draw_gif_content(message.get("path", ""), content_h)

    _draw_reply_buttons()
    _draw_wifi_badge()
    _update()


def show_ap_portal_screen(ssid, ip):
    """Full setup screen shown while the AP portal is running."""
    _display.set_layer(1)
    _display.set_pen(DARK)
    _display.clear()
    _display.set_font("bitmap8")

    # Title
    _display.set_pen(ROSE)
    tw = _display.measure_text("WiFi Setup", scale=3)
    _display.text("WiFi Setup", (WIDTH - tw) // 2, 30, WIDTH, 3)

    # Step 1 — short label + SSID value
    _display.set_pen(GREY)
    tw = _display.measure_text("1. Connect to:", scale=2)
    _display.text("1. Connect to:", (WIDTH - tw) // 2, 74, WIDTH, 2)
    _display.set_pen(WHITE)
    tw = _display.measure_text(ssid, scale=2)
    _display.text(ssid, (WIDTH - tw) // 2, 100, WIDTH, 2)

    # Divider
    _display.set_pen(GREY)
    _display.rectangle(60, 134, WIDTH - 120, 1)

    # Step 2 — short label + IP value (larger)
    _display.set_pen(GREY)
    tw = _display.measure_text("2. Open browser at:", scale=2)
    _display.text("2. Open browser at:", (WIDTH - tw) // 2, 150, WIDTH, 2)
    _display.set_pen(WHITE)
    tw = _display.measure_text(ip, scale=3)
    _display.text(ip, (WIDTH - tw) // 2, 176, WIDTH, 3)

    # Hint
    _display.set_pen(GREY)
    tw = _display.measure_text("(or tap the notification)", scale=2)
    _display.text("(or tap the notification)", (WIDTH - tw) // 2, 270, WIDTH, 2)

    _update()


def show_boot_status(line1, line2=None, ok=True):
    """Show a two-line status screen during boot."""
    _display.set_layer(1)
    _display.set_pen(DARK)
    _display.clear()
    _display.set_font("bitmap8")
    _display.set_pen(WHITE if ok else ROSE)
    tw = _display.measure_text(line1, scale=2)
    _display.text(line1, (WIDTH - tw) // 2, HEIGHT // 2 - 20, -1, 2)
    if line2:
        _display.set_pen(GREY)
        tw = _display.measure_text(line2, scale=2)
        _display.text(line2, (WIDTH - tw) // 2, HEIGHT // 2 + 14, -1, 2)
    _update()


def show_idle():
    """Clear screen to dark when returning to idle."""
    _display.set_layer(1)
    _display.set_pen(DARK)
    _display.clear()
    _update()


def show_toast(text):
    """Overlay a brief toast message without clearing the screen."""
    _display.set_pen(ROSE)
    _display.rectangle(20, HEIGHT // 2 - 20, WIDTH - 40, 40)
    _display.set_pen(WHITE)
    tw = _display.measure_text(text, scale=1)
    _display.text(text, (WIDTH - tw) // 2, HEIGHT // 2 - 8, -1, 1)
    _update()


def _draw_text_content(text, max_h):
    # Box sits inside the content area with a ROSE border
    BOX_MARGIN = 16
    BOX_X = BOX_MARGIN
    BOX_Y = BOX_MARGIN
    BOX_W = WIDTH - BOX_MARGIN * 2
    BOX_H = max_h - BOX_MARGIN * 2

    # Border: filled ROSE rect, then DARK inner rect
    _display.set_pen(ROSE)
    _display.rectangle(BOX_X, BOX_Y, BOX_W, BOX_H)
    _display.set_pen(DARK)
    _display.rectangle(BOX_X + 2, BOX_Y + 2, BOX_W - 4, BOX_H - 4)

    PAD = 16
    text_x = BOX_X + PAD
    text_y = BOX_Y + PAD
    max_w = BOX_W - PAD * 2

    _display.set_font("bitmap8")
    _display.set_pen(WHITE)

    MAX_CHARS = 100
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS - 3] + "..."

    _display.text(text, text_x, text_y, max_w, 2)


def _draw_gif_content(path, max_h):
    """Show the GIF's JPEG thumbnail with a GIF badge, or a text placeholder."""
    if path:
        # Display thumbnail like a photo
        _draw_photo_content(path, max_h)
        # GIF badge in top-left corner
        _display.set_font("bitmap8")
        _display.set_pen(ROSE)
        _display.rectangle(4, 4, 40, 18)
        _display.set_pen(WHITE)
        _display.text("GIF", 9, 6, -1, 1)
    else:
        # No thumbnail — text placeholder
        BOX_MARGIN = 16
        BOX_X = BOX_MARGIN
        BOX_Y = BOX_MARGIN
        BOX_W = WIDTH - BOX_MARGIN * 2
        BOX_H = max_h - BOX_MARGIN * 2
        _display.set_pen(ROSE)
        _display.rectangle(BOX_X, BOX_Y, BOX_W, BOX_H)
        _display.set_pen(DARK)
        _display.rectangle(BOX_X + 2, BOX_Y + 2, BOX_W - 4, BOX_H - 4)
        _display.set_font("bitmap8")
        _display.set_pen(ROSE)
        label = "Animated GIF"
        tw = _display.measure_text(label, scale=2)
        _display.text(label, (WIDTH - tw) // 2, BOX_Y + BOX_H // 2 - 20, -1, 2)
        _display.set_pen(WHITE)
        sub = "tap a button to reply"
        tw2 = _display.measure_text(sub, scale=1)
        _display.text(sub, (WIDTH - tw2) // 2, BOX_Y + BOX_H // 2 + 14, -1, 1)


def _draw_photo_content(path, max_h):
    try:
        j = jpegdec.JPEG(_display)
        j.open_file(path)
        iw, ih = j.get_width(), j.get_height()
        x, y, scale = _fit_jpeg(iw, ih, WIDTH, max_h)
        j.decode(x, y, scale)
    except Exception as e:
        print("Photo display error:", e)
        _display.set_pen(GREY)
        _display.set_font("bitmap8")
        _display.text("Photo unavailable", 20, max_h // 2 - 8, -1, 2)


def display_jpeg(path):
    """Full-screen JPEG for the slideshow. Returns True on success."""
    _display.set_layer(1)
    _display.set_pen(BLACK)
    _display.clear()
    try:
        j = jpegdec.JPEG(_display)
        j.open_file(path)
        iw, ih = j.get_width(), j.get_height()
        x, y, scale = _fit_jpeg(iw, ih, WIDTH, HEIGHT)
        j.decode(x, y, scale)
        _draw_wifi_badge()
        _update()
        return True
    except Exception as e:
        print("display_jpeg error:", path, e)
        return False


def _fit_jpeg(iw, ih, max_w, max_h):
    """Pick the best power-of-2 JPEG scale to fit within max_w x max_h. Returns (x, y, scale)."""
    for scale, div in [
        (jpegdec.JPEG_SCALE_FULL,    1),
        (jpegdec.JPEG_SCALE_HALF,    2),
        (jpegdec.JPEG_SCALE_QUARTER, 4),
        (jpegdec.JPEG_SCALE_EIGHTH,  8),
    ]:
        sw, sh = iw // div, ih // div
        if sw <= max_w and sh <= max_h:
            return (max_w - sw) // 2, (max_h - sh) // 2, scale
    sw, sh = iw // 8, ih // 8
    return (max_w - sw) // 2, (max_h - sh) // 2, jpegdec.JPEG_SCALE_EIGHTH
