"""GitHub Releases の最新バージョン照会とバージョン比較"""

import re
import sys
from dataclasses import dataclass
from typing import Optional

import requests

GITHUB_REPO = "hyuma7/notion_operator"
API_LATEST_RELEASE = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

# リリースアセット名に含まれるプラットフォーム識別子
PLATFORM_KEYS = {
    "darwin": "macos-arm64",
    "win32": "windows-x64",
}


@dataclass
class ReleaseInfo:
    tag: str
    version: tuple
    asset_name: str
    asset_url: str
    checksum_url: Optional[str]
    release_url: str


def parse_version(text: str) -> Optional[tuple]:
    """"v0.4.0" や "0.4.0" を (0, 4, 0) に変換する。解釈できなければ None"""
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", text or "")
    if not m:
        return None
    return tuple(int(part) for part in m.groups())


def platform_key() -> Optional[str]:
    return PLATFORM_KEYS.get(sys.platform)


def select_asset(assets: list, key: str) -> Optional[dict]:
    """アセット一覧から自プラットフォーム用のzipを選ぶ"""
    for asset in assets:
        name = asset.get("name", "")
        if key in name and name.endswith(".zip"):
            return asset
    return None


def find_checksum_url(assets: list, asset_name: str) -> Optional[str]:
    for asset in assets:
        if asset.get("name") == f"{asset_name}.sha256":
            return asset.get("browser_download_url")
    return None


def fetch_latest_release(timeout: float = 10) -> Optional[dict]:
    """最新リリースを取得する。リリースが1つもない場合（404）は None"""
    response = requests.get(
        API_LATEST_RELEASE,
        headers={"Accept": "application/vnd.github+json"},
        timeout=timeout,
    )
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


def check_for_update(current_version: str, timeout: float = 10) -> Optional[ReleaseInfo]:
    """新しいバージョンがあれば ReleaseInfo を返す。なければ None

    ネットワークエラー等は例外がそのまま上がる（呼び出し側で握る）。
    """
    current = parse_version(current_version)
    if current is None:
        return None

    data = fetch_latest_release(timeout=timeout)
    if data is None:
        return None
    latest = parse_version(data.get("tag_name", ""))
    if latest is None or latest <= current:
        return None

    key = platform_key()
    if key is None:
        return None
    asset = select_asset(data.get("assets", []), key)
    if asset is None:
        return None

    return ReleaseInfo(
        tag=data.get("tag_name", ""),
        version=latest,
        asset_name=asset["name"],
        asset_url=asset["browser_download_url"],
        checksum_url=find_checksum_url(data.get("assets", []), asset["name"]),
        release_url=data.get("html_url", ""),
    )
