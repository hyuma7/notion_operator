"""ダウンロード済みzipからの置き換えインストール（プラットフォーム振り分け）"""

import sys
from pathlib import Path
from typing import Optional


def is_frozen() -> bool:
    """PyInstaller でビルドされたバイナリとして動いているか"""
    return bool(getattr(sys, "frozen", False))


def get_install_target() -> Optional[Path]:
    """置き換え対象（mac: .app バンドル / Windows: .exe）のパスを返す

    ソース実行時（非frozen）は None。
    """
    if not is_frozen():
        return None
    exe = Path(sys.executable)
    if sys.platform == "darwin":
        for parent in exe.parents:
            if parent.suffix == ".app":
                return parent
        return None
    if sys.platform == "win32":
        return exe
    return None


def install_and_restart(zip_path: Path) -> None:
    """zipを展開し、ヘルパースクリプト経由で自身を置き換えて再起動する

    この関数はヘルパーを起動して即座に戻る。呼び出し側はその後
    速やかにアプリを終了すること（ヘルパーは本プロセスの終了を待つ）。
    """
    target = get_install_target()
    if target is None:
        raise RuntimeError("ビルド済みアプリとして起動していないため自動更新できません")

    if sys.platform == "darwin":
        from updater import _install_mac

        _install_mac.install_and_restart(zip_path, target)
    elif sys.platform == "win32":
        from updater import _install_win

        _install_win.install_and_restart(zip_path, target)
    else:
        raise RuntimeError(f"未対応のプラットフォームです: {sys.platform}")
