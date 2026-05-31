# LoveBox

A Telegram-driven desk companion built on the [Pimoroni Presto](https://shop.pimoroni.com/products/presto) (RP2350). Always-on rotating photo frame that lights up and prompts for a tap when a message arrives.

![LoveBox device showing slideshow]

---

## What it does

- **Slideshow** — cycles through photos on the SD card with swipe left/right navigation
- **Message delivery** — Shah sends a text, photo, or GIF via Telegram; the device LEDs pulse and a "tap to reveal" screen appears
- **Reply buttons** — Beth taps to read, then replies with a preset button ("Love it", "Haha", "Call me!"); Shah gets a read receipt ("Seen ✓") the moment Beth taps
- **LED mood system** — `/mood <colour>` sets the ambient LED glow and notification pulse colour, persisted across reboots
- **WiFi AP portal** — if no known network is found on boot, the device broadcasts `LoveBox-Setup` and serves a credential form at `http://192.168.4.1`; learned networks are saved to the SD card automatically

---

## Hardware

- [Pimoroni Presto](https://shop.pimoroni.com/products/presto) — RP2350, 4" 480×480 IPS touchscreen, 7 rear RGB LEDs, CYW43 Wi-Fi, SD card slot
- MicroSD card (any size)

---

## Project structure

```
src/
  main.py           # app loop, state machine, boot sequence
  telegram.py       # Telegram polling, file download, command handling
  display_manager.py# all rendering (PicoGraphics + jpegdec)
  slideshow.py      # SD photo rotation, wall-clock timed, swipe gestures
  touch_handler.py  # FT6236 touch, tap/swipe detection
  led_manager.py    # breath animation, mood system
  wifi.py           # multi-network scan+connect, learned networks
  ap_portal.py      # WiFi setup portal — AP mode + DNS + HTTP server
  state.py          # app state constants + message queue
  hardware.py       # Presto singleton
  secrets.py        # credentials template — fill in and copy to device

Utils/
  presto_crop.py    # PC utility: smart-crop any photo to 480×480 baseline JPEG
  presto_gui.py     # GUI wrapper for presto_crop.py
  presto_photos/    # sample 480×480 photos ready to copy to SD card

docs/
  TEST_PLAN.md      # full physical + software test plan
```

---

## Setup

### 1. Telegram bot

1. Message [@BotFather](https://t.me/BotFather) → `/newbot` → copy the token
2. Find your Telegram user ID (message [@userinfobot](https://t.me/userinfobot))

### 2. Credentials

Copy `src/secrets.py` to the device and fill in your values:

```python
WIFI_NETWORKS = [
    ("your-home-wifi",  "home-password"),
    ("your-other-wifi", "other-password"),
]

BOT_TOKEN = "your-telegram-bot-token"   # from @BotFather
SHAH_CHAT_ID = 123456789                # your Telegram user ID (integer)
```

Add as many networks as you like — the device scans first and connects to whichever has the best signal.

### 3. SD card

Create these directories on the SD card:

```
/sd/photos/    ← slideshow images (480×480 baseline JPEG)
/sd/cache/     ← temp downloads (created automatically)
```

Optionally place a custom `arrived.jpg` (480×480 baseline JPEG) at `/sd/arrived.jpg` for a personalised arrival screen.

### 4. Photos

Photos must be **480×480 baseline JPEG** — progressive JPEG (the default from most phones and social apps) will not display. Use `Utils/presto_crop.py` to batch-convert on your PC:

```bash
python Utils/presto_crop.py /path/to/source/photos /path/to/sd/photos
```

This auto-detects faces, smart-crops to square, resizes to 480×480, and saves as baseline JPEG. Sample photos are included in `Utils/presto_photos/`.

### 5. Flash

Copy everything in `src/` to the root of the Presto's flash. The device runs `boot.py` on startup, which adds `/src` to the path and imports `main`.

---

## Telegram commands

| Command | Effect |
|---------|--------|
| `/status` | Reply with network, IP, signal, uptime, photo count, queue depth |
| `/mood <colour>` | Set LED colour for idle glow and notification pulse |
| `/mood off` | Revert to default warm amber |
| `/help` | List all commands and mood colour names |

**Mood colours:** `rose · red · orange · yellow · green · mint · teal · blue · purple · lavender`

---

## Message types

| Type | How to send | Device behaviour |
|------|-------------|-----------------|
| Text | Any message (no `/` prefix) | Displayed in a bordered box, 100-char cap |
| Photo | Telegram photo | Downloads ≤320px variant (baseline JPEG) |
| Photo file | Paperclip → File → `.jpg` | Downloads directly |
| GIF | GIF picker | Displays JPEG thumbnail with "GIF" badge |
| `#slide` | Photo with `#slide` caption | Displayed + saved permanently to slideshow |

---

## WiFi AP portal

If the device can't connect to any known network on boot, it broadcasts an open access point:

- **SSID:** `LoveBox-Setup`
- **URL:** `http://192.168.4.1`

Connect your phone, navigate to the URL, submit your credentials. The device reboots, connects, and saves the network to the SD card — no portal needed next time at that location.

---

## Architecture notes

- **Single-core asyncio** — all tasks cooperative on Core 0; no `_thread`
- **Raw SSL sockets** — all HTTP via `ssl.SSLContext` + manual HTTP/1.1 framing; no `urequests`
- **Short-poll** — `getUpdates?timeout=0` every 15 seconds (average ~7s message latency)
- **Wall-clock slideshow** — interval uses `time.ticks_ms` deadlines, immune to HTTP blocking
- **Three-tier WiFi priority** — `wifi_override.json` → `wifi_learned.json` → `secrets.WIFI_NETWORKS`

---

## Known limitations

- **Offline message loss** — messages sent while the device is offline are discarded on reconnect (intentional, avoids replaying a stale backlog). Use `/status` to confirm the device is live before sending.
- **Progressive JPEG** — `jpegdec` only decodes baseline JPEG. Photos from Facebook, Instagram, and WhatsApp are typically progressive — run them through `presto_crop.py` first.
- **GIF playback** — Telegram converts GIFs to MP4; no MP4 decoder exists for MicroPython/Presto. A representative JPEG thumbnail is displayed instead.
