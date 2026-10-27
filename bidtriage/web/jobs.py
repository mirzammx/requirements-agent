"""Background jobs for the web app: one at a time per bid/shortlist folder, status kept in status.json."""

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Callable

STATUS_FILE = "status.json"
_lock = threading.Lock()


def read_status(folder: Path) -> dict:
    try:
        return json.loads((folder / STATUS_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"state": "idle"}


def write_status(folder: Path, status: dict) -> None:
    (folder / STATUS_FILE).write_text(json.dumps(status, indent=2), encoding="utf-8")


def start(folder: Path, step: str, work: Callable[[], object], *, sync: bool = False) -> bool:
    """Run `work` for this folder unless a job is already running there. Returns False if one was."""
    with _lock:
        if read_status(folder).get("state") == "running":
            return False
        write_status(folder, {"state": "running", "step": step, "started": f"{datetime.now():%Y-%m-%d %H:%M}"})

    def run():
        try:
            work()
            status = {"state": "done", "step": step}
        except Exception as exc:  # shown to the user on the page
            status = {"state": "failed", "step": step, "error": str(exc) or type(exc).__name__}
        status["finished"] = f"{datetime.now():%Y-%m-%d %H:%M}"
        write_status(folder, status)

    if sync:
        run()
    else:
        threading.Thread(target=run, daemon=True).start()
    return True


def recover(folders: list[Path]) -> None:
    """After a restart, a job marked running can never finish: mark it failed so it can be re-run."""
    for folder in folders:
        status = read_status(folder)
        if status.get("state") == "running":
            write_status(folder, {**status, "state": "failed",
                                  "error": "Interrupted (the app was restarted). Run it again."})
