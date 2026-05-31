import asyncio
import os
import utime
import time

import state
import display_manager
import touch_handler

_INTERVAL_S = 30
_COOLDOWN_S = 5  # pause after a message is dismissed before resuming slideshow
_photos = []
_index = 0


def photo_count():
    return len(_photos)


def load_photo_list():
    global _photos, _index
    try:
        files = sorted(
            f for f in os.listdir("/sd/photos")
            if f.lower().endswith(".jpg") or f.lower().endswith(".jpeg")
        )
        _photos = ["/sd/photos/" + f for f in files]
        _index = 0
        print("Slideshow: {} photos loaded".format(len(_photos)))
    except Exception as e:
        print("Slideshow: could not load photo list:", e)
        _photos = []


def _copy_file(src, dst, chunk=4096):
    with open(src, "rb") as f_in:
        with open(dst, "wb") as f_out:
            while True:
                buf = f_in.read(chunk)
                if not buf:
                    break
                f_out.write(buf)


def save_received_photo(src_path):
    """Copy a received photo into /sd/photos/ and add it to the live rotation."""
    dest = "/sd/photos/recv_{}.jpg".format(utime.ticks_ms())
    try:
        _copy_file(src_path, dest)
        if dest not in _photos:
            _photos.append(dest)
        print("Slideshow: saved", dest)
    except Exception as e:
        print("Slideshow: save error:", e)


async def slideshow_task():
    global _index
    load_photo_list()

    just_became_idle = False
    while True:
        if state.current != state.IDLE:
            just_became_idle = True
            await asyncio.sleep(1)
            continue

        if not _photos:
            await asyncio.sleep(_INTERVAL_S)
            continue

        # After returning from a message, pause a full interval before resuming
        # so the screen doesn't immediately flash back to the just-dismissed photo.
        if just_became_idle:
            just_became_idle = False
            deadline = time.ticks_add(time.ticks_ms(), _COOLDOWN_S * 1000)
            while time.ticks_diff(deadline, time.ticks_ms()) > 0:
                if state.current != state.IDLE:
                    break
                await asyncio.sleep_ms(200)
            continue

        path = _photos[_index % len(_photos)]
        ok = display_manager.display_jpeg(path)
        if not ok:
            # Progressive or corrupt JPEG — drop from rotation so we don't
            # keep hitting it. File stays on disk.
            print("Slideshow: removing bad photo from rotation:", path)
            _photos.remove(path)
            # Don't advance _index or wait — immediately try the next photo
            continue

        # Wait for the interval, polling touch for left/right swipe gestures.
        # direction =  1 → advance to next photo (default / swipe left)
        # direction = -1 → go back to previous photo (swipe right)
        # direction =  0 → interrupted by incoming message; keep same photo
        direction = 1
        touch_start_x = None
        touch_start_y = None
        touch_last_x = None
        deadline = time.ticks_add(time.ticks_ms(), _INTERVAL_S * 1000)
        while time.ticks_diff(deadline, time.ticks_ms()) > 0:
            if state.current != state.IDLE:
                direction = 0   # don't advance — resume on same photo after cooldown
                break
            pos = touch_handler.poll_touch()
            if pos is not None:
                x, y = pos
                if touch_start_x is None:
                    touch_start_x = x
                    touch_start_y = y
                touch_last_x = x
            elif touch_start_x is not None:
                # Finger just lifted — measure swipe distance
                dx = touch_last_x - touch_start_x
                if dx < -80:    # swipe left → next photo
                    direction = 1
                    break
                elif dx > 80:   # swipe right → previous photo
                    direction = -1
                    break
                else:
                    # Small tap — check if it landed on the WiFi restart banner
                    if (state.wifi_lost
                            and touch_start_y is not None
                            and touch_start_y <= display_manager.WIFI_BANNER_H):
                        import machine
                        machine.reset()
                # Tap or jitter — ignore and keep waiting
                touch_start_x = None
                touch_start_y = None
                touch_last_x = None
            await asyncio.sleep_ms(50)

        _index += direction
