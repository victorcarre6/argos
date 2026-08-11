from __future__ import annotations

import threading
from typing import Any


def empty_job_state() -> dict[str, Any]:
    return {
        "running": False,
        "started_at": None,
        "finished_at": None,
        "result": None,
        "error": None,
    }


collection_state = empty_job_state()
cluster_state = empty_job_state()
state_lock = threading.Lock()
