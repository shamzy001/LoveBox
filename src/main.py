import asyncio
import time
import os

import hardware  # creates Presto singleton — must be first
import wifi
import state
import led_manager
import telegram
import slideshow
import display_manager
import touch_handler
import secrets


# -- SD card mount -----------------------------------------------------------

def mount_sd():
    try:
        os.listdir("/sd")
        print("SD already mounted")
        _ensure_dirs()
        return True
    except OSError:
        pass

    try:
        import sdcard
        import uos
        import machine
        sd_spi = machine.SPI(0,
            sck=machine.Pin(34, machine.Pin.OUT),
            mosi=machine.Pin(35, machine.Pin.OUT),
            miso=machine.Pin(36, machine.Pin.OUT))
        sd = sdcard.SDCard(sd_spi, machine.Pin(39))
        uos.mount(sd, "/sd")
        _ensure_dirs()
        print("SD mounted OK")
        return True
    except Exception as e:
        print("SD mount failed:", e)
        return False


def _ensure_dirs():
    for path in ("/sd/photos", "/sd/cache"):
        try:
            os.mkdir(path)
        except OSError:
            pass


# -- Main app loop -----------------------------------------------------------

async def app_loop():
    while True:
        display_manager.set_wifi_indicator(wifi.is_connected)
        state.wifi_lost = not wifi.is_connected

        if state.current == state.IDLE:
            msg = state.queue_pop()
            if msg:
                state.current_message = msg
                state.current = state.ARRIVED

        if state.current == state.ARRIVED:
            await handle_arrived()
        elif state.current == state.REVEALING:
            await handle_revealing()
        elif state.current == state.READING:
            await handle_reading()

        await asyncio.sleep_ms(50)


# -- State handlers ----------------------------------------------------------

async def handle_arrived():
    display_manager.show_arrived_screen(queue_depth=state.queue_len())
    led_manager.start_pulse()
    await touch_handler.wait_for_tap()
    telegram.send_message(secrets.SENDER_CHAT_ID, "Seen ✓")
    state.current = state.REVEALING


async def handle_revealing():
    await display_manager.show_reveal_transition()
    state.current = state.READING
    display_manager.render_reading_screen(state.current_message)


async def handle_reading():
    TIMEOUT_MS = 2 * 60 * 1000
    deadline = time.ticks_add(time.ticks_ms(), TIMEOUT_MS)

    while True:
        if time.ticks_diff(deadline, time.ticks_ms()) <= 0:
            break

        pos = touch_handler.poll_touch()
        if pos is not None:
            x, y = pos
            # Wait for release before acting
            while touch_handler.poll_touch() is not None:
                await asyncio.sleep_ms(20)
            idx = touch_handler.hit_test(x, y, display_manager.REPLY_RECTS)
            if idx >= 0:
                label = display_manager.REPLY_LABELS[idx]
                ok = telegram.send_message(secrets.SENDER_CHAT_ID, label)
                if not ok:
                    display_manager.show_toast("Couldn't send — try again")
                    await asyncio.sleep_ms(2500)
            break

        await asyncio.sleep_ms(50)

    if state.current_message:
        msg_type = state.current_message.get("type")
        path = state.current_message.get("path", "")
        if msg_type == "photo" and state.current_message.get("slideshow") and path:
            slideshow.save_received_photo(path)
        # Clean up any cached file (photo or gif)
        if path:
            try:
                os.remove(path)
            except OSError:
                pass

    led_manager.stop_pulse()
    display_manager.show_idle()
    state.current = state.IDLE


# -- Entry point -------------------------------------------------------------

display_manager.init()
led_manager.init()
touch_handler.init()

sd_ok = mount_sd()

display_manager.show_boot_status("Connecting to WiFi...")
connected = wifi.connect()
if not connected:
    # One retry — the radio sometimes needs a moment to settle after a reset
    display_manager.show_boot_status("Retrying WiFi...")
    time.sleep(3)
    connected = wifi.connect()
if connected:
    import network as _net
    _wlan = _net.WLAN(_net.STA_IF)
    ip = _wlan.ifconfig()[0]
    try:
        ssid = _wlan.config('ssid')
    except Exception:
        ssid = "WiFi"
    display_manager.show_boot_status(ssid, ip, ok=True)
    time.sleep(2)
else:
    import ap_portal
    ap_portal.run_portal(
        show_status_cb=display_manager.show_ap_portal_screen,
        timeout_ms=300_000,  # 5 minutes, then continue without WiFi
    )
    # run_portal reboots on success; reaching here means it timed out
    display_manager.show_boot_status("No WiFi", "continuing...", ok=False)
    time.sleep(2)

if sd_ok:
    led_manager.load_mood()
led_manager.set_idle()

loop = asyncio.get_event_loop()
loop.create_task(app_loop())
loop.create_task(telegram.polling_loop())
loop.create_task(led_manager.led_loop())
if sd_ok:
    loop.create_task(slideshow.slideshow_task())

loop.run_forever()
