"""リリースアセットのダウンロードと sha256 検証"""

import hashlib
from pathlib import Path
from typing import Callable, Optional

import requests

CHUNK_SIZE = 256 * 1024


def download(url: str, dest: Path, progress: Optional[Callable[[float], None]] = None) -> None:
    """URL を dest にダウンロードする。progress には 0.0-1.0 を渡す"""
    with requests.get(url, stream=True, timeout=30) as response:
        response.raise_for_status()
        total = int(response.headers.get("Content-Length") or 0)
        done = 0
        with open(dest, "wb") as f:
            for chunk in response.iter_content(CHUNK_SIZE):
                f.write(chunk)
                done += len(chunk)
                if progress and total:
                    progress(done / total)


def verify_sha256(path: Path, checksum_url: str) -> None:
    """checksum_url の内容（"<hash>" または "<hash>  <filename>"）と照合。不一致なら例外"""
    response = requests.get(checksum_url, timeout=30)
    response.raise_for_status()
    expected = response.text.strip().split()[0].lower()

    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    actual = digest.hexdigest()

    if actual != expected:
        raise RuntimeError(
            f"チェックサムが一致しません（期待値: {expected}, 実際: {actual}）"
        )
