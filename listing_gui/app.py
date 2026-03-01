"""
出品ツール + プリンタープロキシ 統合アプリ
タブ構成:
  [Notionデータ] [ヤフオク出品] | [プロキシ状態] [設定] [ログ] [エクスポート]
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import flet as ft

from .notion_tab import create_notion_tab
from .yahoo_tab import create_yahoo_tab


def _try_load_proxy_tabs(proxy, page):
    """brother_ql_proxy のタブを読み込む。失敗時は空リストを返す"""
    try:
        from brother_ql_proxy.ui import (
            create_status_tab, create_config_tab,
            create_log_tab, create_export_tab, create_label_tab,
        )
        status_tab, _ = create_status_tab(proxy, page)
        config_tab, _ = create_config_tab(proxy, page)
        log_tab, _ = create_log_tab(proxy, page)
        export_tab, _ = create_export_tab(proxy, page)
        label_tab, _ = create_label_tab(proxy, page)
        return [status_tab, config_tab, log_tab, export_tab, label_tab]
    except Exception as ex:
        print(f"[WARN] プリンタープロキシのロードに失敗しました: {ex}")
        return []


def main(page: ft.Page):
    """統合アプリのメイン関数"""
    page.title = "出品ツール + プリンタープロキシ"
    page.window.width = 1100
    page.window.height = 750
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0

    # ── 出品ツール タブ ──────────────────────────────────────────
    notion_tab, notion_component = create_notion_tab(page)
    yahoo_tab, _ = create_yahoo_tab(page, lambda: notion_component.notion_data)

    # ── プリンタープロキシ タブ ──────────────────────────────────
    proxy = None
    proxy_tabs = []
    try:
        from brother_ql_proxy.core import PrinterProxy
        from brother_ql_proxy.web import create_flask_app
        proxy = PrinterProxy()
        flask_app = create_flask_app(proxy)
        proxy.set_flask_app(flask_app)
        proxy_tabs = _try_load_proxy_tabs(proxy, page)
    except Exception as ex:
        print(f"[WARN] プリンタープロキシの初期化に失敗しました: {ex}")

    # ── タブ統合 ─────────────────────────────────────────────────
    all_tabs = [notion_tab, yahoo_tab] + proxy_tabs

    tabs = ft.Tabs(
        selected_index=0,
        animation_duration=300,
        tabs=all_tabs,
        expand=True,
    )

    # ── AppBar ───────────────────────────────────────────────────
    page.appbar = ft.AppBar(
        title=ft.Text("出品ツール + プリンタープロキシ"),
        center_title=True,
        bgcolor=ft.Colors.BLUE_GREY_900,
    )

    page.add(tabs)

    # ── ウィンドウクローズ処理 ────────────────────────────────────
    def on_window_event(e):
        if e.data == "close" and proxy and proxy.running:
            proxy.stop_server()

    page.window_prevent_close = True
    page.on_window_event = on_window_event
