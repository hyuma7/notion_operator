"""
Excel出力タブコンポーネント
Notionから売却済みデータを取得してExcel出力

データベース情報:
- データベース名: 商品一覧
- データベースID: 1d254e6206d881bb9e88d2e7ffb90444
- 在庫状況プロパティID: qFjR (status型)
- 売却日プロパティID: ep:H (date型)
"""

import flet as ft
import pandas as pd
from datetime import datetime
from notion_client import Client
import os
from io import BytesIO


class ExportTab:
    def __init__(self, proxy, page: ft.Page):
        self.proxy = proxy
        self.page = page
        self.df = None
        self.data_type = None  # 'yearly' または 'monthly'
        self.fetched_year = None
        self.fetched_month = None
        self.pivot_df = None  # ピボット集計用データ
        self.pivot_start_year_value = None  # ピボット集計の開始年
        self.pivot_start_month_value = None  # ピボット集計の開始月

        # 財務集計用の開始年月選択
        self.pivot_start_year = ft.Dropdown(
            label="開始年",
            width=150,
            options=[ft.dropdown.Option(str(y)) for y in range(2020, 2031)],
            value="2025"
        )

        self.pivot_start_month = ft.Dropdown(
            label="開始月",
            width=150,
            options=[ft.dropdown.Option(str(m), f"{m}月") for m in range(1, 13)],
            value="6"
        )

        # ピボット集計用ボタン
        self.fetch_pivot_btn = ft.ElevatedButton(
            "財務集計データを取得",
            icon=ft.Icons.ASSESSMENT,
            on_click=self.fetch_pivot_data
        )

        self.export_pivot_btn = ft.ElevatedButton(
            "財務集計Excelを保存",
            icon=ft.Icons.TABLE_VIEW,
            on_click=self.export_pivot_excel,
            disabled=True
        )

        # 結果表示
        self.result_text = ft.Text("", size=14)
        self.data_table = ft.DataTable(
            columns=[ft.DataColumn(ft.Text("データを取得してください"))],
            rows=[],
            border=ft.border.all(1, ft.Colors.GREY_400),
            border_radius=10,
            vertical_lines=ft.BorderSide(1, ft.Colors.GREY_300),
            horizontal_lines=ft.BorderSide(1, ft.Colors.GREY_300),
        )

        # プログレスバー
        self.progress = ft.ProgressBar(visible=False)

    def fetch_pivot_data(self, e):
        """財務集計データを取得（選択した開始月から12ヶ月分）"""
        api_key = self.proxy.config.get("notion_api_key", "")
        database_id = self.proxy.config.get("notion_database_id", "")

        if not api_key or not database_id:
            self.show_snackbar("設定タブでNotion API KeyとDatabase IDを設定してください", ft.Colors.RED)
            return

        self.progress.visible = True
        self.result_text.value = "財務集計データを取得中..."
        self.page.update()

        try:
            notion = Client(auth=api_key)

            # 選択された開始年月を取得
            start_year = int(self.pivot_start_year.value)
            start_month = int(self.pivot_start_month.value)

            # 開始日と終了日を計算（12ヶ月分）
            start_date = f"{start_year}-{start_month:02d}-01"

            # 12ヶ月後の年月を計算
            end_month = start_month + 12
            end_year = start_year
            if end_month > 12:
                end_year = start_year + 1
                end_month = end_month - 12

            end_date = f"{end_year}-{end_month:02d}-01"

            # 売却済みデータを取得（ページネーション対応）
            all_results = []
            has_more = True
            start_cursor = None

            while has_more:
                query_params = {
                    "database_id": database_id,
                    "filter": {
                        "and": [
                            {
                                "property": "在庫状況",
                                "status": {
                                    "equals": "売却済み"
                                }
                            },
                            {
                                "property": "売却日",
                                "date": {
                                    "on_or_after": start_date
                                }
                            },
                            {
                                "property": "売却日",
                                "date": {
                                    "before": end_date
                                }
                            }
                        ]
                    },
                    "page_size": 100
                }

                if start_cursor:
                    query_params["start_cursor"] = start_cursor

                results = notion.databases.query(**query_params)
                all_results.extend(results["results"])
                has_more = results.get("has_more", False)
                start_cursor = results.get("next_cursor")

            # 全結果を辞書形式に変換
            combined_results = {
                "results": all_results
            }

            # データフレームに変換
            self.pivot_df = self.parse_notion_results(combined_results)

            if not self.pivot_df.empty:
                # 開始年月を保存
                self.pivot_start_year_value = start_year
                self.pivot_start_month_value = start_month

                # 終了年月を計算
                end_year_display = end_year
                end_month_display = end_month - 1
                if end_month_display == 0:
                    end_month_display = 12
                    end_year_display -= 1

                self.result_text.value = f"✅ {start_year}年{start_month}月〜{end_year_display}年{end_month_display}月の{len(self.pivot_df)}件のデータを取得しました"
                self.export_pivot_btn.disabled = False
            else:
                self.result_text.value = "⚠️ 該当期間のデータがありません"
                self.export_pivot_btn.disabled = True

        except Exception as ex:
            self.result_text.value = f"❌ エラー: {str(ex)}"
            self.export_pivot_btn.disabled = True

        self.progress.visible = False
        self.page.update()

    def parse_notion_results(self, results):
        """Notion APIの結果をDataFrameに変換"""
        if not results or "results" not in results:
            return pd.DataFrame()

        data = []
        for page in results["results"]:
            properties = page["properties"]
            row = {}

            for prop_name, prop_value in properties.items():
                prop_type = prop_value["type"]

                if prop_type == "title":
                    row[prop_name] = prop_value["title"][0]["plain_text"] if prop_value["title"] else ""
                elif prop_type == "rich_text":
                    row[prop_name] = prop_value["rich_text"][0]["plain_text"] if prop_value["rich_text"] else ""
                elif prop_type == "number":
                    row[prop_name] = prop_value["number"]
                elif prop_type == "select":
                    row[prop_name] = prop_value["select"]["name"] if prop_value["select"] else ""
                elif prop_type == "status":  # status型の処理
                    row[prop_name] = prop_value["status"]["name"] if prop_value["status"] else ""
                elif prop_type == "multi_select":
                    row[prop_name] = ", ".join([item["name"] for item in prop_value["multi_select"]])
                elif prop_type == "date":
                    row[prop_name] = prop_value["date"]["start"] if prop_value["date"] else ""
                elif prop_type == "checkbox":
                    row[prop_name] = prop_value["checkbox"]
                elif prop_type == "url":
                    row[prop_name] = prop_value["url"] or ""
                elif prop_type == "email":
                    row[prop_name] = prop_value["email"] or ""
                elif prop_type == "phone_number":
                    row[prop_name] = prop_value["phone_number"] or ""
                elif prop_type == "formula":
                    # 数式の結果型に応じて処理
                    formula = prop_value.get("formula", {})
                    if formula.get("type") == "string":
                        row[prop_name] = formula.get("string", "")
                    elif formula.get("type") == "number":
                        row[prop_name] = formula.get("number", 0)
                    else:
                        row[prop_name] = str(formula)
                elif prop_type == "rollup":
                    # ロールアップの結果を処理
                    rollup = prop_value.get("rollup", {})
                    if rollup.get("type") == "array":
                        array_data = rollup.get("array", [])
                        if array_data:
                            row[prop_name] = ", ".join([str(item) for item in array_data])
                        else:
                            row[prop_name] = ""
                    elif rollup.get("type") == "number":
                        row[prop_name] = rollup.get("number", 0)
                    else:
                        row[prop_name] = str(rollup)
                elif prop_type == "relation":
                    # リレーションのIDを取得
                    relations = prop_value.get("relation", [])
                    row[prop_name] = ", ".join([rel["id"] for rel in relations])
                elif prop_type == "people":
                    # ユーザー名を取得
                    people = prop_value.get("people", [])
                    row[prop_name] = ", ".join([person.get("name", "") for person in people])
                elif prop_type == "files":
                    # ファイル名を取得
                    files = prop_value.get("files", [])
                    row[prop_name] = ", ".join([file.get("name", "") for file in files])
                elif prop_type == "unique_id":
                    # ユニークIDを取得
                    unique_id = prop_value.get("unique_id", {})
                    prefix = unique_id.get("prefix", "")
                    number = unique_id.get("number", 0)
                    row[prop_name] = f"{prefix}{number}" if prefix else str(number)
                elif prop_type == "created_time":
                    row[prop_name] = prop_value.get("created_time", "")
                else:
                    row[prop_name] = str(prop_value.get(prop_type, ""))

            data.append(row)

        return pd.DataFrame(data)

    def update_data_table(self):
        """データテーブルを更新"""
        if self.df is None or self.df.empty:
            return

        # 列を作成（最大5列まで表示）
        columns = list(self.df.columns)[:5]
        self.data_table.columns = [ft.DataColumn(ft.Text(col)) for col in columns]

        # 行を作成（最大10行まで表示）
        rows = []
        for _, row in self.df.head(10).iterrows():
            cells = [ft.DataCell(ft.Text(str(row.get(col, ""))[:30])) for col in columns]
            rows.append(ft.DataRow(cells=cells))

        self.data_table.rows = rows

    def create_pivot_sections(self, df, start_year, start_month):
        """5つのセクションのピボットテーブルを作成"""
        from datetime import datetime
        import re

        # 月のリストを生成（選択された開始月から12ヶ月分）
        months = []
        current_year = start_year
        current_month = start_month

        for i in range(12):
            months.append(f"{current_year}年{current_month}月")
            current_month += 1
            if current_month > 12:
                current_month = 1
                current_year += 1

        # データの前処理
        df_clean = df.copy()

        # 売却日から年月を抽出
        def extract_year_month(date_str):
            if pd.isna(date_str) or date_str == "":
                return None
            try:
                # 日付文字列をパース
                date_obj = pd.to_datetime(date_str)
                return f"{date_obj.year}年{date_obj.month}月"
            except:
                return None

        df_clean['売却年月'] = df_clean['売却日'].apply(extract_year_month)

        # 数値フィールドのクリーニング
        def clean_currency(value):
            if pd.isna(value) or value == "":
                return 0
            if isinstance(value, (int, float)):
                return float(value)
            # "￥1,000" のような文字列を数値に変換
            if isinstance(value, str):
                value = value.replace('￥', '').replace(',', '').strip()
                try:
                    return float(value)
                except:
                    return 0
            return 0

        df_clean['売上金_数値'] = df_clean['売上金'].apply(clean_currency)
        df_clean['純利益_数値'] = df_clean['純利益'].apply(clean_currency)
        df_clean['仕入れ原価_数値'] = df_clean['仕入れ原価'].apply(clean_currency)

        # 仕入先と販売媒体のクリーニング（Notion URLを除去）
        def clean_company_name(value):
            if pd.isna(value) or value == "":
                return "不明"
            # URL部分を除去
            if isinstance(value, str) and '(https://' in value:
                value = re.sub(r'\s*\(https://.*?\)', '', value)
            return value.strip()

        df_clean['仕入れ先_clean'] = df_clean['仕入れ先'].apply(clean_company_name)
        df_clean['販売媒体_clean'] = df_clean['販売媒体'].apply(clean_company_name)

        # セクション1: 企業別売上（業販）- 仕入先別の売上金
        pivot1 = df_clean.pivot_table(
            values='売上金_数値',
            index='仕入れ先_clean',
            columns='売却年月',
            aggfunc='sum',
            fill_value=0
        )

        # セクション2: 企業別販売利益（業販）- 仕入先別の純利益
        pivot2 = df_clean.pivot_table(
            values='純利益_数値',
            index='仕入れ先_clean',
            columns='売却年月',
            aggfunc='sum',
            fill_value=0
        )

        # セクション3: 企業別売上（小売）- 販売媒体別の売上金
        pivot3 = df_clean.pivot_table(
            values='売上金_数値',
            index='販売媒体_clean',
            columns='売却年月',
            aggfunc='sum',
            fill_value=0
        )

        # セクション4: 企業別販売利益（小売）- 販売媒体別の純利益
        pivot4 = df_clean.pivot_table(
            values='純利益_数値',
            index='販売媒体_clean',
            columns='売却年月',
            aggfunc='sum',
            fill_value=0
        )

        # セクション5: 企業別仕入高 - 仕入先別の仕入れ原価
        pivot5 = df_clean.pivot_table(
            values='仕入れ原価_数値',
            index='仕入れ先_clean',
            columns='売却年月',
            aggfunc='sum',
            fill_value=0
        )

        # 月の列を正しい順序で並べ替え、存在しない月は0で埋める
        pivot_list = [pivot1, pivot2, pivot3, pivot4, pivot5]
        for i in range(len(pivot_list)):
            pivot = pivot_list[i]
            # すべての月の列を作成（存在しない月は0で埋める）
            for month in months:
                if month not in pivot.columns:
                    pivot[month] = 0
            # 月の順序で並べ替え
            pivot_list[i] = pivot[months]

        return {
            '企業別売上（業販）': pivot_list[0],
            '企業別販売利益（業販）': pivot_list[1],
            '企業別売上（小売）': pivot_list[2],
            '企業別販売利益（小売）': pivot_list[3],
            '企業別仕入高': pivot_list[4]
        }

    def export_pivot_excel(self, e):
        """ピボット形式の財務集計Excelを保存"""
        if self.pivot_df is None or self.pivot_df.empty:
            return

        # 終了年月を計算
        start_year = self.pivot_start_year_value
        start_month = self.pivot_start_month_value
        end_month = start_month + 11
        end_year = start_year
        if end_month > 12:
            end_year = start_year + 1
            end_month = end_month - 12

        file_name = f"財務集計_{start_year}年{start_month}月-{end_year}年{end_month}月.xlsx"

        def save_file(e: ft.FilePickerResultEvent):
            if e.path:
                try:
                    from openpyxl import Workbook
                    from openpyxl.styles import Font, Border, Side, Alignment, PatternFill

                    # ピボットセクションを作成
                    sections = self.create_pivot_sections(
                        self.pivot_df,
                        self.pivot_start_year_value,
                        self.pivot_start_month_value
                    )

                    # Excelワークブックを作成
                    wb = Workbook()
                    ws = wb.active
                    ws.title = "財務集計"

                    current_row = 1

                    # 各セクションを順番に書き込み
                    for section_name, pivot_df in sections.items():
                        # セクションタイトル
                        ws.cell(row=current_row, column=1, value=section_name)
                        ws.cell(row=current_row, column=1).font = Font(bold=True, size=14)
                        current_row += 1

                        # ヘッダー行（月の列）
                        ws.cell(row=current_row, column=1, value="")  # 左上は空欄
                        for col_idx, month in enumerate(pivot_df.columns, start=2):
                            ws.cell(row=current_row, column=col_idx, value=month)
                            ws.cell(row=current_row, column=col_idx).font = Font(bold=True)
                            ws.cell(row=current_row, column=col_idx).alignment = Alignment(horizontal='center')

                        # 「計」列
                        ws.cell(row=current_row, column=len(pivot_df.columns) + 2, value="計")
                        ws.cell(row=current_row, column=len(pivot_df.columns) + 2).font = Font(bold=True)
                        ws.cell(row=current_row, column=len(pivot_df.columns) + 2).alignment = Alignment(horizontal='center')
                        current_row += 1

                        # データ行
                        for company in pivot_df.index:
                            ws.cell(row=current_row, column=1, value=company)
                            row_total = 0
                            for col_idx, month in enumerate(pivot_df.columns, start=2):
                                value = pivot_df.loc[company, month]
                                ws.cell(row=current_row, column=col_idx, value=value)
                                ws.cell(row=current_row, column=col_idx).number_format = '#,##0'
                                row_total += value

                            # 計列
                            ws.cell(row=current_row, column=len(pivot_df.columns) + 2, value=row_total)
                            ws.cell(row=current_row, column=len(pivot_df.columns) + 2).number_format = '#,##0'
                            current_row += 1

                        # 担当者行（空欄）
                        ws.cell(row=current_row, column=1, value="担当者")
                        ws.cell(row=current_row, column=1).font = Font(bold=True)
                        current_row += 1

                        # 合計行
                        ws.cell(row=current_row, column=1, value="合計")
                        ws.cell(row=current_row, column=1).font = Font(bold=True)
                        for col_idx, month in enumerate(pivot_df.columns, start=2):
                            col_total = pivot_df[month].sum()
                            ws.cell(row=current_row, column=col_idx, value=col_total)
                            ws.cell(row=current_row, column=col_idx).number_format = '#,##0'
                            ws.cell(row=current_row, column=col_idx).font = Font(bold=True)

                        # 合計の計列
                        grand_total = pivot_df.values.sum()
                        ws.cell(row=current_row, column=len(pivot_df.columns) + 2, value=grand_total)
                        ws.cell(row=current_row, column=len(pivot_df.columns) + 2).number_format = '#,##0'
                        ws.cell(row=current_row, column=len(pivot_df.columns) + 2).font = Font(bold=True)
                        current_row += 2  # セクション間に空行

                    # 列幅調整
                    ws.column_dimensions['A'].width = 20
                    # 最初のセクションの列数を取得
                    num_cols = len(sections[list(sections.keys())[0]].columns) + 2
                    for col_idx in range(2, num_cols + 1):
                        # A=1, B=2, ... Z=26, AA=27, AB=28, ...
                        if col_idx <= 26:
                            col_letter = chr(64 + col_idx)
                        else:
                            first_letter = chr(64 + (col_idx - 1) // 26)
                            second_letter = chr(65 + (col_idx - 1) % 26)
                            col_letter = first_letter + second_letter
                        ws.column_dimensions[col_letter].width = 12

                    # 保存
                    wb.save(e.path)
                    self.show_snackbar(f"保存しました: {e.path}", ft.Colors.GREEN)

                except Exception as ex:
                    import traceback
                    error_detail = traceback.format_exc()
                    self.show_snackbar(f"保存エラー: {str(ex)}", ft.Colors.RED)
                    print(error_detail)  # デバッグ用

        file_picker = ft.FilePicker(on_result=save_file)
        self.page.overlay.append(file_picker)
        self.page.update()

        file_picker.save_file(
            dialog_title="財務集計Excelを保存",
            file_name=file_name,
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["xlsx"]
        )

    def show_snackbar(self, message: str, color):
        """スナックバーを表示"""
        snack = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=color
        )
        self.page.snack_bar = snack
        self.page.snack_bar.open = True
        self.page.update()

    def create_tab(self) -> ft.Tab:
        """タブを作成"""
        return ft.Tab(
            text="Excel出力",
            icon=ft.Icons.TABLE_CHART,
            content=ft.Container(
                padding=ft.padding.all(20),
                content=ft.Column([
                    # 期間選択カード
                    ft.Card(
                        content=ft.Container(
                            padding=ft.padding.all(20),
                            content=ft.Column([
                                ft.Text("財務集計期間選択", size=18, weight=ft.FontWeight.BOLD),
                                ft.Divider(),
                                ft.Text("開始年月（12ヶ月分を集計）", size=14, weight=ft.FontWeight.BOLD),
                                ft.Row([
                                    self.pivot_start_year,
                                    self.pivot_start_month,
                                ]),
                                ft.Text("※「在庫状況」が「売却済み」のデータのみ取得します",
                                       size=12, color=ft.Colors.GREY_600),
                            ])
                        )
                    ),
                    # 操作ボタン
                    ft.Row([
                        self.fetch_pivot_btn,
                        self.export_pivot_btn,
                    ]),
                    self.progress,
                    self.result_text,
                    # データプレビュー
                    ft.Card(
                        content=ft.Container(
                            padding=ft.padding.all(20),
                            content=ft.Column([
                                ft.Text("データプレビュー", size=18, weight=ft.FontWeight.BOLD),
                                ft.Divider(),
                                ft.Container(
                                    content=self.data_table,
                                    height=300,
                                )
                            ])
                        )
                    ),
                ], scroll=ft.ScrollMode.AUTO)
            )
        )


def create_export_tab(proxy, page: ft.Page) -> tuple[ft.Tab, ExportTab]:
    """Excel出力タブを作成して返す"""
    export_tab = ExportTab(proxy, page)
    return export_tab.create_tab(), export_tab
