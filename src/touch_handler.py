import asyncio

# Touch is FT6236, accessed via presto.touch
# API: touch.poll() updates state; touch.state is truthy when touching
# Coordinates: touch.x, touch.y (verify names match — run print(dir(touch)) if unsure)

_touch = None


def init():
    global _touch
    from hardware import touch
    _touch = touch


def poll_touch():
    """Return (x, y) if a touch is active, else None."""
    if _touch is None:
        return None
    try:
        _touch.poll()
        if _touch.state:
            return _touch.x, _touch.y
    except Exception as e:
        print("touch error:", e)
    return None


def hit_test(x, y, rects, tolerance=8):
    """
    rects: list of (rx, ry, rw, rh)
    Returns index of first matching rect, or -1.
    """
    for i, (rx, ry, rw, rh) in enumerate(rects):
        if (rx - tolerance <= x <= rx + rw + tolerance and
                ry - tolerance <= y <= ry + rh + tolerance):
            return i
    return -1


async def wait_for_tap():
    """Yield until the screen is tapped. Returns (x, y)."""
    while True:
        pos = poll_touch()
        if pos is not None:
            # Wait for release before returning so we don't double-trigger
            while poll_touch() is not None:
                await asyncio.sleep_ms(20)
            return pos
        await asyncio.sleep_ms(50)
