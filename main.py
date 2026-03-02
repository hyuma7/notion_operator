"""
出品ツール + プリンタープロキシ 統合 GUI 起動スクリプト
"""

import flet as ft
from listing_gui.app import main

if __name__ == "__main__":
    ft.app(target=main)
