import asyncio
import math
import ujson
import os

NUM_LEDS = 7
_IDLE_R,  _IDLE_G,  _IDLE_B  = 255, 220, 160   # warm amber — default idle glow
_IDLE_BRIGHTNESS              = 0.25
_PULSE_R, _PULSE_G, _PULSE_B = 255, 100, 130   # rose — default notification pulse

_pulsing  = False
_presto   = None
_mood_r   = None   # None = no mood set, use defaults above
_mood_g   = None
_mood_b   = None

_MOOD_FILE = "/sd/mood.json"


def init():
    global _presto
    from hardware import presto
    _presto = presto


def load_mood():
    """Read saved mood from SD and apply it. Call after SD is mounted."""
    global _mood_r, _mood_g, _mood_b
    try:
        with open(_MOOD_FILE) as f:
            data = ujson.load(f)
        _mood_r = int(data["r"])
        _mood_g = int(data["g"])
        _mood_b = int(data["b"])
        print("LED: mood loaded ({}, {}, {})".format(_mood_r, _mood_g, _mood_b))
    except Exception:
        _mood_r = _mood_g = _mood_b = None


def set_mood(r, g, b):
    """Set mood colour and persist to SD."""
    global _mood_r, _mood_g, _mood_b
    _mood_r, _mood_g, _mood_b = r, g, b
    try:
        with open(_MOOD_FILE, "w") as f:
            ujson.dump({"r": r, "g": g, "b": b}, f)
    except Exception as e:
        print("LED: could not save mood:", e)


def clear_mood():
    """Clear mood and remove saved file — reverts to default warm amber."""
    global _mood_r, _mood_g, _mood_b
    _mood_r = _mood_g = _mood_b = None
    try:
        os.remove(_MOOD_FILE)
    except Exception:
        pass


def _set_all(r, g, b, brightness=1.0):
    if _presto is None:
        return
    r = max(0, min(255, int(r * brightness)))
    g = max(0, min(255, int(g * brightness)))
    b = max(0, min(255, int(b * brightness)))
    for i in range(NUM_LEDS):
        _presto.set_led_rgb(i, r, g, b)


def set_idle():
    """Apply idle glow — mood colour if set, otherwise default warm amber."""
    if _mood_r is not None:
        _set_all(_mood_r, _mood_g, _mood_b, _IDLE_BRIGHTNESS)
    else:
        _set_all(_IDLE_R, _IDLE_G, _IDLE_B, _IDLE_BRIGHTNESS)


def set_solid(r, g, b):
    _set_all(r, g, b)


def start_pulse():
    global _pulsing
    _pulsing = True


def stop_pulse():
    global _pulsing
    _pulsing = False
    set_idle()


async def led_loop():
    """Continuous LED task — scheduled via create_task in main."""
    step_ms = 20
    steps   = 250   # 20 ms × 250 = 5-second breath cycle
    i = 0
    while True:
        if _pulsing:
            t = math.sin(math.pi * i / steps) ** 2
            brightness = 0.05 + 0.95 * t
            # Pulse in mood colour if set, otherwise default rose
            pr = _mood_r if _mood_r is not None else _PULSE_R
            pg = _mood_g if _mood_g is not None else _PULSE_G
            pb = _mood_b if _mood_b is not None else _PULSE_B
            _set_all(pr, pg, pb, brightness)
            i = (i + 1) % steps
        else:
            set_idle()
        await asyncio.sleep_ms(step_ms)
