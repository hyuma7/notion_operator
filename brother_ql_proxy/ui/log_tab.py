"""
ログタブコンポーネント
"""

import flet as ft
from datetime import datetime


class LogTab:
    def __init__(self, proxy, page: ft.Page):
        self.proxy = proxy
        self.page = page
        
        # ログリスト
        self.log_list = ft.ListView(
            expand=True,
            spacing=2,
            padding=ft.padding.all(10),
            auto_scroll=True
        )
        
        # プロキシにログコールバックを登録
        proxy.add_log_callback(self.add_log)
    
    def add_log(self, message: str):
        """ログを追加"""
        timestamp = datetime.now().strftime('%H:%M:%S')

        # ログレベルによって色を変更
        bgcolor = ft.Colors.GREY_100
        if "[ERROR]" in message:
            bgcolor = ft.Colors.RED_100
        elif "[WARNING]" in message:
            bgcolor = ft.Colors.YELLOW_100
        elif "[INFO]" in message:
            bgcolor = ft.Colors.BLUE_100
        
        log_item = ft.Container(
            content=ft.Text(f"{timestamp} {message}", size=12),
            padding=ft.padding.symmetric(horizontal=10, vertical=5),
            border_radius=ft.border_radius.all(5),
            bgcolor=bgcolor
        )
        
        self.log_list.controls.append(log_item)
        
        # ログが100件を超えたら古いものを削除
        if len(self.log_list.controls) > 100:
            self.log_list.controls.pop(0)
        
        self.page.update()
    
    def clear_logs(self, e):
        """ログをクリア"""
        self.log_list.controls.clear()
        self.page.update()
    
    def create_tab(self) -> ft.Tab:
        """タブを作成"""
        return ft.Tab(
            text="ログ",
            icon=ft.Icons.DESCRIPTION,
            content=ft.Container(
                padding=ft.padding.all(10),
                content=ft.Column([
                    ft.Row([
                        ft.Text("システムログ", size=18, weight=ft.FontWeight.BOLD),
                        ft.Container(expand=True),
                        ft.IconButton(
                            icon=ft.Icons.CLEAR_ALL,
                            tooltip="ログをクリア",
                            on_click=self.clear_logs
                        )
                    ]),
                    ft.Divider(),
                    ft.Card(
                        expand=True,
                        content=ft.Container(
                            padding=ft.padding.all(10),
                            content=self.log_list
                        )
                    )
                ])
            )
        )


def create_log_tab(proxy, page: ft.Page) -> tuple[ft.Tab, LogTab]:
    """ログタブを作成して返す"""
    log_tab = LogTab(proxy, page)
    return log_tab.create_tab(), log_tab