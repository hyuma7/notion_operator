"""
設定管理モジュール
"""

import os
import sys
import tempfile
from pathlib import Path


APP_NAME = "Notion Operator"
CONFIG_FILENAME = "printer_proxy_config.json"
LOG_FILENAME = "printer_proxy.log"


def _is_frozen_app() -> bool:
    return bool(getattr(sys, "frozen", False))


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _user_data_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming"
        return Path(base) / APP_NAME
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "notion-operator"


def _resolve_writable_path(filename: str, env_var: str) -> str:
    override = os.environ.get(env_var)
    if override:
        path = Path(override).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        return str(path)

    primary_dir = _user_data_dir() if _is_frozen_app() else _project_root()
    fallback_dirs = [
        primary_dir,
        Path.home() / ".notion-operator",
        Path(tempfile.gettempdir()) / "notion-operator",
    ]

    for directory in fallback_dirs:
        try:
            directory.mkdir(parents=True, exist_ok=True)
            return str(directory / filename)
        except OSError:
            continue

    return filename


def _legacy_config_candidates(config_file: str) -> tuple[str, ...]:
    candidates: list[Path] = []

    if _is_frozen_app():
        try:
            executable = Path(sys.executable).resolve()
            candidates.extend(parent / CONFIG_FILENAME for parent in executable.parents)
        except OSError:
            pass

    candidates.extend(
        [
            Path.cwd() / CONFIG_FILENAME,
            Path.home() / CONFIG_FILENAME,
            _project_root() / CONFIG_FILENAME,
        ]
    )

    current = Path(config_file).resolve()
    seen: set[Path] = set()
    result: list[str] = []
    for candidate in candidates:
        try:
            resolved = candidate.expanduser().resolve()
        except OSError:
            continue
        if resolved == current or resolved in seen:
            continue
        seen.add(resolved)
        result.append(str(resolved))
    return tuple(result)


# 設定ファイル
CONFIG_FILE = _resolve_writable_path(CONFIG_FILENAME, "NOTION_OPERATOR_CONFIG_FILE")
LOG_FILE = _resolve_writable_path(LOG_FILENAME, "NOTION_OPERATOR_LOG_FILE")
LEGACY_CONFIG_FILES = _legacy_config_candidates(CONFIG_FILE)

# デフォルト設定
DEFAULT_CONFIG = {
    "printer_ip": "192.168.1.100",
    "printer_port": 9100,
    "label_size": "62",
    "font_size": 16,
    "qr_size_scale": 3,
    "notion_api_key": "",
    "notion_database_id": "1d254e6206d881bb9e88d2e7ffb90444",
    "issuer_company_name": "株式会社 アーネスト",
    "issuer_representative": "代表取締役　齊藤 淳",
    "issuer_address": "〒225-0025 神奈川県横浜市青葉区鉄町25-8",
    "issuer_tel": "TEL：045-507-6784　FAX：045-507-6804",
    "issuer_invoice_number": "",
    "issuer_stamp_lines": ["株式会社", "アーネスト", "代表取締役", "齊藤 淳"],
    "issuer_stamp_image_path": "",
}
