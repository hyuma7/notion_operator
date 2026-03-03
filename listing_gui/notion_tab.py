"""
Notionデータ取得・表示・コピータブ
- DB一覧（更新順10件）→ 商品名クリックで詳細表示
- 画像URL表示 + まとめてダウンロード → DL完了後フォルダを即座に開く
"""

import os
import re
import subprocess
import threading
import flet as ft
import requests

from pathlib import Path

from notion.fetch_page import extract_page_id, fetch_all_properties, fetch_recent_items
from yahoo_auction.config import LISTING_DISPLAY_PROPERTIES, EXCLUDE_PROPERTIES

from notion.fetch_page import _get_database_id


class NotionTab:
    def __init__(self, page: ft.Page):
        self.page = page
        self.notion_data = None
        self._is_fetching = False
        self._build_ui()

    # ─────────────────────────────────────────────────────────────────
    # UI構築
    # ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # ── DB一覧パネル ──────────────────────────────────────────
        self.list_column = ft.Column(
            controls=[],
            scroll=ft.ScrollMode.AUTO,
            spacing=2,
        )

        self.refresh_btn = ft.ElevatedButton(
            "最新10件を取得",
            icon=ft.Icons.REFRESH,
            on_click=self.on_refresh_list,
            bgcolor=ft.Colors.BLUE_GREY_700,
            color=ft.Colors.WHITE,
        )
        self.list_status = ft.Text("", size=12, color=ft.Colors.GREY_600)

        list_panel = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text("最近の更新", size=14, weight=ft.FontWeight.BOLD),
                    self.refresh_btn,
                    self.list_status,
                ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Container(
                    content=self.list_column,
                    border=ft.border.all(1, ft.Colors.BLUE_GREY_100),
                    border_radius=6,
                    padding=ft.padding.all(6),
                    height=220,
                ),
            ], spacing=6),
            padding=ft.padding.only(bottom=8),
        )

        # ── URL手動入力 ─────────────────────────────────────────────
        self.url_field = ft.TextField(
            label="Notion共有URL（手動入力）",
            hint_text="https://www.notion.so/...",
            expand=True,
            dense=True,
        )
        self.fetch_btn = ft.ElevatedButton(
            "取得",
            icon=ft.Icons.DOWNLOAD,
            on_click=self.on_fetch_by_url,
            bgcolor=ft.Colors.BLUE,
            color=ft.Colors.WHITE,
        )

        # ── ステータス & プロパティ表示 ─────────────────────────────
        self.status_text = ft.Text("", size=14)

        self.props_column = ft.Column(
            controls=[],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=2,
        )

        self.copy_all_btn = ft.ElevatedButton(
            "全体をコピー",
            icon=ft.Icons.COPY_ALL,
            on_click=self.on_copy_all,
            visible=False,
        )

        # ── レイアウト ───────────────────────────────────────────────
        self.content = ft.Column(
            controls=[
                list_panel,
                ft.Row([self.url_field, self.fetch_btn],
                       alignment=ft.MainAxisAlignment.START),
                self.status_text,
                ft.Divider(height=4),
                self.props_column,
                ft.Divider(height=4),
                self.copy_all_btn,
            ],
            expand=True,
            spacing=8,
        )

    # ─────────────────────────────────────────────────────────────────
    # DB一覧更新
    # ─────────────────────────────────────────────────────────────────

    def on_refresh_list(self, e):
        if not _get_database_id():
            self._show_snackbar("_get_database_id() が未設定です", ft.Colors.RED)
            return
        if self._is_fetching:
            return

        self._is_fetching = True
        self.refresh_btn.disabled = True
        self.list_status.value = "取得中..."
        self.list_column.controls.clear()
        self.page.update()

        def do_fetch():
            try:
                items = fetch_recent_items(_get_database_id(), limit=10)

                def on_success():
                    self._render_item_list(items)
                    self.list_status.value = f"{len(items)}件"
                    self.page.update()

                self.page.run_thread(on_success)

            except Exception as ex:
                err = ex
                def on_error():
                    self.list_status.value = f"エラー: {err}"
                    self.page.update()
                self.page.run_thread(on_error)

            finally:
                def on_finish():
                    self._is_fetching = False
                    self.refresh_btn.disabled = False
                    self.page.update()
                self.page.run_thread(on_finish)

        threading.Thread(target=do_fetch, daemon=True).start()

    def _render_item_list(self, items: list[dict]):
        self.list_column.controls.clear()
        for item in items:
            dt = item["last_edited_time"][:16].replace("T", " ") if item["last_edited_time"] else ""
            row = ft.Container(
                content=ft.Row([
                    ft.Text(dt, size=11, color=ft.Colors.GREY_600, width=120, no_wrap=True),
                    ft.TextButton(
                        item["title"],
                        on_click=lambda e, pid=item["page_id"]: self._fetch_by_page_id(pid),
                        style=ft.ButtonStyle(padding=ft.padding.all(0)),
                    ),
                ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.padding.symmetric(horizontal=6, vertical=2),
                border_radius=4,
                ink=True,
            )
            self.list_column.controls.append(row)

    # ─────────────────────────────────────────────────────────────────
    # ページ詳細取得
    # ─────────────────────────────────────────────────────────────────

    def _fetch_by_page_id(self, page_id: str):
        if self._is_fetching:
            return
        self._start_fetch(lambda: fetch_all_properties(page_id))

    def on_fetch_by_url(self, e):
        url = self.url_field.value.strip()
        if not url:
            self._show_snackbar("URLを入力してください", ft.Colors.RED)
            return
        if self._is_fetching:
            return
        try:
            page_id = extract_page_id(url)
        except ValueError as ex:
            self._show_snackbar(str(ex), ft.Colors.RED)
            return
        self._start_fetch(lambda: fetch_all_properties(page_id))

    def _start_fetch(self, fetch_fn):
        self._is_fetching = True
        self.fetch_btn.disabled = True
        self.status_text.value = "取得中..."
        self.status_text.color = ft.Colors.BLUE
        self.props_column.controls.clear()
        self.copy_all_btn.visible = False
        self.page.update()

        def do_fetch():
            try:
                data = fetch_fn()
                self.notion_data = data

                def on_success():
                    self._display_properties(data)
                    title = data["properties"].get("商品名", {}).get("value", "")
                    self.status_text.value = f"取得完了: {title}"
                    self.status_text.color = ft.Colors.GREEN
                    self.copy_all_btn.visible = True
                    self.page.update()

                self.page.run_thread(on_success)

            except Exception as ex:
                err = ex
                def on_error():
                    self.status_text.value = f"エラー: {err}"
                    self.status_text.color = ft.Colors.RED
                    self.page.update()
                self.page.run_thread(on_error)

            finally:
                def on_finish():
                    self._is_fetching = False
                    self.fetch_btn.disabled = False
                    self.page.update()
                self.page.run_thread(on_finish)

        threading.Thread(target=do_fetch, daemon=True).start()

    # ─────────────────────────────────────────────────────────────────
    # プロパティ表示
    # ─────────────────────────────────────────────────────────────────

    def _display_properties(self, data: dict):
        self.props_column.controls.clear()
        props = data.get("properties", {})

        displayed = set()
        ordered_names = list(LISTING_DISPLAY_PROPERTIES)
        for name in props:
            if name not in EXCLUDE_PROPERTIES and name not in ordered_names:
                ordered_names.append(name)

        for name in ordered_names:
            if name in EXCLUDE_PROPERTIES or name in displayed:
                continue
            info = props.get(name)
            if not info:
                continue
            value = info.get("value")
            if value is None or value == "" or value == [] or value == {} or value is False:
                continue

            displayed.add(name)

            files = self._to_file_list(value)
            if files is not None:
                row = self._build_files_row(name, files)
            else:
                row = self._build_text_row(name, value)

            self.props_column.controls.append(row)

    def _to_file_list(self, value) -> list[dict] | None:
        """値を {"name": str, "url": str} リストに正規化する。画像でなければ None を返す"""
        if not isinstance(value, list) or not value:
            return None
        first = value[0]
        # dict形式 {"name": ..., "url": ...}
        if isinstance(first, dict) and "url" in first:
            return [{"name": f.get("name") or "", "url": f.get("url") or ""} for f in value]
        # 文字列URLリスト（rollupが文字列で返してくるケース）
        if isinstance(first, str) and first.startswith("http"):
            return [{"name": "", "url": u} for u in value if isinstance(u, str)]
        return None

    def _build_text_row(self, name: str, value) -> ft.Container:
        display_value = self._format_value(value)
        return ft.Container(
            content=ft.Row(
                [
                    ft.Text(name, size=13, weight=ft.FontWeight.BOLD,
                            width=150, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(display_value, size=13, expand=True,
                            max_lines=3, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.IconButton(
                        icon=ft.Icons.CONTENT_COPY, icon_size=16, tooltip="コピー",
                        data=str(value), on_click=self._on_copy_value,
                    ),
                ],
                alignment=ft.MainAxisAlignment.START,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=10, vertical=4),
            border_radius=5,
            ink=True,
            on_click=lambda e, v=str(value): self._copy_to_clipboard(v),
        )

    def _build_files_row(self, name: str, files: list) -> ft.Container:
        """files型プロパティ: ファイル名 + URL表示 + コピー/ダウンロードボタン"""
        url_rows = []
        for i, f in enumerate(files):
            url = f.get("url", "")
            fname = f.get("name", "") or f"image_{i + 1:02d}"
            # URLを短縮表示（先頭60文字）
            url_short = url[:80] + "…" if len(url) > 80 else url
            url_rows.append(
                ft.Column([
                    ft.Row([
                        ft.Text(f"[{i + 1}] {fname}", size=12, weight=ft.FontWeight.W_500,
                                color=ft.Colors.BLUE_GREY_700, expand=True,
                                no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.IconButton(
                            icon=ft.Icons.CONTENT_COPY, icon_size=14,
                            tooltip="URLをコピー",
                            on_click=lambda e, u=url: self._copy_to_clipboard(u),
                        ),
                    ], spacing=0, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Text(url_short, size=10, color=ft.Colors.BLUE_400,
                            selectable=True, no_wrap=True,
                            overflow=ft.TextOverflow.ELLIPSIS),
                ], spacing=0)
            )

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text(name, size=13, weight=ft.FontWeight.BOLD, width=150),
                    ft.Text(f"{len(files)}枚", size=13, color=ft.Colors.BLUE_GREY_600),
                    ft.ElevatedButton(
                        f"ダウンロード ({len(files)}枚)",
                        icon=ft.Icons.DOWNLOAD,
                        on_click=lambda e, imgs=files: self._download_images(imgs),
                        bgcolor=ft.Colors.INDIGO_400,
                        color=ft.Colors.WHITE,
                        height=32,
                    ),
                ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Container(
                    content=ft.Column(url_rows, spacing=0),
                    padding=ft.padding.only(left=160),
                ),
            ], spacing=4),
            padding=ft.padding.symmetric(horizontal=10, vertical=6),
            border_radius=5,
            bgcolor=ft.Colors.BLUE_50,
        )

    # ─────────────────────────────────────────────────────────────────
    # 画像ダウンロード
    # ─────────────────────────────────────────────────────────────────

    def _download_images(self, files: list):
        product_name = ""
        if self.notion_data:
            product_name = str(
                self.notion_data.get("properties", {}).get("商品名", {}).get("value", "")
            )

        safe_name = re.sub(r'[\\/*?:"<>|]', "_", product_name)[:30] if product_name else "images"
        project_root = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        save_dir = project_root / "downloads" / safe_name
        save_dir.mkdir(parents=True, exist_ok=True)

        self._show_snackbar("ダウンロード中...", ft.Colors.BLUE)

        def do_download():
            count = 0
            errors = 0
            for i, f in enumerate(files):
                url = f.get("url")
                name = f.get("name", f"image_{i:02d}.jpg")
                if not url:
                    continue
                try:
                    resp = requests.get(url, timeout=30)
                    resp.raise_for_status()
                    (save_dir / name).write_bytes(resp.content)
                    count += 1
                except Exception:
                    errors += 1

            def on_done():
                msg = f"{count}枚を downloads/{safe_name} へ保存しました"
                if errors:
                    msg += f" ({errors}件失敗)"
                color = ft.Colors.GREEN if errors == 0 else ft.Colors.ORANGE
                self._show_snackbar(msg, color)
                # ダウンロード完了後にフォルダを即座に開く
                self._open_folder(save_dir)

            self.page.run_thread(on_done)

        threading.Thread(target=do_download, daemon=True).start()

    def _open_folder(self, path: Path):
        """ダウンロードフォルダをOSのファイルマネージャーで開く"""
        try:
            if os.name == "nt":
                os.startfile(str(path))
            elif os.uname().sysname == "Darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────────
    # コピー・ユーティリティ
    # ─────────────────────────────────────────────────────────────────

    def _format_value(self, value) -> str:
        if isinstance(value, list):
            if value and isinstance(value[0], dict):
                return ", ".join(f.get("name", f.get("url", "")) for f in value)
            return ", ".join(str(v) for v in value)
        if isinstance(value, dict):
            return ", ".join(f"{k}: {v}" for k, v in value.items() if v is not None)
        return str(value)

    def _on_copy_value(self, e):
        self._copy_to_clipboard(e.control.data)

    def on_copy_all(self, e):
        if not self.notion_data:
            return
        lines = []
        props = self.notion_data.get("properties", {})
        ordered_names = list(LISTING_DISPLAY_PROPERTIES)
        for name in props:
            if name not in EXCLUDE_PROPERTIES and name not in ordered_names:
                ordered_names.append(name)
        for name in ordered_names:
            if name in EXCLUDE_PROPERTIES:
                continue
            info = props.get(name)
            if not info:
                continue
            value = info.get("value")
            if value is None or value == "" or value == [] or value == {}:
                continue
            lines.append(f"{name}: {self._format_value(value)}")
        self._copy_to_clipboard("\n".join(lines))

    def _copy_to_clipboard(self, text: str):
        self.page.set_clipboard(text)
        self._show_snackbar("コピーしました", ft.Colors.GREEN)

    def _show_snackbar(self, message: str, color):
        snack = ft.SnackBar(content=ft.Text(message), bgcolor=color)
        self.page.snack_bar = snack
        self.page.snack_bar.open = True
        self.page.update()

    # ─────────────────────────────────────────────────────────────────
    # タブ生成
    # ─────────────────────────────────────────────────────────────────

    def create_tab(self) -> ft.Tab:
        return ft.Tab(
            text="Notionデータ",
            icon=ft.Icons.DATASET,
            content=ft.Container(
                padding=ft.padding.all(20),
                content=self.content,
            ),
        )


def create_notion_tab(page: ft.Page) -> tuple[ft.Tab, "NotionTab"]:
    tab = NotionTab(page)
    return tab.create_tab(), tab
