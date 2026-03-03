"""
ラベル印刷タブ
- Notionから直近10件取得 or 商品名/IDで検索
- 選択した商品の指定フィールドを QR ラベルに印刷
"""

import os
import threading
import flet as ft

from notion.fetch_page import fetch_recent_items, search_items, fetch_all_properties
from brother_ql_proxy.notion import LabelPreviewGenerator
from brother_ql_proxy.utils import convert_to_brother_format

# ラベルに出力するフィールド（順番通り）
LABEL_FIELDS = ["商品名", "ID", "型番名", "年式", "売上金"]


class LabelTab:
    def __init__(self, proxy, page: ft.Page):
        self.proxy = proxy
        self.page = page
        self._page_data = None   # 現在選択中のページの全プロパティ
        self._is_loading = False
        self._build_ui()

    # ─────────────────────────────────────────────────────────────────
    # UI構築
    # ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # ── 一覧エリア ─────────────────────────────────────────────
        self.list_column = ft.Column(
            controls=[],
            scroll=ft.ScrollMode.AUTO,
            spacing=2,
        )
        self.refresh_btn = ft.ElevatedButton(
            "直近10件",
            icon=ft.Icons.REFRESH,
            on_click=self.on_refresh,
            bgcolor=ft.Colors.BLUE_GREY_700,
            color=ft.Colors.WHITE,
        )
        self.list_status = ft.Text("", size=12, color=ft.Colors.GREY_600)

        # ── 検索エリア ─────────────────────────────────────────────
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

        # ── 選択商品・フィールド表示 ───────────────────────────────
        self.selected_label = ft.Text(
            "商品が選択されていません",
            size=13,
            color=ft.Colors.GREY_600,
            italic=True,
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
        self._current_notion_url = ""
        self.fields_column = ft.Column(controls=[], spacing=4)

        # ── 印刷ボタン ─────────────────────────────────────────────
        self.print_btn = ft.ElevatedButton(
            "ラベル印刷",
            icon=ft.Icons.PRINT,
            on_click=self.on_print,
            bgcolor=ft.Colors.GREEN,
            color=ft.Colors.WHITE,
            disabled=True,
        )
        self.print_status = ft.Text("", size=13)

        # ── フォントサイズ設定 ─────────────────────────────────────
        _font_size = self.proxy.config.get('font_size', 16)
        self.font_size_value = ft.Text(str(_font_size), size=14, weight=ft.FontWeight.BOLD, width=30)
        self.font_size_slider = ft.Slider(
            min=8, max=36, divisions=14, value=_font_size,
            label="{value}",
            on_change=self._on_font_size_change,
            expand=True,
        )

        # ── QRサイズ設定 ───────────────────────────────────────────
        _qr_size = self.proxy.config.get('qr_size_scale', 3)
        self.qr_size_value = ft.Text(str(_qr_size), size=14, weight=ft.FontWeight.BOLD, width=20)
        self.qr_size_slider = ft.Slider(
            min=1, max=6, divisions=5, value=_qr_size,
            label="{value}",
            on_change=self._on_qr_size_change,
            expand=True,
        )

        # ── プレビュー ─────────────────────────────────────────────
        self.preview_btn = ft.ElevatedButton(
            "プレビュー",
            icon=ft.Icons.PREVIEW,
            on_click=self.on_preview,
            bgcolor=ft.Colors.INDIGO_400,
            color=ft.Colors.WHITE,
            disabled=True,
        )
        self.preview_status = ft.Text("", size=12)
        self.preview_img = ft.Image(
            visible=False,
            fit=ft.ImageFit.CONTAIN,
            width=600,
        )

        # ── レイアウト ───────────────────────────────────────────────
        self.content = ft.Column(
            controls=[
                ft.Text("QRラベル印刷", size=18, weight=ft.FontWeight.BOLD),
                ft.Divider(height=6),

                # 一覧
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
                    height=200,
                ),

                # 検索
                ft.Row([self.search_field, self.search_btn], spacing=4),
                ft.Divider(height=6),

                # 選択商品フィールド
                ft.Row([self.selected_label, self.notion_link_btn], spacing=8,
                       vertical_alignment=ft.CrossAxisAlignment.CENTER),
                self.fields_column,
                ft.Divider(height=6),

                # フォントサイズ設定
                ft.Row([
                    ft.Text("フォントサイズ:", size=13, width=110),
                    self.font_size_slider,
                    self.font_size_value,
                    ft.Text("pt", size=13),
                ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                # QRサイズ設定
                ft.Row([
                    ft.Text("QRコードサイズ:", size=13, width=110),
                    self.qr_size_slider,
                    self.qr_size_value,
                ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Divider(height=4),

                # 印刷・プレビュー
                ft.Row([self.print_btn, self.preview_btn, self.print_status],
                       spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                self.preview_status,
                self.preview_img,
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=8,
        )

    # ─────────────────────────────────────────────────────────────────
    # 一覧取得
    # ─────────────────────────────────────────────────────────────────

    def on_refresh(self, e):
        db_id = self.proxy.config.get("notion_database_id", "")
        if not db_id:
            self._snack("Notion Database ID が未設定です（設定タブで設定してください）", ft.Colors.RED)
            return
        if self._is_loading:
            return
        self._start_list_load(lambda: fetch_recent_items(db_id, limit=10))

    def on_search(self, e):
        query = self.search_field.value.strip()
        if not query:
            self._snack("検索ワードを入力してください", ft.Colors.ORANGE)
            return
        db_id = self.proxy.config.get("notion_database_id", "")
        if not db_id:
            self._snack("Notion Database ID が未設定です（設定タブで設定してください）", ft.Colors.RED)
            return
        if self._is_loading:
            return
        self._start_list_load(lambda: search_items(db_id, query))

    def _start_list_load(self, fetch_fn):
        self._is_loading = True
        self.refresh_btn.disabled = True
        self.list_status.value = "取得中..."
        self.list_column.controls.clear()
        self.page.update()

        def do():
            try:
                items = fetch_fn()

                def on_ok():
                    self._render_list(items)
                    self.list_status.value = f"{len(items)}件"
                    self.page.update()

                self.page.run_thread(on_ok)
            except Exception as ex:
                def on_err():
                    self.list_status.value = f"エラー: {ex}"
                    self.page.update()
                self.page.run_thread(on_err)
            finally:
                def on_fin():
                    self._is_loading = False
                    self.refresh_btn.disabled = False
                    self.page.update()
                self.page.run_thread(on_fin)

        threading.Thread(target=do, daemon=True).start()

    def _render_list(self, items: list[dict]):
        self.list_column.controls.clear()
        for item in items:
            dt = item["last_edited_time"][:16].replace("T", " ") if item["last_edited_time"] else ""
            row = ft.Container(
                content=ft.Row([
                    ft.Text(dt, size=11, color=ft.Colors.GREY_600, width=115, no_wrap=True),
                    ft.TextButton(
                        item["title"],
                        on_click=lambda e, pid=item["page_id"], t=item["title"]: self._select(pid, t),
                        style=ft.ButtonStyle(padding=ft.padding.all(0)),
                    ),
                ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.padding.symmetric(horizontal=4, vertical=2),
                border_radius=4,
                ink=True,
            )
            self.list_column.controls.append(row)

    # ─────────────────────────────────────────────────────────────────
    # 商品選択・フィールド表示
    # ─────────────────────────────────────────────────────────────────

    def _select(self, page_id: str, title: str):
        if self._is_loading:
            return
        self._is_loading = True
        self.selected_label.value = f"取得中: {title}..."
        self.selected_label.color = ft.Colors.BLUE
        self.fields_column.controls.clear()
        self.print_btn.disabled = True
        self.preview_btn.disabled = True
        self.preview_img.visible = False
        self.preview_status.value = ""
        self.print_status.value = ""
        self.page.update()

        def do():
            try:
                data = fetch_all_properties(page_id)
                self._page_data = data

                def on_ok():
                    self._render_fields(data)
                    self.selected_label.value = f"選択中: {title}"
                    self.selected_label.color = ft.Colors.GREEN_800
                    self.selected_label.italic = False
                    self.print_btn.disabled = False
                    self.preview_btn.disabled = False
                    self._current_notion_url = data.get("url", "")
                    self.notion_link_btn.visible = bool(self._current_notion_url)
                    self.page.update()

                self.page.run_thread(on_ok)
            except Exception as ex:
                def on_err():
                    self.selected_label.value = f"エラー: {ex}"
                    self.selected_label.color = ft.Colors.RED
                    self.page.update()
                self.page.run_thread(on_err)
            finally:
                def on_fin():
                    self._is_loading = False
                    self.page.update()
                self.page.run_thread(on_fin)

        threading.Thread(target=do, daemon=True).start()

    def _render_fields(self, data: dict):
        self.fields_column.controls.clear()
        props = data.get("properties", {})
        for name in LABEL_FIELDS:
            info = props.get(name)
            value = info.get("value") if info else None
            display = self._fmt(value) if value is not None else "—"
            self.fields_column.controls.append(
                ft.Container(
                    content=ft.Row([
                        ft.Text(name, size=13, weight=ft.FontWeight.BOLD, width=100),
                        ft.Text(display, size=13, expand=True,
                                max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                    ]),
                    padding=ft.padding.symmetric(horizontal=8, vertical=3),
                    bgcolor=ft.Colors.GREY_100,
                    border_radius=4,
                )
            )

    def _fmt(self, value) -> str:
        if isinstance(value, list):
            return ", ".join(str(v) for v in value)
        if isinstance(value, dict):
            return ", ".join(f"{k}: {v}" for k, v in value.items() if v is not None)
        return str(value)

    # ─────────────────────────────────────────────────────────────────
    # 印刷
    # ─────────────────────────────────────────────────────────────────

    def on_print(self, e):
        if not self._page_data:
            return
        self.print_btn.disabled = True
        self.print_status.value = "印刷中..."
        self.print_status.color = ft.Colors.BLUE
        self.page.update()

        def do():
            try:
                props = self._page_data.get("properties", {})
                printable_fields = []
                for name in LABEL_FIELDS:
                    info = props.get(name)
                    value = info.get("value") if info else None
                    if value is not None and value != "" and value != [] and value != {}:
                        printable_fields.append({
                            "name": name,
                            "value": self._fmt(value),
                            "type": info.get("type", ""),
                        })

                page_url = self._page_data.get("url", "")
                page_id = self._page_data.get("page_id", "")
                vercel_base_url = self.proxy.config.get("vercel_base_url", "").rstrip("/")
                qr_data = (
                    f"{vercel_base_url}/items/{page_id}"
                    if vercel_base_url and page_id
                    else page_url or "no-url"
                )

                gen = LabelPreviewGenerator()
                label_size = self.proxy.config.get("label_size", "62")
                img = gen.create_print_data(
                    printable_fields,
                    label_size=label_size,
                    include_qr=True,
                    qr_data=qr_data,
                    font_size=int(self.font_size_slider.value),
                    qr_size_scale=int(self.qr_size_slider.value),
                )
                raster = convert_to_brother_format(img, label_size)
                success = self.proxy.send_raw_data_to_printer(raster)

                def on_ok():
                    if success:
                        self.print_status.value = "印刷完了"
                        self.print_status.color = ft.Colors.GREEN
                    else:
                        self.print_status.value = "印刷失敗"
                        self.print_status.color = ft.Colors.RED
                    self.page.update()

                self.page.run_thread(on_ok)
            except Exception as ex:
                def on_err():
                    self.print_status.value = f"エラー: {ex}"
                    self.print_status.color = ft.Colors.RED
                    self.page.update()
                self.page.run_thread(on_err)
            finally:
                def on_fin():
                    self.print_btn.disabled = False
                    self.page.update()
                self.page.run_thread(on_fin)

        threading.Thread(target=do, daemon=True).start()

    # ─────────────────────────────────────────────────────────────────
    # フォントサイズ・プレビュー
    # ─────────────────────────────────────────────────────────────────

    def _on_font_size_change(self, e):
        v = int(e.control.value)
        self.font_size_value.value = str(v)
        self.proxy.config['font_size'] = v
        self.proxy.save_config()
        self.page.update()

    def _on_qr_size_change(self, e):
        v = int(e.control.value)
        self.qr_size_value.value = str(v)
        self.proxy.config['qr_size_scale'] = v
        self.proxy.save_config()
        self.page.update()

    def on_preview(self, e):
        if not self._page_data:
            return
        self.preview_btn.disabled = True
        self.preview_status.value = "プレビュー生成中..."
        self.preview_status.color = ft.Colors.BLUE
        self.preview_img.visible = False
        self.page.update()

        def do():
            try:
                props = self._page_data.get("properties", {})
                printable_fields = []
                for name in LABEL_FIELDS:
                    info = props.get(name)
                    value = info.get("value") if info else None
                    if value is not None and value != "" and value != [] and value != {}:
                        printable_fields.append({
                            "name": name,
                            "value": self._fmt(value),
                            "type": info.get("type", ""),
                        })

                page_url = self._page_data.get("url", "")
                page_id = self._page_data.get("page_id", "")
                vercel_base_url = self.proxy.config.get("vercel_base_url", "").rstrip("/")
                qr_data = (
                    f"{vercel_base_url}/items/{page_id}"
                    if vercel_base_url and page_id
                    else page_url or "no-url"
                )
                font_size = int(self.font_size_slider.value)
                label_size = self.proxy.config.get("label_size", "62")
                gen = LabelPreviewGenerator()
                result = gen.generate_preview(
                    printable_fields,
                    label_size=label_size,
                    include_qr=True,
                    qr_data=qr_data,
                    font_size=font_size,
                    qr_size_scale=int(self.qr_size_slider.value),
                )

                def on_ok():
                    if result.get("success"):
                        img_data = result["preview_image"].split(",")[1]
                        self.preview_img.src_base64 = img_data
                        self.preview_img.visible = True
                        self.preview_status.value = "プレビュー完了"
                        self.preview_status.color = ft.Colors.GREEN
                    else:
                        self.preview_status.value = f"エラー: {result.get('error')}"
                        self.preview_status.color = ft.Colors.RED
                    self.page.update()

                self.page.run_thread(on_ok)
            except Exception as ex:
                def on_err():
                    self.preview_status.value = f"エラー: {ex}"
                    self.preview_status.color = ft.Colors.RED
                    self.page.update()
                self.page.run_thread(on_err)
            finally:
                def on_fin():
                    self.preview_btn.disabled = False
                    self.page.update()
                self.page.run_thread(on_fin)

        threading.Thread(target=do, daemon=True).start()

    # ─────────────────────────────────────────────────────────────────
    # Notionリンクを開く
    # ─────────────────────────────────────────────────────────────────

    def _on_open_notion(self, e):
        if self._current_notion_url:
            self.page.launch_url(self._current_notion_url)

    # ─────────────────────────────────────────────────────────────────
    # ユーティリティ
    # ─────────────────────────────────────────────────────────────────

    def _snack(self, msg: str, color):
        snack = ft.SnackBar(content=ft.Text(msg), bgcolor=color)
        self.page.snack_bar = snack
        self.page.snack_bar.open = True
        self.page.update()

    def create_tab(self) -> ft.Tab:
        return ft.Tab(
            text="ラベル印刷",
            icon=ft.Icons.QR_CODE,
            content=ft.Container(
                padding=ft.padding.all(20),
                content=self.content,
            ),
        )


def create_label_tab(proxy, page: ft.Page) -> tuple[ft.Tab, LabelTab]:
    tab = LabelTab(proxy, page)
    return tab.create_tab(), tab
