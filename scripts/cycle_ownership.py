"""Shared OS-held ticket ownership; no validator/runner import cycle."""

import contextlib
import os
from collections.abc import Iterator
from pathlib import Path


class CycleOwnershipError(RuntimeError):
    pass


@contextlib.contextmanager
def ticket_ownership(directory: Path) -> Iterator[None]:
    """OS ownership survives neither process death nor a second concurrent owner."""
    directory.parent.mkdir(parents=True, exist_ok=True)
    path = directory.parent / f"{directory.name}.runner.lock"
    if path.is_symlink() or path.is_junction():
        raise CycleOwnershipError("runner lock must not be a symbolic link")
    with path.open("a+b") as stream:
        stream.seek(0)
        if os.name == "nt":
            import msvcrt

            def lock() -> None:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)

            def unlock() -> None:
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            def lock() -> None:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

            def unlock() -> None:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

        try:
            lock()
        except OSError as error:
            raise CycleOwnershipError("another runner owns this ticket") from error
        try:
            yield
        finally:
            stream.seek(0)
            unlock()
