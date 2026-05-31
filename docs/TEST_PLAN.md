# LoveBox Test Plan

Physical and software tests to verify the full V2 stack. Run in order — earlier sections catch issues that would confuse later ones.

---

## 1. Boot & Power

| # | Test | Expected |
|---|------|----------|
| 1.1 | Cold power-on with known WiFi in range | Boot screen → "Connecting…" → SSID + IP shown for 2s → slideshow starts |
| 1.2 | Cold power-on with NO known WiFi in range | Boot screen → retry attempt → WiFi Setup screen with "LoveBox-Setup" and "192.168.4.1" |
| 1.3 | Power-cycle mid-slideshow | Clean boot, no errors, slideshow resumes within 10s |
| 1.4 | Power-cycle while in READING state | Clean boot, no leftover state — returns to IDLE/slideshow |
| 1.5 | Boot with SD card removed | **Known limitation:** `wifi_learned.json` is on the SD card; `secrets.WIFI_NETWORKS` is empty by design. No learned networks → WiFi connect fails → AP portal → timeout → "No WiFi" banner. Device is stuck until SD is reinserted or a network is hardcoded in `secrets.py`. No crash; this is an accepted consequence of storing all credentials on SD. |

---

## 2. WiFi — Normal Operation

| # | Test | Expected |
|---|------|----------|
| 2.1 | Boot with home WiFi → confirm `/status` shows correct SSID and IP | Status reply received within 35s |
| 2.2 | Boot log confirms gateway non-zero before first poll | `poll: ip=X gw=Y dns=Z` printed, no EHOSTUNREACH |
| 2.3 | Disconnect router mid-operation (unplug or disable SSID) | Within ~35s, "No WiFi \| tap to restart" banner appears on slideshow |
| 2.4 | Reconnect router while banner is showing | Banner disappears on next poll cycle; slideshow continues cleanly |
| 2.5 | Tap the "No WiFi" banner | Device restarts; reconnects and continues |
| 2.6 | Mobile hotspot: enable hotspot THEN enable mobile data | Confirm boot connects and `/status` shows correct IP (not EHOSTUNREACH) |

---

## 3. WiFi AP Portal

| # | Test | Expected |
|---|------|----------|
| 3.1 | Remove all known networks from `secrets.py`, boot device | WiFi Setup screen appears within ~35s |
| 3.2 | Connect phone to "LoveBox-Setup" (open, no password) | Phone joins network |
| 3.3 | Check for "Sign in to network" notification on Android | Notification appears (may not appear if Private DNS is active — see 3.4) |
| 3.4 | Manually navigate to `http://192.168.4.1` in browser | Form loads with SSID + password fields |
| 3.5 | Submit valid credentials | "Saved! LoveBox is restarting…" shown in browser; device reboots |
| 3.6 | After reboot, confirm device connects to submitted network | Boot screen shows correct SSID |
| 3.7 | Check SD card: `wifi_override.json` gone, `wifi_learned.json` exists | Credentials promoted; override cleaned up |
| 3.8 | Power-cycle and confirm device connects automatically (no portal) | Learned network used; portal not triggered |
| 3.9 | Submit blank SSID on portal form | Form stays open; no reboot |
| 3.10 | Let portal time out (5 min, no submission) | Device continues to slideshow without WiFi; "No WiFi" banner visible |

---

## 4. Telegram — Message Delivery

| # | Test | Expected |
|---|------|----------|
| 4.1 | Send a short text message | ARRIVED screen + LED pulse within 35s; tap → text displayed in ROSE box |
| 4.2 | Send text exactly 100 chars | Displayed in full, no truncation |
| 4.3 | Send text >100 chars | Truncated to 100 chars with "…" |
| 4.4 | Send an inline photo | ARRIVED; tap → photo displayed full-area |
| 4.5 | Send photo with `#slide` caption | Photo displayed; saved to `/sd/photos/`; appears in slideshow rotation |
| 4.6 | Send a `.jpg` file via paperclip → File | Same as inline photo |
| 4.7 | Send a GIF from the GIF picker | ARRIVED; tap → thumbnail displayed with "GIF" badge |
| 4.8 | Send a message from a different Telegram account | Silently ignored; no arrival screen |
| 4.9 | Send 3 messages in quick succession | First ARRIVED shows "+ 2 more waiting" badge; subsequent arrivals decrement correctly |
| 4.10 | Send message while device is in READING state | Queued; ARRIVED screen shown after current reading dismisses |

---

## 5. Telegram — Commands

