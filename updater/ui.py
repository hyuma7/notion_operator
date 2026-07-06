"""アップデートのUI（設定タブのカードと起動時チェック）"""

import tempfile
import threading
import traceback
from pathlib import Path
from typing import Optional

import flet as ft

from updater import checker, downloader, installer
from updater.checker import ReleaseInfo
from version import __version__


class UpdateSection:
    """設定タブに置くアップデートカード"""

    def __init__(self, page: ft.Page):
        self.page = page
        self.release: Optional[ReleaseInfo] = None

        self.current_text = ft.Text(
            f"現在のバージョン: v{__version__}", size=13
        )
        self.status_text = ft.Text("", size=12, color=ft.Colors.GREY_600)
        self.progress = ft.ProgressBar(width=300, visible=False)
        self.check_btn = ft.OutlinedButton(
            "アップデートを確認",
            icon=ft.Icons.REFRESH,
            on_click=self.on_check,
        )
        self.install_btn = ft.ElevatedButton(
            "ダウンロードして更新",
            icon=ft.Icons.SYSTEM_UPDATE_ALT,
            visible=False,
            on_click=self.on_install,
        )

    def create_card(self) -> ft.Card:
        return ft.Card(
            content=ft.Container(
                padding=ft.padding.all(20),
                content=ft.Column([
                    ft.Text("アップデート", size=18, weight=ft.FontWeight.BOLD),
                    ft.Divider(),
                    self.current_text,
                    self.status_text,
                    self.progress,
                    ft.Row([self.check_btn, self.install_btn]),
                ]),
            )
        )

    # --- チェック ---

    def on_check(self, e):
        self.check_btn.disabled = True
        self.status_text.value = "確認中..."
        self.page.update()
        threading.Thread(target=self._check_worker, daemon=True).start()

    def _check_worker(self):
        try:
            release = checker.check_for_update(__version__)
        except Exception as ex:
            self.status_text.value = f"確認に失敗しました: {ex}"
            self.check_btn.disabled = False
            self.page.update()
            return

        self.check_btn.disabled = False
        self.set_release(release, notify_latest=True)

    def set_release(self, release: Optional[ReleaseInfo], notify_latest: bool = False):
        """チェック結果をUIに反映する（起動時チェックからも呼ばれる）"""
        self.release = release
        if release is None:
            if notify_latest:
                self.status_text.value = "最新バージョンです"
        elif not installer.is_frozen():
            self.status_text.value = (
                f"新しいバージョン {release.tag} があります"
                "（ソース実行のため自動更新は無効。git pull してください）"
            )
        else:
            self.status_text.value = f"新しいバージョン {release.tag} があります"
            self.install_btn.visible = True
        self.page.update()

    # --- インストール ---

    def on_install(self, e):
        if self.release is None:
            return
        self.check_btn.disabled = True
        self.install_btn.disabled = True
        self.progress.visible = True
        self.progress.value = 0
        self.status_text.value = f"{self.release.tag} をダウンロード中..."
        self.page.update()
        threading.Thread(target=self._install_worker, daemon=True).start()

    def _install_worker(self):
        release = self.release
        try:
            workdir = Path(tempfile.mkdtemp(prefix="notion_operator_dl_"))
            zip_path = workdir / release.asset_name
            downloader.download(release.asset_url, zip_path, progress=self._on_progress)

            if release.checksum_url:
                self.status_text.value = "チェックサムを検証中..."
                self.page.update()
                downloader.verify_sha256(zip_path, release.checksum_url)

            self.status_text.value = "更新を適用しています。アプリを再起動します..."
            self.page.update()
            installer.install_and_restart(zip_path)
        except Exception as ex:
            print(f"[ERROR] アップデートに失敗しました:\n{traceback.format_exc()}")
            self.status_text.value = f"更新に失敗しました: {ex}"
            self.progress.visible = False
            self.check_btn.disabled = False
            self.install_btn.disabled = False
            self.page.update()
            return

        # ヘルパースクリプトが本プロセスの終了を待っているので、ここで終了する
        self.page.window.destroy()

    def _on_progress(self, ratio: float):
        self.progress.value = ratio
        self.page.update()


_section_singleton: Optional[UpdateSection] = None


def get_update_section(page: ft.Page) -> UpdateSection:
    """設定タブと起動時チェックで同じインスタンスを共有する"""
    global _section_singleton
    if _section_singleton is None:
        _section_singleton = UpdateSection(page)
    return _section_singleton


def check_on_startup(page: ft.Page, section: Optional[UpdateSection] = None) -> None:
    """起動時にバックグラウンドで更新確認し、あればスナックバーで知らせる

    オフライン等の失敗は黙ってスキップする。
    """

    def worker():
        try:
            release = checker.check_for_update(__version__)
        except Exception:
            return
        if release is None:
            return
        if section is not None:
            section.set_release(release)
        snack = ft.SnackBar(
            content=ft.Text(
                f"新しいバージョン {release.tag} があります（設定タブから更新できます）"
            ),
            bgcolor=ft.Colors.BLUE_700,
            duration=8000,
        )
        page.snack_bar = snack
        page.snack_bar.open = True
        page.update()

    threading.Thread(target=worker, daemon=True).start()
