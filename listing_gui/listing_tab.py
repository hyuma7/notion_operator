"""
出品タブ（統合版）
- 左ペイン: 商品選択（Notionリスト + 商品名/ID検索）
- 右ペイン: 商品詳細プロパティ表示 + Notionリンク
- 下部: 出品先選択 + 実行（ログイン・出品を1ボタンに統合）
"""

import os
import re
import subprocess
import threading
import flet as ft
import requests

from pathlib import Path

from notion.fetch_page import extract_page_id, fetch_all_properties, fetch_recent_items, search_items
from yahoo_auction.config import LISTING_DISPLAY_PROPERTIES, EXCLUDE_PROPERTIES
from yahoo_auction.login import YahooLogin
from yahoo_auction.listing import YahooAuctionListing

from notion.fetch_page import _get_database_id


class ListingTab:
    def __init__(self, page: ft.Page):
        self.page = page
        self.notion_data = None
        self._current_notion_url = ""
        self._is_fetching = False
        self._is_running = False
        self.login = None
        self.listing = None
        self._build_ui()

    # ─────────────────────────────────────────────────────────────────
    # UI構築
    # ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # ── 左ペイン: 商品選択 ──────────────────────────────────────
        self.list_column = ft.Column(
            controls=[],
            scroll=ft.ScrollMode.AUTO,
            spacing=2,
        )

        self.refresh_btn = ft.ElevatedButton(
            "直近10件",
            icon=ft.Icons.REFRESH,
            on_click=self.on_refresh_list,
            bgcolor=ft.Colors.BLUE_GREY_700,
            color=ft.Colors.WHITE,
            height=36,
        )
        self.list_status = ft.Text("", size=11, color=ft.Colors.GREY_600)

        self.search_field = ft.TextField(
            label="商品名 / ID で検索",
            hint_text="例: テスト商品  または  123",
            expand=True,
            dense=True,
            on_submit=self.on_search,
        )
        self.search_btn = ft.IconButton(
            icon=ft.Icons.SEARCH,
            tooltip="検索",
            on_click=self.on_search,
        )

        left_pane = ft.Container(
            width=300,
            content=ft.Column([
                ft.Row([
                    ft.Text("商品選択", size=14, weight=ft.FontWeight.BOLD),
                    self.refresh_btn,
                    self.list_status,
                ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Container(
                    content=self.list_column,
                    border=ft.border.all(1, ft.Colors.BLUE_GREY_100),
                    border_radius=6,
                    padding=ft.padding.all(6),
                    height=240,
                ),
                ft.Divider(height=8),
                ft.Row([self.search_field, self.search_btn], spacing=4),
            ], spacing=8),
            padding=ft.padding.only(right=12),
        )

        # ── 右ペイン: 商品詳細 ───────────────────────────────────────
        self.detail_status = ft.Text(
            "商品を選択してください",
            size=13,
            color=ft.Colors.GREY_500,
        )
        self.notion_link_btn = ft.TextButton(
            "Notionで開く",
            icon=ft.Icons.OPEN_IN_NEW,
            on_click=self._on_open_notion,
            visible=False,
            style=ft.ButtonStyle(
                color=ft.Colors.BLUE_400,
                padding=ft.padding.all(0),
            ),
        )
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
            height=32,
        )

        right_pane = ft.Container(
            expand=True,
            content=ft.Column([
                ft.Row([
                    self.detail_status,
                    self.notion_link_btn,
                ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Divider(height=4),
                self.props_column,
                self.copy_all_btn,
            ], expand=True, spacing=6),
        )

        # ── 上部エリア（左右ペイン） ─────────────────────────────────
        top_area = ft.Row(
            controls=[
                left_pane,
                ft.VerticalDivider(width=1),
                right_pane,
            ],
            expand=True,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )

        # ── 下部: 出品実行エリア ─────────────────────────────────────
        self.exec_status = ft.Text(
            "未接続",
            size=14,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.GREY,
        )

        # 出品先ボタン（将来のメルカリ等に備えた拡張点）
        self.yahoo_btn = ft.ElevatedButton(
            "ヤフオク",
            icon=ft.Icons.SELL,
            bgcolor=ft.Colors.BLUE_700,
            color=ft.Colors.WHITE,
            height=36,
        )
        self.mercari_btn = ft.ElevatedButton(
            "メルカリ（未実装）",
            icon=ft.Icons.STOREFRONT,
            disabled=True,
            height=36,
        )

        # ログイン + 出品を1ボタンに統合
        self.start_btn = ft.ElevatedButton(
            "出品開始",
            icon=ft.Icons.ROCKET_LAUNCH,
            on_click=self.on_start,
            bgcolor=ft.Colors.GREEN_700,
            color=ft.Colors.WHITE,
            height=40,
        )
        self.quit_btn = ft.ElevatedButton(
            "ブラウザ終了",
            icon=ft.Icons.CLOSE,
            on_click=self.on_quit,
            disabled=True,
            bgcolor=ft.Colors.RED_700,
            color=ft.Colors.WHITE,
            height=40,
        )

        self.log_column = ft.Column(
            controls=[],
            scroll=ft.ScrollMode.AUTO,
            spacing=2,
        )

        bottom_area = ft.Card(
            content=ft.Container(
                padding=ft.padding.all(12),
                content=ft.Column([
                    ft.Row([
                        ft.Text("出品先:", size=13, color=ft.Colors.GREY_700),
                        self.yahoo_btn,
                        self.mercari_btn,
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                    ft.Row([
                        self.start_btn,
                        self.quit_btn,
                        ft.Container(expand=True),
                        ft.Text("ステータス:", size=13),
                        self.exec_status,
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                    ft.Divider(height=6),
                    ft.Container(
                        content=self.log_column,
                        height=120,
                        border=ft.border.all(1, ft.Colors.BLUE_GREY_50),
                        border_radius=4,
                        padding=ft.padding.all(4),
                    ),
                ], spacing=8),
            ),
        )

        self.content = ft.Column(
            controls=[top_area, ft.Divider(height=4), bottom_area],
            expand=True,
            spacing=6,
        )

    # ─────────────────────────────────────────────────────────────────
    # 商品一覧取得
    # ─────────────────────────────────────────────────────────────────

    def on_refresh_list(self, e):
        db_id = _get_database_id()
        if not db_id:
            self._show_snackbar("Database IDが未設定です", ft.Colors.RED)
            return
        if self._is_fetching:
            return
        self._start_list_load(lambda: fetch_recent_items(db_id, limit=10))

    def on_search(self, e):
        query = self.search_field.value.strip()
        if not query:
            self._show_snackbar("検索ワードを入力してください", ft.Colors.ORANGE)
            return
        db_id = _get_database_id()
        if not db_id:
            self._show_snackbar("Database IDが未設定です", ft.Colors.RED)
            return
        if self._is_fetching:
            return
        self._start_list_load(lambda: search_items(db_id, query))

    def _start_list_load(self, fetch_fn):
        self._is_fetching = True
        self.refresh_btn.disabled = True
        self.list_status.value = "取得中..."
        self.list_column.controls.clear()
        self.page.update()

        def do_fetch():
            try:
                items = fetch_fn()

                def on_success():
                    self._render_item_list(items)
                    self.list_status.value = f"{len(items)}件"
                    self.page.update()

                self.page.run_thread(on_success)
            except Exception as ex:
                def on_error():
                    self.list_status.value = f"エラー: {ex}"
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
                    ft.Text(dt, size=11, color=ft.Colors.GREY_600, width=105, no_wrap=True),
                    ft.TextButton(
                        item["title"],
                        on_click=lambda e, pid=item["page_id"]: self._fetch_by_page_id(pid),
                        style=ft.ButtonStyle(padding=ft.padding.all(0)),
                    ),
                ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.padding.symmetric(horizontal=4, vertical=2),
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

    def _start_fetch(self, fetch_fn):
        self._is_fetching = True
        self.detail_status.value = "取得中..."
        self.detail_status.color = ft.Colors.BLUE
        self.notion_link_btn.visible = False
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
                    self.detail_status.value = f"選択中: {title}"
                    self.detail_status.color = ft.Colors.GREEN_700
                    self.copy_all_btn.visible = True
                    self._current_notion_url = data.get("url", "")
                    self.notion_link_btn.visible = bool(self._current_notion_url)
                    self.page.update()

                self.page.run_thread(on_success)
            except Exception as ex:
                def on_error():
                    self.detail_status.value = f"エラー: {ex}"
                    self.detail_status.color = ft.Colors.RED
                    self.page.update()
                self.page.run_thread(on_error)
            finally:
                def on_finish():
                    self._is_fetching = False
                    self.page.update()
                self.page.run_thread(on_finish)

        threading.Thread(target=do_fetch, daemon=True).start()

    # ─────────────────────────────────────────────────────────────────
    # Notionリンクを開く
    # ─────────────────────────────────────────────────────────────────

    def _on_open_notion(self, e):
        if self._current_notion_url:
            self.page.launch_url(self._current_notion_url)

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
        if not isinstance(value, list) or not value:
            return None
        first = value[0]
        if isinstance(first, dict) and "url" in first:
            return [{"name": f.get("name") or "", "url": f.get("url") or ""} for f in value]
        if isinstance(first, str) and first.startswith("http"):
            return [{"name": "", "url": u} for u in value if isinstance(u, str)]
        return None

    def _build_text_row(self, name: str, value) -> ft.Container:
        display_value = self._format_value(value)
        return ft.Container(
            content=ft.Row([
                ft.Text(name, size=13, weight=ft.FontWeight.BOLD,
                        width=140, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
                ft.Text(display_value, size=13, expand=True,
                        max_lines=3, overflow=ft.TextOverflow.ELLIPSIS),
                ft.IconButton(
                    icon=ft.Icons.CONTENT_COPY, icon_size=16, tooltip="コピー",
                    data=str(value), on_click=self._on_copy_value,
                ),
            ], alignment=ft.MainAxisAlignment.START,
               vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.padding.symmetric(horizontal=10, vertical=4),
            border_radius=5,
            ink=True,
            on_click=lambda e, v=str(value): self._copy_to_clipboard(v),
        )

    def _build_files_row(self, name: str, files: list) -> ft.Container:
        url_rows = []
        for i, f in enumerate(files):
            url = f.get("url", "")
            fname = f.get("name", "") or f"image_{i + 1:02d}"
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
                    ft.Text(name, size=13, weight=ft.FontWeight.BOLD, width=140),
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
                    padding=ft.padding.only(left=150),
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
                self._show_snackbar(msg, ft.Colors.GREEN if errors == 0 else ft.Colors.ORANGE)
                self._open_folder(save_dir)

            self.page.run_thread(on_done)

        threading.Thread(target=do_download, daemon=True).start()

    def _open_folder(self, path: Path):
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
    # 出品実行（ログイン + 出品 1ボタン）
    # ─────────────────────────────────────────────────────────────────

    def on_start(self, e):
        if not self.notion_data:
            self._show_snackbar("商品を選択してください", ft.Colors.RED)
            return
        if self._is_running:
            return

        self._is_running = True
        self.start_btn.disabled = True
        self.log_column.controls.clear()
        self.page.update()

        def on_progress(step: str, message: str):
            success = not message.startswith("[エラー]") and not message.startswith("[要素未発見]")
            def update():
                self._add_log(message, success=success)
            self.page.run_thread(update)

        def do_run():
            try:
                # ── ログイン確認（初回のみブラウザ起動） ─────────────
                already_ok = (
                    self.login is not None
                    and self.login.get_driver() is not None
                    and self.login.check_login_status()
                )

                if not already_ok:
                    def upd_login():
                        self._set_exec_status("ログイン中...", ft.Colors.ORANGE)
                        self._add_log("ブラウザを起動中...")
                        self.page.update()
                    self.page.run_thread(upd_login)

                    if not self.login:
                        self.login = YahooLogin()
                    if not self.login.get_driver():
                        self.login.init_driver()

                    logged_in = self.login.ensure_login()
                    if not logged_in:
                        def on_login_fail():
                            self._set_exec_status("ログイン失敗", ft.Colors.RED)
                            self._add_log("ログインに失敗しました", success=False)
                            self.quit_btn.disabled = False
                            self.page.update()
                        self.page.run_thread(on_login_fail)
                        return

                    def on_login_ok():
                        self._set_exec_status("ログイン済み", ft.Colors.GREEN)
                        self._add_log("ログイン成功")
                        self.quit_btn.disabled = False
                        self.page.update()
                    self.page.run_thread(on_login_ok)
                else:
                    def upd_already():
                        self._set_exec_status("ログイン済み", ft.Colors.GREEN)
                        self._add_log("ログイン確認済み")
                        self.page.update()
                    self.page.run_thread(upd_already)

                # ── 出品フォーム自動入力 ─────────────────────────────
                def upd_start():
                    self._add_log("出品フォーム自動入力を開始...")
                    self.page.update()
                self.page.run_thread(upd_start)

                self.listing = YahooAuctionListing(self.login.get_driver())
                self.listing.fill_form(self.notion_data, on_progress=on_progress)

                def on_done():
                    self._add_log("自動入力完了 - フォームを確認して手動で出品してください")
                    self._set_exec_status("入力完了", ft.Colors.GREEN)
                    self.page.update()
                self.page.run_thread(on_done)

            except Exception as ex:
                def on_error():
                    self._add_log(f"エラー: {ex}", success=False)
                    self._set_exec_status("エラー", ft.Colors.RED)
                    self.page.update()
                self.page.run_thread(on_error)

            finally:
                def on_finish():
                    self._is_running = False
                    self.start_btn.disabled = False
                    if self.listing:
                        self.listing.cleanup()
                    self.page.update()
                self.page.run_thread(on_finish)

        threading.Thread(target=do_run, daemon=True).start()

    def on_quit(self, e):
        if self.login:
            self.login.quit()
            self.login = None
        self.listing = None
        self._set_exec_status("未接続", ft.Colors.GREY)
        self.quit_btn.disabled = True
        self._add_log("ブラウザを閉じました")
        self.page.update()

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

    def _add_log(self, message: str, success: bool = True):
        icon = ft.Icons.CHECK_CIRCLE if success else ft.Icons.ERROR
        color = ft.Colors.GREEN if success else ft.Colors.RED
        row = ft.Row([
            ft.Icon(icon, size=16, color=color),
            ft.Text(message, size=13),
        ], spacing=5)
        self.log_column.controls.append(row)
        self.page.update()

    def _set_exec_status(self, text: str, color):
        self.exec_status.value = text
        self.exec_status.color = color
        self.page.update()

    # ─────────────────────────────────────────────────────────────────
    # タブ生成
    # ─────────────────────────────────────────────────────────────────

    def create_tab(self) -> ft.Tab:
        return ft.Tab(
            text="出品",
            icon=ft.Icons.SELL,
            content=ft.Container(
                padding=ft.padding.all(16),
                content=self.content,
            ),
        )


def create_listing_tab(page: ft.Page) -> ft.Tab:
    return ListingTab(page).create_tab()
