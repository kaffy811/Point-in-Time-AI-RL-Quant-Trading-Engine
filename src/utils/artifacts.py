"""Provider-independent hashes and durable exclusive audit publication."""
import hashlib
import json
import os
from pathlib import Path
from typing import Any


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + '\n').encode()


def sync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def sync_file(path: Path) -> None:
    with path.open('rb') as handle:
        os.fsync(handle.fileno())


def write_once(path: Path, content: bytes) -> None:
    """Preserve any failed partial write; never replace or silently truncate."""
    with path.open('xb') as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    path.chmod(0o400)
    sync_directory(path.parent)
