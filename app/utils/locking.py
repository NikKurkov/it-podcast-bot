import fcntl
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def exclusive_lock(path: Path, message: str):
    """Hold a nonblocking process lock; closing the file releases it on failure."""
    with path.open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError(message) from exc
        yield
