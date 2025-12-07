"""
ステータスタブコンポーネント
"""

import flet as ft
from typing import Callable


class StatusTab:
    def __init__(self, proxy, page: ft.Page):
        self.proxy = proxy
        self.page = page
        
        # ステータス表示要素
        self.status_text = ft.Text("サーバー停止中", size=20, weight=ft.FontWeight.BOLD)
        self.local_url_text = ft.Text("ローカルURL: -", size=14)
        self.external_url_text = ft.Text("外部URL: -", size=14)
        self.printer_status = ft.Text("プリンター: 未接続", size=14)
        
        # ボタン
        self.start_btn = ft.ElevatedButton(
            "サーバー開始",
            icon=ft.Icons.PLAY_ARROW,
            on_click=self.start_server,
            bgcolor=ft.Colors.GREEN,
            color=ft.Colors.WHITE
        )

        self.stop_btn = ft.ElevatedButton(
            "サーバー停止",
            icon=ft.Icons.STOP,
            on_click=self.stop_server,
            bgcolor=ft.Colors.RED,
            color=ft.Colors.WHITE,
            disabled=True
        )

        self.test_btn = ft.ElevatedButton(
            "接続テスト",
            icon=ft.Icons.WIFI,
            on_click=self.test_connection
        )
    
    def start_server(self, e):
        """サーバーを開始"""
        self.proxy.start_server()
        self.status_text.value = "サーバー稼働中"
        self.status_text.color = ft.Colors.GREEN
        local_url = f"http://localhost:{self.proxy.config['proxy_port']}"
        self.local_url_text.value = f"ローカルURL: {local_url}"
        
        if self.proxy.ngrok_url:
            self.external_url_text.value = f"外部URL: {self.proxy.ngrok_url}"
        else:
            self.external_url_text.value = "外部URL: ngrok未設定"
        
        self.start_btn.disabled = True
        self.stop_btn.disabled = False
        self.page.update()
    
    def stop_server(self, e):
        """サーバーを停止"""
        self.proxy.stop_server()
        self.status_text.value = "サーバー停止中"
        self.status_text.color = ft.Colors.RED
        self.local_url_text.value = "ローカルURL: -"
        self.external_url_text.value = "外部URL: -"
        self.start_btn.disabled = False
        self.stop_btn.disabled = True
        self.page.update()
    
    def test_connection(self, e):
        """プリンター接続テスト"""
        result = self.proxy.test_printer_connection()
        if result.get('connected'):
            self.printer_status.value = f"プリンター: 接続OK ({self.proxy.config['printer_ip']}:{self.proxy.config['printer_port']})"
            self.printer_status.color = ft.Colors.GREEN
            self.show_snackbar("プリンターに正常に接続できました", ft.Colors.GREEN)
        else:
            self.printer_status.value = "プリンター: 接続エラー"
            self.printer_status.color = ft.Colors.RED
            error = result.get('error', 'Unknown error')
            self.show_snackbar(f"プリンターに接続できません: {error}", ft.Colors.RED)
        self.page.update()
    
    def show_snackbar(self, message: str, color):
        """スナックバーを表示"""
        snack = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=color
        )
        self.page.snack_bar = snack
        self.page.snack_bar.open = True
        self.page.update()
    
    def open_web_interface(self, e):
        """Webインターフェースを開く"""
        if self.proxy.running:
            self.page.launch_url(f"http://localhost:{self.proxy.config['proxy_port']}")
    
    def create_tab(self) -> ft.Tab:
        """タブを作成"""
        return ft.Tab(
            text="ステータス",
            icon=ft.Icons.INFO,
            content=ft.Container(
                padding=ft.padding.all(20),
                content=ft.Column([
                    ft.Card(
                        content=ft.Container(
                            padding=ft.padding.all(20),
                            content=ft.Column([
                                self.status_text,
                                ft.Divider(),
                                self.local_url_text,
                                self.external_url_text,
                                self.printer_status,
                                ft.Divider(),
                                ft.Row([self.start_btn, self.stop_btn, self.test_btn], spacing=10)
                            ])
                        )
                    ),
                    ft.Card(
                        content=ft.Container(
                            padding=ft.padding.all(20),
                            content=ft.Column([
                                ft.Text("クイックアクション", size=18, weight=ft.FontWeight.BOLD),
                                ft.Divider(),
                                ft.ElevatedButton(
                                    "Webインターフェースを開く",
                                    icon=ft.Icons.OPEN_IN_BROWSER,
                                    on_click=self.open_web_interface
                                )
                            ])
                        )
                    )
                ])
            )
        )


def create_status_tab(proxy, page: ft.Page) -> tuple[ft.Tab, StatusTab]:
    """ステータスタブを作成して返す"""
    status_tab = StatusTab(proxy, page)
    return status_tab.create_tab(), status_tab