## Why

Beth's desk needs a dedicated ambient device that surfaces personal messages from Shah without the noise of a phone — something that sits as a photo frame, wakes up with intention when a message arrives, and lets her reply with a single tap. The Pimoroni Presto (RP2350, 480×480 touchscreen, rear RGB LEDs, Wi-Fi, SD card) running MicroPython is the target platform.

## What Changes

- New MicroPython firmware project from scratch — no existing codebase
- Wi-Fi connection management with automatic reconnection
- Telegram Bot polling on Core 1 (`_thread`) so UI never freezes waiting for network
- Message arrival flow: LED pulse → "Shah sent you something — tap to reveal" → message display → preset reply buttons
- Message types: plain text, photo (displayed + added to slideshow rotation)
- Idle screen: rotating JPEG slideshow from SD card (pre-loaded base set; new photos added via Telegram)
- Preset reply buttons post-read: ❤️ / 😂 / "call me" — each sends a message back to Shah's Telegram
- Secrets stored in `secrets.py` on device flash (Wi-Fi SSID/password, bot token, Shah's chat ID)

## Capabilities

### New Capabilities

- `wifi-connection`: Manages Wi-Fi initialisation on boot and silent reconnection on drop
- `telegram-polling`: Runs on Core 1 via `_thread`; calls getUpdates, parses messages, pushes to a shared thread-safe queue; handles photos by downloading to SD before signalling Core 0
- `message-handling`: Core 0 reads from the queue, identifies message type (text / GIF / photo), drives the arrival → reveal → display state machine
- `led-animations`: Rear RGB LED control — pulsing animation on message arrival, steady idle state; brightness and colour managed as a simple driver layer
- `photo-slideshow`: Idle screen that cycles through JPEGs stored in `/photos` on SD; advances on a configurable timer; new photos added by Telegram flow are appended to the rotation
- `touch-ui`: Touch input dispatch — maps raw coordinates to UI states (idle tap to reveal, reply button taps, return-to-idle tap); renders "tap to reveal" prompt and the three preset reply buttons

### Modified Capabilities

*(none — greenfield project)*

## Impact

- **Hardware**: Pimoroni Presto — RP2350 dual-core, 8 MB PSRAM, 480×480 IPS touchscreen, 7× rear RGB LEDs, CYW43 Wi-Fi, SD card slot
- **Runtime**: MicroPython with `asyncio` (Core 0) and `_thread` (Core 1)
- **External APIs**: Telegram Bot API — `getUpdates` for polling, `sendMessage` for preset replies, `getFile`/file download for media
- **Storage**: SD card — `/photos/*.jpg` for slideshow, `/cache/current.jpg` for received photo cache
- **Secrets**: `secrets.py` — never committed to version control
- **Dependencies**: Presto's bundled MicroPython libs (`picographics`, `pimoroni`, `machine`, `network`, `urequests` or raw socket HTTP)
