"""
Brother QL プリンタープロキシ - メインアプリケーション
コンポーネント化されたFlet版
"""

import flet as ft
from .core import PrinterProxy
from .ui import create_status_tab, create_config_tab, create_log_tab
from .web import create_flask_app


def main(page: ft.Page):
    """Fletアプリケーションのメイン関数"""
    # ページ設定
    page.title = "Brother QL プリンタープロキシ"
    page.window_width = 900
    page.window_height = 700
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    
    # プロキシインスタンスを作成
    proxy = PrinterProxy()
    
    # Flaskアプリを作成してプロキシに設定
    flask_app = create_flask_app(proxy)
    proxy.set_flask_app(flask_app)
    
    # 各タブコンポーネントを作成
    status_tab, status_component = create_status_tab(proxy, page)
    config_tab, config_component = create_config_tab(proxy, page)
    log_tab, log_component = create_log_tab(proxy, page)
    
    # メインタブコンテナ
    tabs = ft.Tabs(
        selected_index=0,
        animation_duration=300,
        tabs=[status_tab, config_tab, log_tab],
        expand=True
    )
    
    # AppBar
    def show_about(e):
        """バージョン情報を表示"""
        dlg = ft.AlertDialog(
            title=ft.Text("Brother QL プリンタープロキシ"),
            content=ft.Column([
                ft.Text("バージョン: 1.0.0"),
                ft.Text("モダンなFletインターフェース版"),
                ft.Divider(),
                ft.Text("Brother QLプリンターをネットワーク経由で"),
                ft.Text("利用可能にするプロキシサーバー")
            ], tight=True),
            actions=[
                ft.TextButton("閉じる", on_click=lambda e: close_dialog())
            ]
        )
        page.dialog = dlg
        dlg.open = True
        page.update()
    
    def close_dialog():
        page.dialog.open = False
        page.update()
    
    appbar = ft.AppBar(
        title=ft.Text("Brother QL プリンタープロキシ"),
        center_title=True,
        bgcolor=ft.Colors.BLUE_GREY_900,
        actions=[
            ft.IconButton(
                icon=ft.Icons.INFO_OUTLINE,
                tooltip="バージョン情報",
                on_click=show_about
            )
        ]
    )
    
    # ページに追加
    page.appbar = appbar
    page.add(tabs)
    
    # 初期接続テスト（コメントアウト - 必要に応じて手動実行）
    # status_component.test_connection(None)
    
    # ウィンドウクローズ時の処理
    def window_event(e):
        if e.data == "close":
            if proxy.running:
                proxy.stop_server()
    
    page.window_prevent_close = True
    page.on_window_event = window_event


# このファイルは直接実行せず、run_proxy.pyから実行してください