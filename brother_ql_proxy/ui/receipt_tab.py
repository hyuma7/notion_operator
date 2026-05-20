"""
領収書タブ
- Notionから直近10件取得 or 商品名/IDで検索
- 選択した商品の領収書プレビューを表示
- Excel形式で領収書を出力
"""

import os
import threading
from datetime import date, datetime
import flet as ft

from notion.fetch_page import fetch_recent_items, search_items, fetch_all_properties


def _fmt_currency(value) -> str:
    """数値を ¥X,XXX 形式にフォーマット"""
    try:
        n = int(value)
        return f"¥{n:,}"
    except (TypeError, ValueError):
        return "¥0"


def _generate_receipt_excel(path: str, item_name: str, amount: int, issue_date: str):
    """openpyxl で領収書Excelを生成する"""
    from openpyxl import Workbook
    from openpyxl.styles import (
        Font, Alignment, Border, Side, PatternFill, numbers
    )
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "領収書"

    # 列幅設定
    ws.column_dimensions["A"].width = 8
    ws.column_dimensions["B"].width = 30
    ws.column_dimensions["C"].width = 10
    ws.column_dimensions["D"].width = 15
    ws.column_dimensions["E"].width = 12

    # 行高設定
    ws.row_dimensions[1].height = 40
    ws.row_dimensions[2].height = 20
    ws.row_dimensions[4].height = 22
    ws.row_dimensions[5].height = 22
    ws.row_dimensions[8].height = 20
    ws.row_dimensions[9].height = 20
    ws.row_dimensions[10].height = 24

    # ── スタイル定義 ─────────────────────────────────────────────
    thin = Side(style="thin")
    medium = Side(style="medium")
    thick = Side(style="thick")

    header_border = Border(
        left=thin, right=thin, top=thin, bottom=thin
    )
    data_border = Border(
        left=thin, right=thin, top=thin, bottom=thin
    )
    total_border = Border(
        left=thin, right=thin, top=thin, bottom=medium
    )
    hanko_border = Border(
        left=thick, right=thick, top=thick, bottom=thick
    )

    # ── Row 1: 領収書タイトル ──────────────────────────────────────
    ws.merge_cells("A1:D1")
    title_cell = ws["A1"]
    title_cell.value = "領　収　書"
    title_cell.font = Font(name="MS Gothic", size=24, bold=True)
    title_cell.alignment = Alignment(horizontal="center", vertical="center")

    # ── Row 2: 発行日 ─────────────────────────────────────────────
    ws.merge_cells("A2:D2")
    date_cell = ws["A2"]
    date_cell.value = f"発行日: {issue_date}"
    date_cell.font = Font(name="MS Gothic", size=11)
    date_cell.alignment = Alignment(horizontal="right", vertical="center")

    # ── Row 3: 空白 ───────────────────────────────────────────────

    # ── Row 4: テーブルヘッダー ────────────────────────────────────
    headers = [("A4", "No."), ("B4", "品名"), ("C4", "数量"), ("D4", "金額")]
    for cell_ref, label in headers:
        cell = ws[cell_ref]
        cell.value = label
        cell.font = Font(name="MS Gothic", size=11, bold=True)
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = header_border
        cell.fill = PatternFill(fill_type="solid", fgColor="D9D9D9")

    # ── Row 5: 商品データ ──────────────────────────────────────────
    ws["A5"].value = 1
    ws["A5"].alignment = Alignment(horizontal="center", vertical="center")
    ws["A5"].border = data_border
    ws["A5"].font = Font(name="MS Gothic", size=11)

    ws["B5"].value = item_name
    ws["B5"].alignment = Alignment(horizontal="left", vertical="center")
    ws["B5"].border = data_border
    ws["B5"].font = Font(name="MS Gothic", size=11)

    ws["C5"].value = 1
    ws["C5"].alignment = Alignment(horizontal="center", vertical="center")
    ws["C5"].border = data_border
    ws["C5"].font = Font(name="MS Gothic", size=11)

    ws["D5"].value = amount
    ws["D5"].alignment = Alignment(horizontal="right", vertical="center")
    ws["D5"].border = data_border
    ws["D5"].font = Font(name="MS Gothic", size=11)
    ws["D5"].number_format = '"¥"#,##0'

    # ── Row 6-7: 空白 ─────────────────────────────────────────────

    # ── Row 8-10: 合計ブロック ─────────────────────────────────────
    subtotal = amount
    tax = int(subtotal * 0.1)
    total = subtotal + tax

    summary_rows = [
        (8, "小計", subtotal, False),
        (9, "消費税(10%)", tax, False),
        (10, "合計", total, True),
    ]
    for row_num, label, value, is_bold in summary_rows:
        label_cell = ws.cell(row=row_num, column=3)
        label_cell.value = label
        label_cell.font = Font(name="MS Gothic", size=11, bold=is_bold)
        label_cell.alignment = Alignment(horizontal="right", vertical="center")
        label_cell.border = total_border if is_bold else header_border

        value_cell = ws.cell(row=row_num, column=4)
        value_cell.value = value
        value_cell.font = Font(name="MS Gothic", size=12 if is_bold else 11, bold=is_bold)
        value_cell.alignment = Alignment(horizontal="right", vertical="center")
        value_cell.border = total_border if is_bold else header_border
        value_cell.number_format = '"¥"#,##0'

    # ── Row 11: 空白 ──────────────────────────────────────────────

    # ── Row 12-14: 署名・ハンコ ────────────────────────────────────
    ws.row_dimensions[12].height = 22
    ws.row_dimensions[13].height = 22
    ws.row_dimensions[14].height = 22

    ws["A12"].value = "株式会社アーネスト"
    ws["A12"].font = Font(name="MS Gothic", size=11)
    ws["A12"].alignment = Alignment(horizontal="left", vertical="center")

    ws["A13"].value = "代表取締役  斉藤 潤"
    ws["A13"].font = Font(name="MS Gothic", size=11)
    ws["A13"].alignment = Alignment(horizontal="left", vertical="center")

    # ハンコセル (D12:E14) をマージして印鑑風に表示
    ws.merge_cells("D12:E14")
    hanko_cell = ws["D12"]
    hanko_cell.value = "株式会社アーネスト\n代表取締役\n斉藤 潤"
    hanko_cell.font = Font(name="MS Gothic", size=10, bold=True, color="8B0000")
    hanko_cell.alignment = Alignment(
        horizontal="center", vertical="center", wrap_text=True
    )
    hanko_cell.border = hanko_border
    # 薄いピンク/赤みがかった背景（印鑑の朱色イメージ）
    hanko_cell.fill = PatternFill(fill_type="solid", fgColor="FFE4E1")

    wb.save(path)


