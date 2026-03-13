import flet as ft
from datetime import datetime, date
from .service import ExportService, FetchCancelled
import traceback
import threading

class ExportTab:
    def __init__(self, proxy, page: ft.Page):
        self.proxy = proxy
        self.page = page
        self.service = None
        
        # Init service if config available
        self._init_service()

        # State
        today = datetime.now()
        self.pivot_start_date = datetime(2025, 6, 1) # Default
        self.daily_start_date = today
        self.daily_end_date = today
        
        # Data cache
        self.pivot_data_cache = {}
        self.daily_sales_cache = []
        self.daily_purchases_cache = []

        # UI Components
        self._build_ui()

    def _init_service(self):
        api_key = self.proxy.config.get("notion_api_key", "")
        database_id = self.proxy.config.get("notion_database_id", "")
        if api_key and database_id:
            self.service = ExportService(api_key, database_id)

    def _build_ui(self):
        # --- Pivot Section Controls ---
        self.pivot_date_picker = ft.DatePicker(
            value=self.pivot_start_date,
            first_date=datetime(2020, 1, 1),
            last_date=datetime(2030, 12, 31),
            on_change=self.on_pivot_date_change,
        )
        
        self.pivot_date_button = ft.ElevatedButton(
            text=f"開始月: {self.pivot_start_date.year}年{self.pivot_start_date.month}月",
            icon=ft.Icons.CALENDAR_MONTH,
            on_click=lambda _: self.page.open(self.pivot_date_picker)
        )

        self.fetch_pivot_btn = ft.ElevatedButton(
            "財務集計データを取得",
            icon=ft.Icons.ASSESSMENT,
            on_click=self.fetch_pivot_data
        )

        self.export_pivot_btn = ft.Button( # Was ElevatedButton
            text="財務集計Excelを保存",
            icon=ft.Icons.TABLE_VIEW,
            on_click=self.export_pivot_excel,
            disabled=True
        )

        self.pivot_result_text = ft.Text("", size=14)

        # --- Daily Section Controls ---
        self.daily_start_picker = ft.DatePicker(
            value=self.daily_start_date,
            first_date=datetime(2020, 1, 1),
            last_date=datetime(2030, 12, 31),
            on_change=self.on_daily_start_change,
        )
        self.daily_end_picker = ft.DatePicker(
            value=self.daily_end_date,
            first_date=datetime(2020, 1, 1),
            last_date=datetime(2030, 12, 31),
            on_change=self.on_daily_end_change,
        )

        self.daily_start_btn = ft.ElevatedButton(
            text=f"開始日: {self.daily_start_date.strftime('%Y-%m-%d')}",
            icon=ft.Icons.CALENDAR_TODAY,
            on_click=lambda _: self.page.open(self.daily_start_picker)
        )
        self.daily_end_btn = ft.ElevatedButton(
            text=f"終了日: {self.daily_end_date.strftime('%Y-%m-%d')}",
            icon=ft.Icons.CALENDAR_TODAY,
            on_click=lambda _: self.page.open(self.daily_end_picker)
        )

        self.fetch_daily_btn = ft.ElevatedButton(
            "日別売上データを取得",
            icon=ft.Icons.CALENDAR_TODAY,
            on_click=self.fetch_daily_data
        )

        self.export_daily_btn = ft.Button(
            text="日別売上Excelを保存",
            icon=ft.Icons.TABLE_CHART,
            on_click=self.export_daily_excel,
            disabled=True
        )
        self.daily_result_text = ft.Text("", size=14)

        # Progress (詳細な進捗表示)
        self.progress_bar = ft.ProgressBar(visible=False, width=400)
        self.progress_text = ft.Text("", size=12, visible=False)
        self.cancel_btn = ft.ElevatedButton(
            "キャンセル",
            icon=ft.Icons.CANCEL,
            on_click=self.on_cancel_fetch,
            visible=False,
            bgcolor=ft.Colors.RED_400,
            color=ft.Colors.WHITE
        )
        self.progress_container = ft.Row(
            controls=[
                ft.Column([
                    self.progress_bar,
                    self.progress_text,
                ], spacing=5),
                self.cancel_btn
            ],
            visible=False,
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=20
        )

        # フェッチ中フラグ
        self._is_fetching = False

        # Layout
        self.content = ft.Column(
            controls=[
                ft.Text("Excel出力 / 財務集計", size=20, weight=ft.FontWeight.BOLD),
                ft.Divider(),
                
                ft.Text("財務集計 (12ヶ月分)", size=16, weight=ft.FontWeight.BOLD),
                ft.Row([self.pivot_date_button, self.fetch_pivot_btn, self.export_pivot_btn]),
                self.pivot_result_text,
                ft.Divider(),

                ft.Text("日別売上集計", size=16, weight=ft.FontWeight.BOLD),
                ft.Row([ ft.Text("期間:"), self.daily_start_btn, ft.Text("〜"), self.daily_end_btn]),
                ft.Row([self.fetch_daily_btn, self.export_daily_btn]),
                self.daily_result_text,
                
                ft.Divider(),
                self.progress_container
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=20
        )

    def get_content(self):
        return self.content

    def create_tab(self) -> ft.Tab:
        """タブを作成"""
        return ft.Tab(
            text="Excel出力",
            icon=ft.Icons.TABLE_CHART,
            content=ft.Container(
                padding=ft.padding.all(20),
                content=self.content
            )
        )

    # --- Event Handlers ---

    def on_pivot_date_change(self, e):
        if e.control.value:
            self.pivot_start_date = e.control.value
            self.pivot_date_button.text = f"開始月: {self.pivot_start_date.year}年{self.pivot_start_date.month}月"
            self.page.update()

    def on_daily_start_change(self, e):
        if e.control.value:
            self.daily_start_date = e.control.value
            self.daily_start_btn.text = f"開始日: {self.daily_start_date.strftime('%Y-%m-%d')}"
            self.page.update()

    def on_daily_end_change(self, e):
        if e.control.value:
            self.daily_end_date = e.control.value
            self.daily_end_btn.text = f"終了日: {self.daily_end_date.strftime('%Y-%m-%d')}"
            self.page.update()

    def show_snackbar(self, message: str, color):
        snack = ft.SnackBar(content=ft.Text(message), bgcolor=color)
        self.page.snack_bar = snack
        self.page.snack_bar.open = True
        self.page.update()

    def on_cancel_fetch(self, e):
        """キャンセルボタンがクリックされた"""
        if self.service and self._is_fetching:
            self.service.cancel()
            self.cancel_btn.disabled = True
            self.cancel_btn.text = "キャンセル中..."
            self.page.update()

    def _show_progress(self, show: bool):
        """進捗表示の表示/非表示を切り替え"""
        self.progress_container.visible = show
        self.progress_bar.visible = show
        self.progress_text.visible = show
        self.cancel_btn.visible = show
        self.cancel_btn.disabled = False
        self.cancel_btn.text = "キャンセル"
        if show:
            self.progress_bar.value = None  # インデターミネートモード
        self.page.update()

    def _update_progress(self, current: int, total: int, message: str):
        """進捗を更新（コールバック用）"""
        def update():
            self.progress_text.value = message
            if total > 0:
                self.progress_bar.value = current / total
            else:
                self.progress_bar.value = None  # インデターミネート
            self.page.update()
        # メインスレッドで更新
        self.page.run_thread(update)

    # --- Actions ---

    def fetch_pivot_data(self, e):
        self._init_service()
        if not self.service:
            self.show_snackbar("設定タブでNotion API Keyを設定してください", ft.Colors.RED)
            return

        if self._is_fetching:
            self.show_snackbar("データ取得中です", ft.Colors.ORANGE)
            return

        self._is_fetching = True
        self._show_progress(True)
        self.pivot_result_text.value = "データを取得中..."
        self.export_pivot_btn.disabled = True
        self.fetch_pivot_btn.disabled = True
        self.page.update()

        # 進捗コールバックを設定
        self.service.set_progress_callback(self._update_progress)
        self.service.reset_cancel()

        def do_fetch():
            try:
                start_year = self.pivot_start_date.year
                start_month = self.pivot_start_date.month

                # Logic to calculate date range for query (1 year)
                start_date_str = f"{start_year}-{start_month:02d}-01"

                # End date: start + 12 months
                end_year = start_year + 1
                end_month = start_month
                end_date_str = f"{end_year}-{end_month:02d}-01"

                # Fetch
                sales = self.service.fetch_sales_data(start_date_str, end_date_str)
                purchases = self.service.fetch_purchase_data(start_date_str, end_date_str)

                # Generate months list for processing
                months = []
                cur_y, cur_m = start_year, start_month
                for _ in range(12):
                    months.append(f"{cur_y}年{cur_m}月")
                    cur_m += 1
                    if cur_m > 12:
                        cur_m = 1
                        cur_y += 1

                # Process
                self.pivot_data_cache = self.service.process_pivot_data(sales, purchases, months)
                self.pivot_data_cache['months'] = months  # Store for export
                self.pivot_data_cache['display_range'] = f"{start_year}年{start_month}月〜{end_year if end_month==1 else end_year}年{12 if end_month==1 else end_month-1}月"

                count = len(sales)

                def on_success():
                    self.pivot_result_text.value = f"✅ {self.pivot_data_cache['display_range']}の売上{count}件、仕入{len(purchases)}件を取得しました"
                    self.export_pivot_btn.disabled = False
                self.page.run_thread(on_success)

            except FetchCancelled:
                def on_cancelled():
                    self.pivot_result_text.value = "⚠️ キャンセルされました"
                    self.export_pivot_btn.disabled = True
                self.page.run_thread(on_cancelled)

            except Exception as ex:
                err = ex
                traceback.print_exc()
                def on_error():
                    self.pivot_result_text.value = f"❌ エラー: {str(err)}"
                    self.export_pivot_btn.disabled = True
                self.page.run_thread(on_error)

            finally:
                def on_finish():
                    self._is_fetching = False
                    self._show_progress(False)
                    self.fetch_pivot_btn.disabled = False
                    self.service.set_progress_callback(None)
                    self.page.update()
                self.page.run_thread(on_finish)

        # バックグラウンドスレッドで実行
        thread = threading.Thread(target=do_fetch, daemon=True)
        thread.start()

    def export_pivot_excel(self, e):
        if not self.pivot_data_cache:
            return

        def save_file(e: ft.FilePickerResultEvent):
            if e.path:
                try:
                    self.service.generate_excel(e.path, self.pivot_data_cache, self.pivot_data_cache['months'])
                    self.show_snackbar(f"保存しました: {e.path}", ft.Colors.GREEN)
                except Exception as ex:
                    self.show_snackbar(f"保存エラー: {str(ex)}", ft.Colors.RED)

        file_picker = ft.FilePicker(on_result=save_file)
        self.page.overlay.append(file_picker)
        self.page.update()

        # Filename
        fname = f"財務集計_{self.pivot_data_cache.get('display_range', 'data')}.xlsx".replace("〜", "-")
        file_picker.save_file(
            dialog_title="財務集計Excelを保存",
            file_name=fname,
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["xlsx"]
        )

    def fetch_daily_data(self, e):
        self._init_service()
        if not self.service:
            self.show_snackbar("設定タブでNotion API Keyを設定してください", ft.Colors.RED)
            return

        if self.daily_start_date > self.daily_end_date:
            self.show_snackbar("開始日は終了日より前である必要があります", ft.Colors.RED)
            return

        if self._is_fetching:
            self.show_snackbar("データ取得中です", ft.Colors.ORANGE)
            return

        self._is_fetching = True
        self._show_progress(True)
        self.daily_result_text.value = "日別データを取得中..."
        self.export_daily_btn.disabled = True
        self.fetch_daily_btn.disabled = True
        self.page.update()

        # 進捗コールバックを設定
        self.service.set_progress_callback(self._update_progress)
        self.service.reset_cancel()

        def do_fetch():
            try:
                s_str = self.daily_start_date.strftime("%Y-%m-%d")
                # End date for Notion query (exclusive) -> add 1 day
                from datetime import timedelta
                e_plus = self.daily_end_date + timedelta(days=1)
                e_str = e_plus.strftime("%Y-%m-%d")

                sales = self.service.fetch_daily_sales_data(s_str, e_str)
                self.daily_sales_cache = sales

                purchases = self.service.fetch_daily_purchase_data(s_str, e_str)
                self.daily_purchases_cache = purchases

                def on_success():
                    if sales or purchases:
                        self.daily_result_text.value = (
                            f"✅ 売上 {len(sales)}件 / 仕入れ {len(purchases)}件 を取得しました"
                        )
                        self.export_daily_btn.disabled = False
                    else:
                        self.daily_result_text.value = "⚠️ 該当期間のデータがありません"
                        self.export_daily_btn.disabled = True
                self.page.run_thread(on_success)

            except FetchCancelled:
                def on_cancelled():
                    self.daily_result_text.value = "⚠️ キャンセルされました"
                    self.export_daily_btn.disabled = True
                self.page.run_thread(on_cancelled)

            except Exception as ex:
                err = ex
                traceback.print_exc()
                def on_error():
                    self.daily_result_text.value = f"❌ エラー: {str(err)}"
                    self.export_daily_btn.disabled = True
                self.page.run_thread(on_error)

            finally:
                def on_finish():
                    self._is_fetching = False
                    self._show_progress(False)
                    self.fetch_daily_btn.disabled = False
                    self.service.set_progress_callback(None)
                    self.page.update()
                self.page.run_thread(on_finish)

        # バックグラウンドスレッドで実行
        thread = threading.Thread(target=do_fetch, daemon=True)
        thread.start()

    def export_daily_excel(self, e):
        if not self.daily_sales_cache and not self.daily_purchases_cache:
            return

        def save_file(e: ft.FilePickerResultEvent):
            if e.path:
                try:
                    self.service.generate_daily_excel(
                        e.path, self.daily_sales_cache, self.daily_purchases_cache
                    )
                    self.show_snackbar(f"保存しました: {e.path}", ft.Colors.GREEN)
                except Exception as ex:
                    self.show_snackbar(f"保存エラー: {str(ex)}", ft.Colors.RED)

        file_picker = ft.FilePicker(on_result=save_file)
        self.page.overlay.append(file_picker)
        self.page.update()
        
        s_name = self.daily_start_date.strftime("%Y-%m-%d")
        e_name = self.daily_end_date.strftime("%Y-%m-%d")
        fname = f"日別売上_{s_name}_{e_name}.xlsx" if s_name != e_name else f"日別売上_{s_name}.xlsx"
        
        file_picker.save_file(
            dialog_title="日別売上Excelを保存",
            file_name=fname,
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["xlsx"]
        )

def create_export_tab(proxy, page):
    """Factory function"""
    export_tab = ExportTab(proxy, page)
    return export_tab.create_tab(), export_tab
