## 1. Project Scaffold & Secrets

- [x] 1.1 Create `secrets.py` with `SSID`, `PASSWORD`, `BOT_TOKEN`, `SHAH_CHAT_ID` (add to `.gitignore`)
- [x] 1.2 Create `main.py` entry point that imports and launches the app
- [x] 1.3 Create SD card mount helper that mounts to `/sd` and returns success/failure without crashing
- [x] 1.4 Verify SD directories exist (`/sd/photos`, `/sd/cache`), creating them if absent

## 2. Wi-Fi Connection (`wifi.py`)

- [x] 2.1 Implement `connect()` — blocking connect with 30s timeout, returns bool
- [x] 2.2 Implement `ensure_connected()` — non-blocking check + reconnect trigger for use in loops
- [x] 2.3 Expose a module-level `is_connected` bool updated by both functions
- [x] 2.4 Multi-network support added: `WIFI_NETWORKS` list in secrets.py; scans first to prioritise visible networks, falls back to trying all in order. Confirmed working.

## 3. Shared State & Inter-Core Queue (`state.py`)

- [x] 3.1 Define app state constants: `IDLE`, `ARRIVED`, `REVEALING`, `READING`
- [x] 3.2 Message queue implemented as simple `list` with `queue_push()` / `queue_pop()` — no lock needed (single-core asyncio, not `_thread`)
- [x] 3.3 `current_message` dict set when message is popped from queue
- [x] 3.4 *(deviation)* Core 1 heartbeat not implemented — architecture changed to single-core asyncio; no watchdog needed

## 4. LED Manager (`led_manager.py`)

- [x] 4.1 Initialise Presto RGB LEDs
- [x] 4.2 `set_idle()` — static low-brightness state
- [x] 4.3 `start_pulse()` — 5-second breath cycle, 5% brightness floor (never fully dark)
- [x] 4.4 `stop_pulse()` — cancels pulse task
- [x] 4.5 `set_solid(r, g, b)` — wired for v2 /mood support
- [x] 4.6 Pulse yields correctly; confirmed does not block display rendering

## 5. Telegram Polling (`telegram.py`)

- [x] 5.1 `get_updates(offset)` — raw SSL socket HTTP (no urequests); chunked transfer decoding
- [x] 5.2 `download_file(file_id, dest_path)` — streaming download to SD in 4 KB chunks
- [x] 5.3 `send_message(chat_id, text)` — posts to sendMessage, returns bool
- [x] 5.4 `classify_message(update)` — handles text, photo, JPEG file uploads, and GIF thumbnails. *(deviation from spec)* GIFs NOT deferred — animation.thumb downloaded as JPEG and displayed with "GIF" badge
- [x] 5.5 `check_photo_size()` — prefers ≤320px variants (baseline JPEG); larger variants are progressive and fail jpegdec
- [x] 5.6 `polling_loop()` — asyncio task (not Core 1 thread); getUpdates → classify → download → queue push → sleep 30s
- [x] 5.7 Broad exception handler with continue on error
- [x] 5.8 *(deviation)* Launched as `asyncio.create_task()` not `_thread.start_new_thread()`
- [x] 5.9 Text, photo, file upload, GIF all confirmed working end-to-end
- [x] 5.10 *(added)* Dedup via `_seen_ids` (update_id) + `_seen_msg_ids` (message_id) — prevents double-processing from offset resets and message/edited_message pairs
- [x] 5.11 *(added)* DHCP wait loop at startup; DNS caching after first resolution

## 6. Photo Slideshow (`slideshow.py`)

- [x] 6.1 `load_photo_list()` — scans `/sd/photos/*.jpg`
- [x] 6.2 `display_jpeg(path)` — in `display_manager.py`; returns True/False; bad photos removed from in-memory rotation
- [x] 6.3 `slideshow_task()` — wall-clock timed (not iteration-count) to prevent HTTP blocking from compressing display time; 5s cooldown after message dismiss
- [x] 6.4 `save_received_photo(path)` — copies from cache to `/sd/photos/`, appends to live rotation
- [x] 6.5 Progressive JPEG / corrupt file handled: skipped immediately, removed from rotation
- [x] 6.6 Slideshow confirmed cycling correctly; pauses correctly during ARRIVED/READING states

## 7. Message Display (`display_manager.py`)

- [x] 7.1 `show_arrived_screen()` — loads `/sd/arrived.jpg` if present, else text fallback
- [x] 7.2 `show_reveal_transition()` — 500ms fade (20 steps × 25ms)
- [x] 7.3 `render_reading_screen(message)` — text (bitmap8, ROSE border, 100-char cap), photo (jpegdec, fit-to-area), gif (thumbnail + GIF badge)
- [x] 7.4 *(deviation)* GIF display implemented in v1 via JPEG thumbnail + badge overlay

## 8. Touch Handler (`touch_handler.py`)

- [x] 8.1 `poll_touch()` — returns `(x, y)` or None
- [x] 8.2 `hit_test(x, y, rects)` — returns index or -1, with 8px tolerance
- [x] 8.3 `wait_for_tap()` — waits for press AND release before returning (prevents bleed-through)
- [x] 8.4 Touch confirmed working; reply buttons and miss-taps behave correctly

## 9. Main App Loop & State Machine (`main.py`)

