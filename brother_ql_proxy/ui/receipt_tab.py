"""
領収書タブ
- Notionから直近30件取得 or 商品名で検索
- チェックボックスで複数選択
- 選択した商品の領収書プレビューを表示
- PDF形式で請求書・領収証を出力
"""

import os
import platform
import uuid
import threading
from datetime import date, datetime
import flet as ft

from notion.fetch_page import fetch_recent_items, search_items, fetch_all_properties
from .export.pdf_service import (
    generate_invoice_receipt_pdf,
    issuer_info_from_config,
    MAX_INVOICE_ROWS_PER_PAGE,
)


def _fmt_currency(value) -> str:
    try:
        n = int(value)
        return f"¥{n:,}"
    except (TypeError, ValueError):
        return "¥0"


class ReceiptTab:
    def __init__(self, proxy, page: ft.Page):
        self.proxy = proxy
        self.page = page
        self._is_loading = False
        self._selected_items: dict[str, str] = {}   # page_id → title
        self._item_data_cache: dict[str, dict] = {}  # page_id → properties data
        self._current_list: list[dict] = []
        self._build_ui()

    # ─────────────────────────────────────────────────────────────────
    # UI構築
    # ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.list_column = ft.Column(
            controls=[],
            scroll=ft.ScrollMode.AUTO,
            spacing=2,
        )
        self.refresh_btn = ft.ElevatedButton(
            "直近30件",
            icon=ft.Icons.REFRESH,
            on_click=self.on_refresh,
            bgcolor=ft.Colors.BLUE_GREY_700,
            color=ft.Colors.WHITE,
        )
        self.list_status = ft.Text("", size=12, color=ft.Colors.GREY_600)

        self.search_field = ft.TextField(
            label="商品名で検索",
            hint_text="例: MacBook",
            expand=True,
            dense=True,
            on_submit=self.on_search,
        )
        self.search_btn = ft.IconButton(
            icon=ft.Icons.SEARCH,
            tooltip="検索",
            on_click=self.on_search,
        )

        self.selection_label = ft.Text(
            "0件選択中",
            size=13,
            color=ft.Colors.GREY_600,
        )
        self.clear_btn = ft.TextButton(
            "選択解除",
            on_click=self._clear_selection,
        )

        self.recipient_field = ft.TextField(
            label="請求先・宛名",
            hint_text="例: 株式会社〇〇",
            dense=True,
            expand=True,
        )
        self.issue_date_field = ft.TextField(
            label="発行日",
            hint_text="YYYY-MM-DD",
            value=date.today().strftime("%Y-%m-%d"),
            dense=True,
            width=150,
        )
        self.receipt_note_field = ft.TextField(
            label="但し書き",
            value="上記金額正に領収いたしました",
            dense=True,
            expand=True,
        )

        self.preview_column = ft.Column(controls=[], spacing=4, visible=False)

        self.preview_btn = ft.ElevatedButton(
            "プレビュー",
            icon=ft.Icons.PREVIEW,
            on_click=self.on_preview,
            bgcolor=ft.Colors.BLUE_700,
            color=ft.Colors.WHITE,
            disabled=True,
        )
        self.export_btn = ft.ElevatedButton(
            "PDF出力",
            icon=ft.Icons.PICTURE_AS_PDF,
            on_click=self.on_export,
            bgcolor=ft.Colors.RED_700,
            color=ft.Colors.WHITE,
            disabled=True,
        )
        self.export_status = ft.Text("", size=13)

        self.content = ft.Column(
            controls=[
                ft.Text("領収書", size=18, weight=ft.FontWeight.BOLD),
                ft.Divider(height=6),

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
                    height=300,
                ),

                ft.Row([self.search_field, self.search_btn], spacing=4),
                ft.Divider(height=6),

                ft.Row([
                    self.selection_label,
                    self.clear_btn,
                ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Divider(height=6),

                ft.Container(
                    content=ft.Column([
                        ft.Text("発行内容", size=14, weight=ft.FontWeight.BOLD),
                        ft.Row(
                            [self.recipient_field, self.issue_date_field],
                            spacing=10,
                        ),
                        self.receipt_note_field,
                    ], spacing=8),
                    border=ft.border.all(1, ft.Colors.BLUE_GREY_100),
                    border_radius=6,
                    padding=ft.padding.all(12),
                    bgcolor=ft.Colors.BLUE_GREY_50,
                ),
                ft.Divider(height=6),

                self.preview_column,

                ft.Row(
                    [self.preview_btn, self.export_btn, self.export_status],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
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
        self._start_list_load(lambda: fetch_recent_items(db_id, limit=30))

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
                    self._current_list = items
                    self._render_list(items)
                    self.list_status.value = f"{len(items)}件"
                    self.page.update()

                self.page.run_thread(on_ok)
            except Exception as ex:
                err = ex

                def on_err():
                    self.list_status.value = f"エラー: {err}"
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
            pid = item["page_id"]
            title = item["title"]
            dt = item["last_edited_time"][:16].replace("T", " ") if item.get("last_edited_time") else ""
            is_checked = pid in self._selected_items

            cb = ft.Checkbox(
                value=is_checked,
                on_change=lambda e, p=pid, t=title: self._on_check(e, p, t),
            )
            row = ft.Container(
                content=ft.Row([
                    cb,
                    ft.Text(dt, size=11, color=ft.Colors.GREY_600, width=115, no_wrap=True),
                    ft.Text(title, size=12, expand=True, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
                ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.padding.symmetric(horizontal=4, vertical=2),
                border_radius=4,
                bgcolor=ft.Colors.GREEN_50 if is_checked else None,
            )
            self.list_column.controls.append(row)

    def _on_check(self, e, page_id: str, title: str):
        if e.control.value:
            self._selected_items[page_id] = title
        else:
            self._selected_items.pop(page_id, None)
        self._refresh_list_colors()
        self._update_selection_state()

    def _refresh_list_colors(self):
        for ctrl in self.list_column.controls:
            row = ctrl.content
            cb = row.controls[0]
            pid = None
            for item in self._current_list:
                if item["title"] == row.controls[2].value:
                    pid = item["page_id"]
                    break
            is_checked = cb.value
            ctrl.bgcolor = ft.Colors.GREEN_50 if is_checked else None
        self.page.update()

    def _update_selection_state(self):
        n = len(self._selected_items)
        self.selection_label.value = f"{n}件選択中"
        self.selection_label.color = ft.Colors.GREEN_800 if n > 0 else ft.Colors.GREY_600
        self.preview_btn.disabled = n == 0
        self.export_btn.disabled = n == 0
        self.page.update()

    def _clear_selection(self, e=None):
        self._selected_items.clear()
        self._render_list(self._current_list)
        self._update_selection_state()
        self.preview_column.visible = False
        self.preview_column.controls.clear()
        self.export_status.value = ""
        self.page.update()

    # ─────────────────────────────────────────────────────────────────
    # 選択データ取得
    # ─────────────────────────────────────────────────────────────────

    def _fetch_selected_data(self) -> list[tuple[str, dict]]:
        """選択中の全アイテムのプロパティを取得（キャッシュ利用）"""
        result = []
        for pid, title in self._selected_items.items():
            if pid not in self._item_data_cache:
                data = fetch_all_properties(pid)
                self._item_data_cache[pid] = data
            result.append((pid, self._item_data_cache[pid]))
        return result

    def _get_recipient(self) -> str:
        return (self.recipient_field.value or "").strip()

    def _get_receipt_note(self) -> str:
        return (self.receipt_note_field.value or "").strip() or "上記金額正に領収いたしました"

    def _get_issue_date(self) -> str:
        raw = (self.issue_date_field.value or "").strip()
        if not raw:
            return date.today().strftime("%Y年%m月%d日")
        for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
            try:
                return datetime.strptime(raw, fmt).strftime("%Y年%m月%d日")
            except ValueError:
                pass
        return raw

    def _get_issue_date_filename(self) -> str:
        raw = (self.issue_date_field.value or "").strip()
        for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
            try:
                return datetime.strptime(raw, fmt).strftime("%Y%m%d")
            except ValueError:
                pass
        return date.today().strftime("%Y%m%d")

    def _get_issuer(self) -> dict[str, object]:
        return issuer_info_from_config(self.proxy.config)

    def _invoice_page_count(self, item_count: int) -> int:
        return max(1, (item_count + MAX_INVOICE_ROWS_PER_PAGE - 1) // MAX_INVOICE_ROWS_PER_PAGE)

    # ─────────────────────────────────────────────────────────────────
    # プレビュー
    # ─────────────────────────────────────────────────────────────────

    def on_preview(self, e):
        if not self._selected_items or self._is_loading:
            return
        self._is_loading = True
        self.preview_btn.disabled = True
        self.export_btn.disabled = True
        self.export_status.value = "データ取得中..."
        self.page.update()

        def do():
            try:
                fetched = self._fetch_selected_data()

                def on_ok():
                    self._render_preview(fetched)
                    self.export_btn.disabled = False
                    self.export_status.value = ""
                    self.page.update()

                self.page.run_thread(on_ok)
            except Exception as ex:
                err = ex

                def on_err():
                    self.export_status.value = f"エラー: {err}"
                    self.export_status.color = ft.Colors.RED
                    self.page.update()

                self.page.run_thread(on_err)
            finally:
                def on_fin():
                    self._is_loading = False
                    self.preview_btn.disabled = False
                    self.page.update()

                self.page.run_thread(on_fin)

        threading.Thread(target=do, daemon=True).start()

    def _render_preview(self, fetched: list[tuple[str, dict]]):
        header_style = ft.TextStyle(size=11, weight=ft.FontWeight.BOLD)

        def cell(text, bold=False, right=False):
            return ft.DataCell(ft.Text(
                text,
                size=11,
                weight=ft.FontWeight.BOLD if bold else ft.FontWeight.NORMAL,
                text_align=ft.TextAlign.RIGHT if right else ft.TextAlign.LEFT,
            ))

        items_data = self._extract_items_data(fetched)
        subtotal = sum(amt for _, _, amt in items_data)
        tax = int(subtotal * 0.1)
        total = subtotal + tax
        issue_date = self._get_issue_date()
        recipient = self._get_recipient()
        receipt_note = self._get_receipt_note()
        issuer = self._get_issuer()
        invoice_number = str(issuer.get("invoice_number", "") or "").strip()
        page_count = self._invoice_page_count(len(items_data))

        rows = []
        for idx, (item_name, model_number, amount) in enumerate(items_data):
            rows.append(ft.DataRow(cells=[
                cell(str(idx + 1)),
                cell(item_name),
                cell("1", right=True),
                cell(_fmt_currency(amount) if amount else "", right=True),
                cell("10%" if amount else "", right=True),
                cell(model_number),
            ]))

        item_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("連番", style=header_style)),
                ft.DataColumn(ft.Text("品名", style=header_style)),
                ft.DataColumn(ft.Text("数量", style=header_style), numeric=True),
                ft.DataColumn(ft.Text("金額", style=header_style), numeric=True),
                ft.DataColumn(ft.Text("税率", style=header_style), numeric=True),
                ft.DataColumn(ft.Text("備考", style=header_style)),
            ],
            rows=rows,
            border=ft.border.all(1, ft.Colors.GREY_400),
            border_radius=4,
            column_spacing=20,
        )

        summary_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("")),
                ft.DataColumn(ft.Text(""), numeric=True),
            ],
            rows=[
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text("小計", size=11)),
                    ft.DataCell(ft.Text(_fmt_currency(subtotal), size=11, text_align=ft.TextAlign.RIGHT)),
                ]),
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text("消費税 (税率10%)", size=11)),
                    ft.DataCell(ft.Text(_fmt_currency(tax), size=11, text_align=ft.TextAlign.RIGHT)),
                ]),
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text("合計", size=13, weight=ft.FontWeight.BOLD)),
                    ft.DataCell(ft.Text(_fmt_currency(total), size=13, weight=ft.FontWeight.BOLD,
                                       text_align=ft.TextAlign.RIGHT)),
                ]),
            ],
            border=ft.border.all(1, ft.Colors.GREY_400),
            border_radius=4,
            column_spacing=20,
        )

        stamp_lines = [str(line) for line in (issuer.get("stamp_lines") or []) if str(line).strip()]
        stamp_image_path = str(issuer.get("stamp_image_path") or "")
        if stamp_image_path and os.path.exists(stamp_image_path):
            hanko_content = ft.Image(src=stamp_image_path, fit=ft.ImageFit.CONTAIN, opacity=0.6)
            hanko_border = None
            hanko_bgcolor = None
        else:
            hanko_content = ft.Text(
                "\n".join(stamp_lines[:5]),
                size=9,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.with_opacity(0.6, ft.Colors.RED_900),
                text_align=ft.TextAlign.CENTER,
            )
            hanko_border = ft.border.all(2, ft.Colors.with_opacity(0.45, ft.Colors.RED_900))
            hanko_bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.RED_200)

        # ハンコ（1個のみ・左寄り・半透明）
        hanko = ft.Container(
            content=hanko_content,
            width=80,
            height=80,
            border=hanko_border,
            border_radius=40,
            bgcolor=hanko_bgcolor,
            alignment=ft.alignment.center,
            padding=ft.padding.all(4),
        )

        # 発行者情報ブロック（右寄り）
        issuer_lines = [
            ft.Text(str(issuer.get("company_name", "")), size=10),
            ft.Text(str(issuer.get("representative", "")), size=10),
            ft.Text(str(issuer.get("address", "")), size=9, color=ft.Colors.GREY_700),
            ft.Text(str(issuer.get("tel", "")), size=9, color=ft.Colors.GREY_700),
        ]
        if invoice_number:
            issuer_lines.append(
                ft.Text(f"登録番号：{invoice_number}", size=9, color=ft.Colors.GREY_700)
            )
        issuer_block = ft.Column(issuer_lines, spacing=2)

        self.preview_column.controls = [
            ft.Container(
                content=ft.Column([
                    ft.Text("請　求　書", size=18, weight=ft.FontWeight.BOLD,
                            text_align=ft.TextAlign.CENTER),
                    ft.Row([
                        ft.Text(f"{recipient or '　　　　　　　　　'}　御中", size=12, expand=True),
                        ft.Text(f"発行日：{issue_date}", size=10),
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Text(f"PDF {page_count}ページ", size=10, color=ft.Colors.BLUE_GREY_500),
                    ft.Divider(height=4),
                    item_table,
                    ft.Divider(height=4),
                    ft.Row([ft.Container(expand=True), summary_table]),
                    ft.Divider(height=10, color=ft.Colors.GREY_400),
                    ft.Text("領　収　証", size=18, weight=ft.FontWeight.BOLD,
                            text_align=ft.TextAlign.CENTER),
                    ft.Text(f"{recipient or '　　　　　　　　　'}　様", size=11),
                    ft.Text(f"金　¥{total:,} -", size=15, weight=ft.FontWeight.BOLD),
                    ft.Text(f"但し　{receipt_note}", size=10),
                    ft.Row([
                        hanko,
                        ft.Container(expand=True),
                        issuer_block,
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ], spacing=8),
                padding=ft.padding.all(16),
                border=ft.border.all(1, ft.Colors.GREY_300),
                border_radius=8,
                bgcolor=ft.Colors.WHITE,
            )
        ]
        self.preview_column.visible = True

    # ─────────────────────────────────────────────────────────────────
    # PDF出力
    # ─────────────────────────────────────────────────────────────────

    def _extract_items_data(self, fetched: list[tuple[str, dict]]) -> list[tuple[str, str, int]]:
        result = []
        for pid, data in fetched:
            props = data.get("properties", {})
            name_info = props.get("商品名")
            item_name = str(name_info.get("value") or self._selected_items.get(pid, "")) if name_info else self._selected_items.get(pid, "")
            model_info = props.get("型番名")
            model_number = str(model_info.get("value") or "") if model_info else ""
            amount_info = props.get("売上金")
            try:
                amount = int(amount_info.get("value") or 0) if amount_info else 0
            except (TypeError, ValueError):
                amount = 0
            result.append((item_name, model_number, amount))
        return result

    def _export_web(self, issue_date: str, fname: str):
        """Web mode: downloads/に書き出してFletのstatic配信経由でブラウザに開く"""
        # downloads/ ディレクトリ（main.pyと同じ場所）
        downloads_dir = os.path.normpath(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "downloads")
        )
        os.makedirs(downloads_dir, exist_ok=True)

        self.export_status.value = "PDF生成中..."
        self.export_status.color = ft.Colors.BLUE
        self.export_btn.disabled = True
        self.page.update()

        def do():
            try:
                fetched = self._fetch_selected_data()
                items_data = self._extract_items_data(fetched)

                # セッション衝突を避けるためユニークなファイル名を使用
                unique_fname = f"receipt_{uuid.uuid4().hex[:8]}.pdf"
                out_path = os.path.join(downloads_dir, unique_fname)

                generate_invoice_receipt_pdf(
                    out_path,
                    items_data,
                    issue_date,
                    recipient=self._get_recipient(),
                    issuer=self._get_issuer(),
                    receipt_note=self._get_receipt_note(),
                )

                def on_ok():
                    self.export_status.value = f"PDFを開きました（ブラウザで保存してください）: {fname}"
                    self.export_status.color = ft.Colors.GREEN
                    self.export_btn.disabled = False
                    # Fletのassets_dirから配信されるURLで開く
                    self.page.launch_url(f"/{unique_fname}")
                    self.page.update()

                self.page.run_thread(on_ok)
            except Exception as ex:
                err = ex

                def on_err():
                    self.export_status.value = f"エラー: {err}"
                    self.export_status.color = ft.Colors.RED
                    self.export_btn.disabled = False
                    self.page.update()

                self.page.run_thread(on_err)

        threading.Thread(target=do, daemon=True).start()

    def on_export(self, e):
        if not self._selected_items:
            return

        issue_date = self._get_issue_date()
        fname = f"請求書_{self._get_issue_date_filename()}.pdf"

        if getattr(self.page, 'web', False):
            self._export_web(issue_date, fname)
            return

        if platform.system() == "Darwin":
            # Mac: ダイアログなしで ~/Downloads/ に直接保存
            downloads_dir = os.path.expanduser("~/Downloads")
            os.makedirs(downloads_dir, exist_ok=True)
            out_path = os.path.join(downloads_dir, fname)

            self.export_status.value = "PDF生成中..."
            self.export_status.color = ft.Colors.BLUE
            self.export_btn.disabled = True
            self.page.update()

            def do_mac():
                try:
                    fetched = self._fetch_selected_data()
                    items_data = self._extract_items_data(fetched)
                    generate_invoice_receipt_pdf(
                        out_path,
                        items_data,
                        issue_date,
                        recipient=self._get_recipient(),
                        issuer=self._get_issuer(),
                        receipt_note=self._get_receipt_note(),
                    )
                    def on_ok():
                        self.export_status.value = f"保存しました: {out_path}"
                        self.export_status.color = ft.Colors.GREEN
                        self.export_btn.disabled = False
                        self.page.update()
                    self.page.run_thread(on_ok)
                except Exception as ex:
                    err = ex
                    def on_err():
                        self.export_status.value = f"エラー: {str(err)}"
                        self.export_status.color = ft.Colors.RED
                        self.export_btn.disabled = False
                        self.page.update()
                    self.page.run_thread(on_err)

            threading.Thread(target=do_mac, daemon=True).start()
            return

        # Windows / Linux: FilePicker でダイアログ表示
        def save_file(ev: ft.FilePickerResultEvent):
            if not ev.path:
                return
            try:
                fetched = self._fetch_selected_data()
                items_data = self._extract_items_data(fetched)
                generate_invoice_receipt_pdf(
                    ev.path,
                    items_data,
                    issue_date,
                    recipient=self._get_recipient(),
                    issuer=self._get_issuer(),
                    receipt_note=self._get_receipt_note(),
                )
                self._snack(f"保存しました: {ev.path}", ft.Colors.GREEN)
            except Exception as ex:
                self._snack(f"保存エラー: {str(ex)}", ft.Colors.RED)

        file_picker = ft.FilePicker(on_result=save_file)
        self.page.overlay.append(file_picker)
        self.page.update()
        file_picker.save_file(
            dialog_title="請求書・領収証PDFを保存",
            file_name=fname,
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["pdf"],
        )

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
            text="領収書",
            icon=ft.Icons.RECEIPT,
            content=ft.Container(
                padding=ft.padding.all(20),
                content=self.content,
            ),
        )


def create_receipt_tab(proxy, page: ft.Page) -> tuple[ft.Tab, "ReceiptTab"]:
    tab = ReceiptTab(proxy, page)
    return tab.create_tab(), tab
