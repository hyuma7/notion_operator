"""
Excel出力タブコンポーネント
Notionから売却済みデータを取得してExcel出力
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

        # Notion設定
        self.api_key_field = ft.TextField(
            label="Notion API Key",
            password=True,
            width=400,
            value=os.getenv("NOTION_API_KEY", "")
        )

        self.database_id_field = ft.TextField(
            label="Database ID",
            width=400,
            value=os.getenv("NOTION_DATABASE_ID", "")
        )

        # 年選択
        current_year = datetime.now().year
        self.year_dropdown = ft.Dropdown(
            label="年",
            width=150,
            options=[ft.dropdown.Option(str(y)) for y in range(2020, 2031)],
            value=str(current_year)
        )

        # 月選択
        self.month_dropdown = ft.Dropdown(
            label="月",
            width=150,
            options=[ft.dropdown.Option(str(m), f"{m}月") for m in range(1, 13)],
            value=str(datetime.now().month)
        )

        # ボタン
        self.fetch_btn = ft.ElevatedButton(
            "データを取得",
            icon=ft.Icons.DOWNLOAD,
            on_click=self.fetch_data
        )

        self.export_btn = ft.ElevatedButton(
            "Excelファイルを保存",
            icon=ft.Icons.SAVE_ALT,
            on_click=self.export_excel,
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

    def fetch_data(self, e):
        """Notionからデータを取得"""
        api_key = self.api_key_field.value
        database_id = self.database_id_field.value

        if not api_key or not database_id:
            self.show_snackbar("API KeyとDatabase IDを入力してください", ft.Colors.RED)
            return

        self.progress.visible = True
        self.result_text.value = "データを取得中..."
        self.page.update()

        try:
            notion = Client(auth=api_key)
            year = int(self.year_dropdown.value)
            month = int(self.month_dropdown.value)

            # 期間計算
            start_date = f"{year}-{month:02d}-01"
            if month == 12:
                end_date = f"{year + 1}-01-01"
            else:
                end_date = f"{year}-{month + 1:02d}-01"

            # Notion APIクエリ
            results = notion.databases.query(
                database_id=database_id,
                filter={
                    "and": [
                        {
                            "property": "在庫状態",
                            "select": {
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
                }
            )

            # データフレームに変換
            self.df = self.parse_notion_results(results)

            if not self.df.empty:
                self.result_text.value = f"✅ {len(self.df)}件のデータを取得しました"
                self.update_data_table()
                self.export_btn.disabled = False
            else:
                self.result_text.value = "⚠️ 該当するデータがありません"
                self.export_btn.disabled = True

        except Exception as ex:
            self.result_text.value = f"❌ エラー: {str(ex)}"
            self.export_btn.disabled = True

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

    def export_excel(self, e):
        """Excelファイルを保存"""
        if self.df is None or self.df.empty:
            return

        year = self.year_dropdown.value
        month = self.month_dropdown.value

        # ファイル保存ダイアログ
        def save_file(e: ft.FilePickerResultEvent):
            if e.path:
                try:
                    with pd.ExcelWriter(e.path, engine='openpyxl') as writer:
                        self.df.to_excel(writer, index=False, sheet_name='売却済み物件')

                        # 列幅調整
                        worksheet = writer.sheets['売却済み物件']
                        for idx, col in enumerate(self.df.columns):
                            max_length = max(
                                self.df[col].astype(str).apply(len).max(),
                                len(str(col))
                            )
                            worksheet.column_dimensions[chr(65 + idx)].width = min(max_length + 2, 50)

                    self.show_snackbar(f"保存しました: {e.path}", ft.Colors.GREEN)
                except Exception as ex:
                    self.show_snackbar(f"保存エラー: {str(ex)}", ft.Colors.RED)

        file_picker = ft.FilePicker(on_result=save_file)
        self.page.overlay.append(file_picker)
        self.page.update()

        file_picker.save_file(
            dialog_title="Excelファイルを保存",
            file_name=f"flat_sold_{year}年{month}月.xlsx",
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
                    # Notion設定カード
                    ft.Card(
                        content=ft.Container(
                            padding=ft.padding.all(20),
                            content=ft.Column([
                                ft.Text("Notion設定", size=18, weight=ft.FontWeight.BOLD),
                                ft.Divider(),
                                self.api_key_field,
                                self.database_id_field,
                            ])
                        )
                    ),
                    # 期間選択カード
                    ft.Card(
                        content=ft.Container(
                            padding=ft.padding.all(20),
                            content=ft.Column([
                                ft.Text("期間選択", size=18, weight=ft.FontWeight.BOLD),
                                ft.Divider(),
                                ft.Row([
                                    self.year_dropdown,
                                    self.month_dropdown,
                                ]),
                                ft.Text("※「在庫状態」が「売却済み」のデータのみ取得します",
                                       size=12, color=ft.Colors.GREY_600),
                            ])
                        )
                    ),
                    # 操作ボタン
                    ft.Row([
                        self.fetch_btn,
                        self.export_btn,
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