| # | Test | Expected |
|---|------|----------|
| 5.1 | Send `/help` | Reply lists all commands and mood colours |
| 5.2 | Send `/status` | Reply with SSID, IP, signal dBm, uptime h/m, photo count, queue depth |
| 5.3 | `/status` queue depth: send 2 messages, do not tap, then `/status` | Queue shows 2 |
| 5.4 | `/mood rose` | Reply "Mood set to rose"; LEDs shift to rose within 1 poll cycle |
| 5.5 | `/mood calm` / `happy` / `red` / `orange` / `yellow` / `green` / `mint` / `teal` / `blue` / `purple` / `lavender` | Each changes LED colour; reply confirms |
| 5.6 | `/mood off` | Reply confirms; LEDs revert to warm amber |
| 5.7 | Set a mood, power-cycle | Mood persists after reboot (`/sd/mood.json` loaded on boot) |
| 5.8 | `/mood banana` (unknown colour) | Reply "Unknown mood. Try: rose, calm, happy…" |
| 5.9 | `/mood` with no argument | Unknown mood reply; no crash |
| 5.10 | Send a `/` command that isn't handled (e.g. `/foo`) | Silently ignored; no crash |

---

## 6. Reply & Read Receipt Flow

| # | Test | Expected |
|---|------|----------|
| 6.1 | Tap ARRIVED screen | Shah receives "Seen ✓" before reveal transition begins |
| 6.2 | Tap "Love it" reply button | Shah receives "Love it" message; device returns to IDLE |
| 6.3 | Tap "Haha" | Shah receives "Haha" |
| 6.4 | Tap "Call me!" | Shah receives "Call me!" |
| 6.5 | Wait 2 minutes without tapping any reply button | Reading times out; device returns to IDLE automatically |
| 6.6 | Send reply while WiFi is down | Toast "Couldn't send — try again" shown for 2.5s; device returns to IDLE |

---

## 7. Slideshow

| # | Test | Expected |
|---|------|----------|
| 7.1 | Swipe left during slideshow | Advances to next photo |
| 7.2 | Swipe right | Goes to previous photo |
| 7.3 | Small tap (not a swipe) on slideshow area (not WiFi banner) | No navigation; interval continues |
| 7.4 | Message arrives during slideshow | Slideshow pauses; ARRIVED shown; after dismiss, same photo resumes with 5s cooldown |
| 7.5 | Place a corrupt/progressive JPEG in `/sd/photos/` | Skipped silently; rest of slideshow continues; file stays on SD |
| 7.6 | Slideshow with 0 photos (empty `/sd/photos/`) | No crash; dark screen in IDLE; messages still received |

---

## 8. Resilience & Concurrency

| # | Test | Expected |
|---|------|----------|
| 8.1 | Send 5 messages as fast as Telegram allows | All queued; delivered sequentially; no messages dropped (if device is online) |
| 8.2 | WiFi drops exactly during a photo download | `download_file` fails cleanly; partial cache file removed; no crash; polling resumes |
| 8.3 | WiFi drops during `polling_loop` getUpdates call | GET error logged; `gc.collect()` runs; poll retries after 30s |
| 8.4 | WiFi drops and comes back before next poll | Reconnects silently; no banner |
| 8.5 | Run continuously for 8+ hours | No memory leak; stable polling; slideshow cycling; no crash |
| 8.6 | Send `/status` command while device is in READING state | Command processed on next poll after reading state; reply arrives slightly delayed |
| 8.7 | Send `/mood` while a message is being displayed | Mood applied on next poll; no display disruption |
| 8.8 | Tap WiFi banner while slideshow is between photos (rendering) | Restart triggered correctly; no lockup |

---

## 9. Known Issue: Offline Message Loss

This is documented behaviour, not a bug to fix — but should be verified and understood.

| # | Scenario | Actual behaviour |
|---|----------|-----------------|
| 9.1 | Device offline for 1+ hour; Shah sends messages during outage; device comes back online | Messages sent during outage are **not delivered** to the screen. Device drains pending Telegram updates on boot startup without processing them (intentional — avoids flooding Beth with stale messages). |
| 9.2 | Shah sends messages while device is online but between 30s polls | Messages **are delivered** — Telegram buffers them and the next `getUpdates` call picks them up. The 30s gap is a delay, not a loss. |
| 9.3 | Device reboots while messages are in the in-memory queue (not yet displayed) | Queued messages **are lost** — the queue is in RAM, not persisted. |

**Workflow recommendation:** After any extended outage, Shah should send `/status` first to confirm the device is live, then resend any important messages.

---

## 10. LED Visual Checks (physical)

| # | Test | Expected |
|---|------|----------|
| 10.1 | Boot with no saved mood | Warm amber glow at 25% brightness |
| 10.2 | `/mood rose` | All 7 LEDs shift to pink within 35s |
| 10.3 | Message arrives with mood set | Pulse breathes in mood colour (not default rose) |
| 10.4 | Message dismissed | LEDs return to mood colour ambient glow |
| 10.5 | `/mood off` | LEDs return to warm amber |
| 10.6 | All 10 mood colours | Each visually distinct; no obviously wrong colours |
