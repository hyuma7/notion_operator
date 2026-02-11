"""
出品ツール GUI - メインアプリケーション
Notionデータ表示 + ヤフオク自動出品
"""

import os
import sys

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import flet as ft

from .notion_tab import create_notion_tab
from .yahoo_tab import create_yahoo_tab


def main(page: ft.Page):
    """Fletアプリケーションのメイン関数"""
    page.title = "出品ツール"
    page.window.width = 1000
    page.window.height = 700
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0

    # Notionタブ
    notion_tab, notion_component = create_notion_tab(page)

    # ヤフオクタブ（Notionデータを参照できるようにコールバックを渡す）
    yahoo_tab, yahoo_component = create_yahoo_tab(
        page, lambda: notion_component.notion_data
    )

    # タブ構成
    tabs = ft.Tabs(
        selected_index=0,
        animation_duration=300,
        tabs=[notion_tab, yahoo_tab],
        expand=True,
    )

    # AppBar
    appbar = ft.AppBar(
        title=ft.Text("出品ツール"),
        center_title=True,
        bgcolor=ft.Colors.BLUE_GREY_900,
    )

    page.appbar = appbar
    page.add(tabs)
