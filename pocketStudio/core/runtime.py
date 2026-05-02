from __future__ import annotations

import time


STARTED_AT = time.time()


def uptime_seconds() -> int:
    return int(time.time() - STARTED_AT)
