## Context

Greenfield MicroPython firmware for the Pimoroni Presto — a RP2350-based desk device with a 4" 480×480 IPS touchscreen, 7 rear RGB LEDs, CYW43 Wi-Fi, SD card slot, and 8 MB PSRAM. The device must simultaneously run a photo slideshow, poll Telegram for new messages, animate LEDs, and respond to touch — all within MicroPython's cooperative runtime.

The key hardware constraint is that MicroPython's `asyncio` is single-threaded cooperative multitasking: a blocking call (HTTP request, file I/O) stalls all coroutines. The RP2350 has two ARM Cortex-M33 cores, which MicroPython exposes via `_thread`.

> **Implementation note:** The original design chose dual-core (`_thread` on Core 1 for polling). In practice, `urequests` was never used — all HTTP is done via raw `ssl.SSLContext` sockets with short timeouts. The blocking duration (2–5s per poll every 30s) proved acceptable for single-core asyncio. The dual-core approach was abandoned in favour of a simpler, fully-asyncio architecture. See Decision 1 below.

---

## Goals / Non-Goals

**Goals:**
- Stable, always-on operation with graceful Wi-Fi reconnection
- Telegram polling that never visibly freezes the UI
- Complete message flow: arrival → reveal → display → reply → idle
- Idle photo slideshow with smooth transitions
- LED animations that feel alive and responsive

**Non-Goals (v1):**
- Weather overlay (deferred to v2)
- /mood, /timer commands (deferred to v2)
- Scheduled auto-messages (deferred to v2)
- OTA firmware updates
- Web-based configuration UI / AP setup mode

---

## Decisions

### Decision 1: Single-core asyncio (deviation from original spec)

**Original plan:** Telegram HTTP polling on Core 1 via `_thread`; Core 0 runs `asyncio` for UI.

**What was built:** Everything on Core 0 as asyncio tasks. `polling_loop` is a standard `asyncio.create_task()`.

**Why it changed:** The original plan assumed `urequests` would be used for HTTP, which blocks for the full request duration. In implementation, all HTTP was done via raw `ssl.SSLContext` sockets with a 15s timeout. The actual blocking time per poll (2–5s every 30s) is short enough that asyncio cooperative scheduling handles it without visible UI hitches. Single-core asyncio is simpler — no shared-memory race conditions, no lock on the queue, no watchdog needed.

**Consequences:**
- `_thread.allocate_lock()` mutex on the queue → replaced by a plain `list` (no lock needed)
- Core 0 heartbeat watchdog → not implemented (nothing to watch)
- Core 1 crash recovery → not needed

### Decision 2: Raw SSL sockets instead of urequests

**What was built:** All HTTP calls use `ssl.SSLContext` wrapping a raw `socket.socket()`. Manual HTTP/1.1 request framing, response parsing, and chunked transfer decoding are implemented in `telegram.py`.

**Why:** `urequests` was unreliable for streaming downloads and chunked responses on the Presto's MicroPython build. Raw sockets gave full control over timeouts, chunked decoding, and streaming file writes to SD.

**Notable implementation details:**
- DNS result cached in `_HOST_ADDR` after first resolution (avoids repeated DNS lookups)
- `_recv_all()` for small responses (getUpdates, sendMessage)
- `_stream_to_file()` for media downloads — writes directly to SD in 4 KB chunks without buffering the full file in RAM

### Decision 3: GIF support via JPEG thumbnail (deviation from original spec)

**Original plan:** GIFs explicitly deferred to v2. Rationale: Telegram converts GIFs to MP4 (`animation` type); MicroPython cannot decode MP4.

**What was built:** GIFs supported in v1 via the animation object's JPEG thumbnail. Every Telegram `animation` message includes `thumb`/`thumbnail` — a JPEG preview frame. The device downloads this thumbnail and displays it full-screen with a "GIF" badge overlay. Not true animation, but Beth sees a representative frame and knows it's a GIF.

**Implementation detail:** `classify_message` checks `animation` before `document` — GIF messages carry both fields and the animation branch must win.

### Decision 4: Photo slideshow as asyncio Task ✓

**Unchanged from spec.** A persistent `asyncio.Task` manages the slideshow with one refinement: the interval uses a wall-clock deadline (`time.ticks_ms`) rather than counting `asyncio.sleep(1)` iterations. This prevents blocking HTTP calls from compressing the display time (expired sleep timers fire in rapid succession when the scheduler resumes after a block).

### Decision 5: State machine for message flow ✓

**Unchanged from spec.**

`IDLE → ARRIVED → REVEALING → READING → IDLE`

- **IDLE**: slideshow running, LEDs ambient
- **ARRIVED**: LEDs pulsing, arrival screen, waiting for tap
- **REVEALING**: 500ms fade transition (20 steps × 25ms), auto-advances
- **READING**: message + reply buttons shown simultaneously, 2-min timeout

### Decision 6: secrets.py for credentials — extended

**Built as specced, plus:** `WIFI_NETWORKS` list added for multi-network support. On `connect()`, the device scans visible networks first and connects to the best available known SSID. Falls back to trying all networks in order if scan fails. Backwards-compatible with single `WIFI_SSID`/`WIFI_PASSWORD`.

### Decision 7: File layout — minor changes