class ReceiptTab:
    def __init__(self, proxy, page: ft.Page):
        self.proxy = proxy
        self.page = page
        self._page_data = None
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

        # ── 選択商品 ───────────────────────────────────────────────
        self.selected_label = ft.Text(
            "商品が選択されていません",
            size=13,
            color=ft.Colors.GREY_600,
            italic=True,
        )

        # ── 領収書プレビュー ───────────────────────────────────────
        self.preview_column = ft.Column(controls=[], spacing=4, visible=False)

        # ── Excel出力ボタン ────────────────────────────────────────
        self.export_btn = ft.ElevatedButton(
            "Excel出力",
            icon=ft.Icons.TABLE_VIEW,
            on_click=self.on_export,
            bgcolor=ft.Colors.GREEN_700,
            color=ft.Colors.WHITE,
            disabled=True,
        )
        self.export_status = ft.Text("", size=13)

        # ── レイアウト ───────────────────────────────────────────────
        self.content = ft.Column(
            controls=[
                ft.Text("領収書", size=18, weight=ft.FontWeight.BOLD),
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

                # 選択商品
                self.selected_label,
                ft.Divider(height=6),

                # 領収書プレビュー
                self.preview_column,

                # Excel出力
                ft.Row([self.export_btn, self.export_status],
                       spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
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
    # 商品選択・プレビュー
    # ─────────────────────────────────────────────────────────────────

    def _select(self, page_id: str, title: str):
        if self._is_loading:
            return
        self._is_loading = True
        self.selected_label.value = f"取得中: {title}..."
        self.selected_label.color = ft.Colors.BLUE
        self.selected_label.italic = False
        self.preview_column.visible = False
        self.preview_column.controls.clear()
        self.export_btn.disabled = True
        self.export_status.value = ""
        self.page.update()

        def do():
            try:
                data = fetch_all_properties(page_id)
                self._page_data = data

                def on_ok():
                    self._render_preview(data, title)
                    self.selected_label.value = f"選択中: {title}"
                    self.selected_label.color = ft.Colors.GREEN_800
                    self.selected_label.italic = False
                    self.export_btn.disabled = False
                    self.page.update()

                self.page.run_thread(on_ok)
            except Exception as ex:
                err = ex

                def on_err():
                    self.selected_label.value = f"エラー: {err}"
                    self.selected_label.color = ft.Colors.RED
                    self.page.update()

                self.page.run_thread(on_err)
            finally:
                def on_fin():
                    self._is_loading = False
                    self.page.update()

                self.page.run_thread(on_fin)

        threading.Thread(target=do, daemon=True).start()

    def _render_preview(self, data: dict, title: str):
        """領収書プレビューをUIに描画する"""
        props = data.get("properties", {})

        # 商品名・金額を取得
        name_info = props.get("商品名")
        item_name = name_info.get("value") if name_info else None
        if not item_name:
            item_name = title

        amount_info = props.get("売上金")
        amount_raw = amount_info.get("value") if amount_info else None
        try:
            amount = int(amount_raw) if amount_raw is not None else 0
        except (TypeError, ValueError):
            amount = 0

        subtotal = amount
        tax = int(subtotal * 0.1)
        total = subtotal + tax

        today_str = date.today().strftime("%Y年%m月%d日")

        # ── プレビュー構築 ─────────────────────────────────────────
        header_style = ft.TextStyle(size=11, weight=ft.FontWeight.BOLD)

        def cell(text, bold=False, right=False, width=None):
            return ft.DataCell(
                ft.Text(
                    text,
                    size=11,
                    weight=ft.FontWeight.BOLD if bold else ft.FontWeight.NORMAL,
                    text_align=ft.TextAlign.RIGHT if right else ft.TextAlign.LEFT,
                )
            )

        item_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("No.", style=header_style)),
                ft.DataColumn(ft.Text("品名", style=header_style)),
                ft.DataColumn(ft.Text("数量", style=header_style), numeric=True),
                ft.DataColumn(ft.Text("金額", style=header_style), numeric=True),
            ],
            rows=[
                ft.DataRow(cells=[
                    cell("1"),
                    cell(str(item_name)),
                    cell("1", right=True),
                    cell(_fmt_currency(amount), right=True),
                ]),
            ],
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

        hanko_cell = ft.Container(
            content=ft.Text(
                "株式会社アーネスト\n代表取締役\n斉藤 潤",
                size=10,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.RED_900,
                text_align=ft.TextAlign.CENTER,
            ),
            width=110,
            height=80,
            border=ft.border.all(3, ft.Colors.RED_900),
            border_radius=4,
            bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.RED_200),
            alignment=ft.alignment.center,
            padding=ft.padding.all(6),
        )

        self.preview_column.controls = [
            ft.Container(
                content=ft.Column([
                    ft.Text("領　収　書", size=22, weight=ft.FontWeight.BOLD,
                            text_align=ft.TextAlign.CENTER),
                    ft.Text(f"発行日: {today_str}", size=11,
                            text_align=ft.TextAlign.RIGHT),
                    ft.Divider(height=4),
                    item_table,
                    ft.Divider(height=4),
                    ft.Row([
                        ft.Container(expand=True),
                        summary_table,
                    ]),
                    ft.Divider(height=8),
                    ft.Row([
                        ft.Column([
                            ft.Text("株式会社アーネスト", size=11),
                            ft.Text("代表取締役  斉藤 潤", size=11),
                        ], spacing=2),
                        ft.Container(expand=True),
                        hanko_cell,
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
    # Excel出力
    # ─────────────────────────────────────────────────────────────────

    def on_export(self, e):
        if not self._page_data:
            return

        props = self._page_data.get("properties", {})
        name_info = props.get("商品名")
        item_name = str(name_info.get("value") or "") if name_info else ""
        amount_info = props.get("売上金")
        amount_raw = amount_info.get("value") if amount_info else None
        try:
            amount = int(amount_raw) if amount_raw is not None else 0
        except (TypeError, ValueError):
            amount = 0

        today_str = date.today().strftime("%Y年%m月%d日")
        fname = f"領収書_{item_name}_{date.today().strftime('%Y%m%d')}.xlsx"

        def save_file(ev: ft.FilePickerResultEvent):
            if ev.path:
                try:
                    _generate_receipt_excel(ev.path, item_name, amount, today_str)

                    def on_ok():
                        self.export_status.value = f"保存しました: {ev.path}"
                        self.export_status.color = ft.Colors.GREEN
                        self.page.update()

                    self.page.run_thread(on_ok)
                except Exception as ex:
                    err = ex

                    def on_err():
                        self.export_status.value = f"エラー: {err}"
                        self.export_status.color = ft.Colors.RED
                        self.page.update()

                    self.page.run_thread(on_err)

        file_picker = ft.FilePicker(on_result=save_file)
        self.page.overlay.append(file_picker)
        self.page.update()
        file_picker.save_file(
            dialog_title="領収書Excelを保存",
            file_name=fname,
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["xlsx"],
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