- [x] 9.1 Boot: mount SD → connect Wi-Fi → init display/LEDs/touch → start tasks
- [x] 9.2 `app_loop()` — 50ms tick, queue pop, state dispatch
- [x] 9.3 `handle_arrived()` — arrived screen, LED pulse, wait for tap, send "Seen ✓" to Shah, trigger reveal
- [x] 9.4 `handle_revealing()` — fade transition → READING
- [x] 9.5 `handle_reading()` — reply buttons, toast on failure, 2-min timeout, path cleanup, slideshow save on #slide
- [x] 9.7 *(deviation)* Core 1 watchdog not needed — single-core asyncio
- [x] 9.8 Wi-Fi indicator badge shown when disconnected

## 10. End-to-End Integration — All Confirmed ✅

- [x] 10.1 Text message: ARRIVED → LED pulse → reveal → display → reply delivered to Shah
- [x] 10.2 Photo: downloaded, displayed, saved to slideshow via #slide caption
- [x] 10.3 Oversized photo: bot replies to Shah with warning
- [x] 10.4 Wi-Fi drop: reconnects, polling resumes
- [x] 10.5 Extended operation: stable (no observed crashes)
- [x] 10.6 Unknown sender: silently ignored by SHAH_CHAT_ID filter

## Additional (beyond original spec)

- [x] A.1 GIF support via animation JPEG thumbnail (animation check before document check)
- [x] A.2 JPEG file upload support (.jpg documents)
- [x] A.3 `#slide` caption routes photos to permanent slideshow
- [x] A.4 "Seen ✓" notification sent to Shah when Beth taps arrived screen
- [x] A.5 Reply failure toast with 2.5s display
- [x] A.6 Multi-network WiFi with scan-and-prioritise
- [x] A.7 presto_crop.py PC utility — face-detect smart crop to 480×480 baseline JPEG
- [x] A.8 Message dedup (_seen_ids + _seen_msg_ids)
- [x] A.9 Wall-clock slideshow interval (immune to HTTP blocking)
- [x] A.10 Progressive JPEG auto-skip in slideshow

---

## V2 — WiFi Resilience ✅

- [x] V2.1 `ap_portal.py` — AP mode portal on boot WiFi failure; broadcasts "LoveBox-Setup"; DNS server (UDP 53) hijacks all queries to 192.168.4.1 to trigger OS captive portal notification; HTTP server (TCP 80) serves credential form; saves to `/sd/wifi_override.json`; 5-minute timeout then continues without WiFi
- [x] V2.2 `wifi.py` — learned networks: `_networks()` order is override → `wifi_learned.json` → `secrets.WIFI_NETWORKS`; `_promote_override()` auto-graduates portal credentials to permanent learned list on first successful connect, then deletes the override file
- [x] V2.3 Runtime WiFi loss banner — `state.wifi_lost` flag set every 50ms tick; full-width ROSE "No WiFi | tap to restart" banner overlaid on slideshow via `display_manager._draw_wifi_badge()`; tap within top 36px triggers `machine.reset()`; slideshow now tracks touch Y coordinate for this
- [x] V2.4 `telegram.py` socket leak fix — `_open_ssl()` now wraps `connect()` + `wrap_socket()` in try/except and explicitly closes raw socket on failure; `gc.collect()` added to all error paths; prevents CYW43 socket pool exhaustion (ENOMEM cascade)
- [x] V2.5 `telegram.py` DHCP gateway fix — polling startup loop now checks both `ifconfig()[0]` (IP) and `ifconfig()[2]` (gateway) non-zero before starting; resolves EHOSTUNREACH on Android hotspot where gateway route injection lags IP assignment
- [x] V2.6 `main.py` — one silent retry after 3s before falling back to AP portal; resolves CYW43 radio settle time after `machine.reset()`
- [x] V2.7 Legacy `WIFI_SSID`/`WIFI_PASSWORD` fallback removed from `wifi.py`; `secrets.py` must use `WIFI_NETWORKS` list

## V2 — Commands & Polish ✅

- [x] V2.8 `/status` command — replies with network SSID, IP, signal (dBm), uptime (h/m), photo count, queue depth; `state.queue_len()` and `slideshow.photo_count()` helpers added
- [x] V2.9 `/mood <colour>` command — 10 named colours (rose · red · orange · yellow · green · mint · teal · blue · purple · lavender); sets LED idle glow (25% brightness) AND notification pulse colour; persisted to `/sd/mood.json`; loaded on boot after SD mount; `/mood off` reverts to default warm amber
- [x] V2.10 `/help` command — lists all commands and mood colour names
- [x] V2.11 "N more waiting" badge — ROSE pill at bottom of arrived screen showing `state.queue_len()` when >1 messages queued; `show_arrived_screen()` accepts `queue_depth` parameter

## V2 — Known limitations / deferred

- [ ] V2.D1 `/timer` countdown — deferred; requires NTP sync on boot
- [ ] V2.D2 NTP sync — deferred; prerequisite for `/timer`
- [ ] V2.D3 `/eod` end-of-day card — deferred (low priority)
- [ ] V2.D4 Drawing tool — deferred (separate web project, zero device changes needed)
- [ ] V2.D5 Animated GIF playback — blocked; no MicroPython MP4/GIF decoder available for Presto
- [ ] V2.D6 Weather overlay — dropped; Beth has a window
- [ ] V2.D7 Offline message loss — known issue; messages sent to Telegram while device is offline are drained without processing on boot startup (see design.md Decision 10)