**Flash (`/`):** `boot.py` (auto-start shim), `src/` directory containing all app modules.

**SD (`/sd/`):**
- `/sd/photos/*.jpg` — slideshow images (480×480 baseline JPEG, pre-processed via `presto_crop.py`)
- `/sd/cache/p{ticks_ms}.jpg` — temp downloads, timestamped (original spec used `current.jpg`; timestamped names needed to support queued messages without overwriting)
- `/sd/arrived.jpg` — custom arrival screen image

### Decision 8: Message deduplication (not in original spec)

**Added:** Two-layer dedup to prevent double-processing:
- `_seen_ids` — dedup on `update_id` (guards against offset resets between polls)
- `_seen_msg_ids` — dedup on `message_id` (guards against Telegram sending both a `message` and `edited_message` update for the same message, e.g. when attaching a GIF thumbnail after initial delivery)

The original spec noted "worst case: Beth sees the same message twice — acceptable for v1." In practice this happened consistently and was fixed.

### Decision 9: "Seen ✓" notification (not in original spec)

**Added:** When Beth taps the arrived screen, `telegram.send_message(SHAH_CHAT_ID, "Seen ✓")` is called before the reveal transition. Shah receives a read receipt for every message regardless of whether Beth replies.

---

## Risks / Trade-offs (as-built)

**[Resolved] Duplicate updates** → Fixed via `_seen_ids` + `_seen_msg_ids` dedup.

**[Accepted] Blocking HTTP on asyncio** → Raw socket calls block Core 0 for 2–5s during each poll. Slideshow timing uses wall-clock deadlines to absorb this. No visible UI hitches observed.

**[Accepted] Progressive JPEG limitation** → `jpegdec` only decodes baseline JPEG. Telegram photo variants ≥480px are progressive; capped at ≤320px variants. Photos for slideshow must be pre-processed via `presto_crop.py` on PC before copying to SD.

**[Accepted] GIF = thumbnail only** → True animation not possible (MP4 undecoded). JPEG thumbnail with badge is the v1 solution.

**[Resolved] SD card not mounted** → Slideshow skipped gracefully; photo/GIF messages show placeholder text.

**[Resolved] Wi-Fi drops** → `ensure_connected()` called before each poll; reconnects to best available network from `WIFI_NETWORKS` list.


---

## Open Questions → v2 (now resolved below)

---

## V2 Decisions

### Decision 10: Offline message loss (known, accepted)

**Issue:** Messages sent to the Telegram bot while the device is offline are silently discarded on the next boot.

**Root cause:** The startup sequence calls `get_updates(0)` and advances `offset` past all pending updates without calling `classify_message` or `queue_push`. This "drain" was intentional — to avoid flooding Beth's screen with a backlog of hours-old messages — but it means messages sent during an outage are permanently lost from the device's perspective. Telegram itself retains them until acknowledged; the device simply acknowledges and discards them.

**Decision:** Accept. The use case (a desk companion that displays timely messages) is better served by starting fresh than by replaying a multi-hour backlog. Shah should resend anything important after confirming the device is back online via `/status`.

**Mitigation:** `/status` command lets Shah confirm the device is live before sending. If offline message delivery ever becomes a requirement, the startup drain can be replaced with processing (call `classify_message` on startup updates, up to a configurable limit).

### Decision 11: Single-core asyncio confirmed for V2

**Re-evaluated:** V2 added WiFi AP portal, command handling, mood persistence, and badge rendering. None introduced new long-blocking operations in the asyncio event loop. The AP portal runs before the event loop starts (boot sequence). Commands are handled inline in `polling_loop` with sub-second network calls. Conclusion: no compelling reason to migrate to dual-core `_thread` for the current feature set. Deferred indefinitely.

### Decision 12: CYW43 socket pool management

**Added:** `_open_ssl()` now explicitly closes the raw `socket.socket()` in a try/except if `connect()` or `wrap_socket()` fails, before re-raising. Without this, failed connections left socket slots occupied until GC ran; with 4 CYW43 slots available, 5 consecutive failures produced ENOMEM. `gc.collect()` added to all error paths as belt-and-suspenders.

### Decision 13: DHCP gateway check

**Added:** The polling startup loop previously waited only for `ifconfig()[0] != '0.0.0.0'` (IP assigned). On Android hotspot, the gateway route (`ifconfig()[2]`) can lag behind IP assignment. TCP connections attempted before the gateway route is injected fail with EHOSTUNREACH even though DNS resolves correctly (DNS queries go to the local hotspot resolver; TCP to external IPs needs the default route). Fix: wait for both IP and gateway to be non-zero.

### Decision 14: WiFi credential persistence

**Added:** Three-tier network priority: `wifi_override.json` (one-time portal credential) → `wifi_learned.json` (accumulated portal history) → `secrets.WIFI_NETWORKS` (hardcoded). On first successful connect via override, credentials are promoted to `wifi_learned.json` and the override file is deleted. This means the AP portal only needs to be used once per new location; subsequent boots at that location connect automatically.

## Remaining open questions (deferred)

- `/timer` — requires NTP sync on boot; NTP not yet implemented
- Animated GIF playback — requires MP4 or GIF decoder, none available for MicroPython/Presto
- Drawing tool — separate web app on Shah's side; zero device changes required
