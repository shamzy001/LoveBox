IDLE = "idle"
ARRIVED = "arrived"
REVEALING = "revealing"
READING = "reading"

current = IDLE
current_message = None
wifi_lost = False

_queue = []


def queue_push(msg):
    _queue.append(msg)


def queue_pop():
    return _queue.pop(0) if _queue else None


def queue_len():
    return len(_queue)
