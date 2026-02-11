"""
Notionデータ取得・表示・コピータブ
"""

import threading
import flet as ft

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fetch_notion_page import extract_page_id, fetch_all_properties
from yahoo_auction.config import LISTING_DISPLAY_PROPERTIES, EXCLUDE_PROPERTIES


class NotionTab:
    def __init__(self, page: ft.Page):
        self.page = page
        self.notion_data = None  # 取得したデータ（他タブから参照可能）
        self._is_fetching = False
        self._build_ui()

    def _build_ui(self):
        # URL入力
        self.url_field = ft.TextField(
            label="Notion共有URL",
            hint_text="https://www.notion.so/...",
            expand=True,
        )

        self.fetch_btn = ft.ElevatedButton(
            "取得",
            icon=ft.Icons.DOWNLOAD,
            on_click=self.on_fetch,
            bgcolor=ft.Colors.BLUE,
            color=ft.Colors.WHITE,
        )

        # ステータス
        self.status_text = ft.Text("", size=14)

        # プロパティ一覧表示エリア
        self.props_column = ft.Column(
            controls=[],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=2,
        )

        # 全体コピーボタン
        self.copy_all_btn = ft.ElevatedButton(
            "全体をコピー",
            icon=ft.Icons.COPY_ALL,
            on_click=self.on_copy_all,
            visible=False,
        )

        # レイアウト
        self.content = ft.Column(
            controls=[
                ft.Row(
                    [self.url_field, self.fetch_btn],
                    alignment=ft.MainAxisAlignment.START,
                ),
                self.status_text,
                ft.Divider(),
                self.props_column,
                ft.Divider(),
                self.copy_all_btn,
            ],
            expand=True,
            spacing=10,
        )

    def on_fetch(self, e):
        """Notionデータを取得"""
        url = self.url_field.value.strip()
        if not url:
            self._show_snackbar("URLを入力してください", ft.Colors.RED)
            return

        if self._is_fetching:
            return

        self._is_fetching = True
        self.fetch_btn.disabled = True
        self.status_text.value = "取得中..."
        self.status_text.color = ft.Colors.BLUE
        self.props_column.controls.clear()
        self.copy_all_btn.visible = False
        self.page.update()

        def do_fetch():
            try:
                page_id = extract_page_id(url)
                data = fetch_all_properties(page_id)
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
                def on_error():
                    self.status_text.value = f"エラー: {ex}"
                    self.status_text.color = ft.Colors.RED
                    self.page.update()

                self.page.run_thread(on_error)

            finally:
                def on_finish():
                    self._is_fetching = False
                    self.fetch_btn.disabled = False
                    self.page.update()

                self.page.run_thread(on_finish)

        thread = threading.Thread(target=do_fetch, daemon=True)
        thread.start()

    def _display_properties(self, data: dict):
        """プロパティ一覧を表示（スキーマ順、除外フィルタ適用）"""
        self.props_column.controls.clear()
        props = data.get("properties", {})

        # スキーマ順に表示
        displayed = set()
        ordered_names = list(LISTING_DISPLAY_PROPERTIES)
        # スキーマにないが除外リストにもないプロパティを末尾に追加
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
            display_value = self._format_value(value)

            row = ft.Container(
                content=ft.Row(
                    [
                        ft.Text(
                            name,
                            size=13,
                            weight=ft.FontWeight.BOLD,
                            width=150,
                            no_wrap=True,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.Text(
                            display_value,
                            size=13,
                            expand=True,
                            max_lines=3,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.CONTENT_COPY,
                            icon_size=16,
                            tooltip="コピー",
                            data=str(value),
                            on_click=self._on_copy_value,
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

            self.props_column.controls.append(row)

    def _format_value(self, value) -> str:
        """値を表示用に整形"""
        if isinstance(value, list):
            if value and isinstance(value[0], dict):
                # files型
                return ", ".join(
                    f.get("name", f.get("url", "")) for f in value
                )
            return ", ".join(str(v) for v in value)
        if isinstance(value, dict):
            # date型など
            parts = []
            for k, v in value.items():
                if v is not None:
                    parts.append(f"{k}: {v}")
            return ", ".join(parts)
        return str(value)

    def _on_copy_value(self, e):
        """個別コピーボタン"""
        value = e.control.data
        self._copy_to_clipboard(value)

    def on_copy_all(self, e):
        """全体コピー（スキーマ順、除外フィルタ適用）"""
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

        text = "\n".join(lines)
        self._copy_to_clipboard(text)

    def _copy_to_clipboard(self, text: str):
        """クリップボードにコピー"""
        self.page.set_clipboard(text)
        self._show_snackbar("コピーしました", ft.Colors.GREEN)

    def _show_snackbar(self, message: str, color):
        snack = ft.SnackBar(content=ft.Text(message), bgcolor=color)
        self.page.snack_bar = snack
        self.page.snack_bar.open = True
        self.page.update()

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
