"""
出品ツール + プリンタープロキシ 統合アプリ
タブ構成: [ラベル印刷] [出品] [Excel出力] [設定]
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import flet as ft

from .listing_tab import create_listing_tab


def _try_load_proxy_tabs(proxy, page) -> dict:
    """brother_ql_proxy のタブを読み込む。失敗時は空辞書を返す"""
    try:
        from brother_ql_proxy.ui import (
            create_config_tab, create_export_tab, create_label_tab,
        )
        config_tab, _ = create_config_tab(proxy, page)
        export_tab, _ = create_export_tab(proxy, page)
        label_tab, _ = create_label_tab(proxy, page)
        return {"label": label_tab, "export": export_tab, "config": config_tab}
    except Exception as ex:
        print(f"[WARN] プリンタープロキシのロードに失敗しました: {ex}")
        return {}


def main(page: ft.Page):
    """統合アプリのメイン関数"""
    page.title = "出品ツール"
    page.window.width = 1100
    page.window.height = 750
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0

    listing_tab = create_listing_tab(page)

    proxy = None
    proxy_tabs = {}
    try:
        from brother_ql_proxy.core import PrinterProxy
        proxy = PrinterProxy()
        proxy_tabs = _try_load_proxy_tabs(proxy, page)
    except Exception as ex:
        print(f"[WARN] プリンタープロキシの初期化に失敗しました: {ex}")

    # タブ順: ラベル印刷 > 出品 > Excel出力 > 設定
    all_tabs = []
    if "label" in proxy_tabs:
        all_tabs.append(proxy_tabs["label"])
    all_tabs.append(listing_tab)
    if "export" in proxy_tabs:
        all_tabs.append(proxy_tabs["export"])
    if "config" in proxy_tabs:
        all_tabs.append(proxy_tabs["config"])

    tabs = ft.Tabs(
        selected_index=0,
        animation_duration=300,
        tabs=all_tabs,
        expand=True,
    )

    page.appbar = ft.AppBar(
        title=ft.Text("出品ツール"),
        center_title=True,
        bgcolor=ft.Colors.BLUE_GREY_900,
    )

    page.add(tabs)
