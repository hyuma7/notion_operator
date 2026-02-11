"""
ヤフオク出品操作タブ
"""

import threading
import flet as ft

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from yahoo_auction.login import YahooLogin
from yahoo_auction.listing import YahooAuctionListing


class YahooTab:
    def __init__(self, page: ft.Page, get_notion_data):
        """
        Args:
            page: Fletページ
            get_notion_data: NotionTabからデータを取得するコールバック
        """
        self.page = page
        self.get_notion_data = get_notion_data
        self.login = None
        self.listing = None
        self._is_running = False
        self._build_ui()

    def _build_ui(self):
        # ステータス
        self.status_text = ft.Text(
            "未接続",
            size=16,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.GREY,
        )

        # ボタン
        self.login_btn = ft.ElevatedButton(
            "Yahooログイン",
            icon=ft.Icons.LOGIN,
            on_click=self.on_login,
            bgcolor=ft.Colors.BLUE,
            color=ft.Colors.WHITE,
        )

        self.listing_btn = ft.ElevatedButton(
            "出品開始",
            icon=ft.Icons.SELL,
            on_click=self.on_start_listing,
            disabled=True,
            bgcolor=ft.Colors.GREEN,
            color=ft.Colors.WHITE,
        )

        self.quit_btn = ft.ElevatedButton(
            "ブラウザ終了",
            icon=ft.Icons.CLOSE,
            on_click=self.on_quit,
            disabled=True,
            bgcolor=ft.Colors.RED,
            color=ft.Colors.WHITE,
        )

        # 実行ログ
        self.log_column = ft.Column(
            controls=[],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=2,
        )

        # レイアウト
        self.content = ft.Column(
            controls=[
                ft.Card(
                    content=ft.Container(
                        padding=ft.padding.all(15),
                        content=ft.Column([
                            ft.Row(
                                [ft.Text("ステータス:", size=14), self.status_text],
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            ft.Divider(),
                            ft.Row(
                                [self.login_btn, self.listing_btn, self.quit_btn],
                                spacing=10,
                            ),
                        ]),
                    )
                ),
                ft.Text("実行ログ", size=16, weight=ft.FontWeight.BOLD),
                ft.Divider(),
                self.log_column,
            ],
            expand=True,
            spacing=10,
        )

    def _add_log(self, message: str, success: bool = True):
        """ログ行を追加"""
        icon = ft.Icons.CHECK_CIRCLE if success else ft.Icons.ERROR
        color = ft.Colors.GREEN if success else ft.Colors.RED

        row = ft.Row(
            [
                ft.Icon(icon, size=16, color=color),
                ft.Text(message, size=13),
            ],
            spacing=5,
        )
        self.log_column.controls.append(row)
        self.page.update()

    def _set_status(self, text: str, color):
        self.status_text.value = text
        self.status_text.color = color
        self.page.update()

    def on_login(self, e):
        """Yahooログイン"""
        if self._is_running:
            return

        self._is_running = True
        self.login_btn.disabled = True
        self.log_column.controls.clear()
        self._set_status("ログイン中...", ft.Colors.ORANGE)
        self._add_log("ブラウザを起動中...")
        self.page.update()

        def do_login():
            try:
                self.login = YahooLogin()
                self.login.init_driver()

                def update_init():
                    self._add_log("ブラウザ起動完了")
                    self._add_log("ログイン状態を確認中...")
                self.page.run_thread(update_init)

                logged_in = self.login.ensure_login()

                def on_result():
                    if logged_in:
                        self._set_status("ログイン済み", ft.Colors.GREEN)
                        self._add_log("ログイン成功")
                        self.listing_btn.disabled = False
                        self.quit_btn.disabled = False
                    else:
                        self._set_status("ログイン失敗", ft.Colors.RED)
                        self._add_log("ログインに失敗しました", success=False)
                        if self.login:
                            self.login.quit()
                            self.login = None
                    self.page.update()

                self.page.run_thread(on_result)

            except Exception as ex:
                def on_error():
                    self._set_status("エラー", ft.Colors.RED)
                    self._add_log(f"エラー: {ex}", success=False)
                    if self.login:
                        try:
                            self.login.quit()
                        except Exception:
                            pass
                        self.login = None
                    self.page.update()

                self.page.run_thread(on_error)

            finally:
                def on_finish():
                    self._is_running = False
                    self.login_btn.disabled = False
                    self.page.update()

                self.page.run_thread(on_finish)

        thread = threading.Thread(target=do_login, daemon=True)
        thread.start()

    def on_start_listing(self, e):
        """出品開始"""
        notion_data = self.get_notion_data()
        if not notion_data:
            self._show_snackbar("先にNotionデータタブでデータを取得してください", ft.Colors.RED)
            return

        if not self.login or not self.login.get_driver():
            self._show_snackbar("先にYahooログインしてください", ft.Colors.RED)
            return

        if self._is_running:
            return

        self._is_running = True
        self.listing_btn.disabled = True
        self._add_log("出品フォーム自動入力を開始...")
        self.page.update()

        def on_progress(step: str, message: str):
            """進捗コールバック"""
            success = not message.startswith("[エラー]") and not message.startswith("[要素未発見]")
            def update():
                self._add_log(message, success=success)
            self.page.run_thread(update)

        def do_listing():
            try:
                self.listing = YahooAuctionListing(self.login.get_driver())
                self.listing.fill_form(notion_data, on_progress=on_progress)

                def on_done():
                    self._add_log("自動入力完了 - フォームを確認して手動で出品してください")
                    self._set_status("入力完了", ft.Colors.GREEN)
                    self.page.update()

                self.page.run_thread(on_done)

            except Exception as ex:
                def on_error():
                    self._add_log(f"出品エラー: {ex}", success=False)
                    self.page.update()

                self.page.run_thread(on_error)

            finally:
                def on_finish():
                    self._is_running = False
                    self.listing_btn.disabled = False
                    if self.listing:
                        self.listing.cleanup()
                    self.page.update()

                self.page.run_thread(on_finish)

        thread = threading.Thread(target=do_listing, daemon=True)
        thread.start()

    def on_quit(self, e):
        """ブラウザ終了"""
        if self.login:
            self.login.quit()
            self.login = None
        self.listing = None
        self._set_status("未接続", ft.Colors.GREY)
        self.listing_btn.disabled = True
        self.quit_btn.disabled = True
        self._add_log("ブラウザを閉じました")
        self.page.update()

    def _show_snackbar(self, message: str, color):
        snack = ft.SnackBar(content=ft.Text(message), bgcolor=color)
        self.page.snack_bar = snack
        self.page.snack_bar.open = True
        self.page.update()

    def create_tab(self) -> ft.Tab:
        return ft.Tab(
            text="ヤフオク出品",
            icon=ft.Icons.SELL,
            content=ft.Container(
                padding=ft.padding.all(20),
                content=self.content,
            ),
        )


def create_yahoo_tab(page: ft.Page, get_notion_data) -> tuple[ft.Tab, "YahooTab"]:
    tab = YahooTab(page, get_notion_data)
    return tab.create_tab(), tab
