import os
import flet as ft
from dotenv import load_dotenv

load_dotenv()

# PDF一時ダウンロード用ディレクトリ（Fletがweb modeでstatic配信する）
DOWNLOADS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)


def _try_load_proxy_tabs(proxy, page) -> dict:
    """brother_ql_proxy のタブを読み込む。失敗時は空辞書を返す"""
    try:
        from brother_ql_proxy.ui import (
            create_config_tab,
            create_export_tab,
            create_label_tab,
            create_receipt_tab,
        )

        config_tab, _ = create_config_tab(proxy, page)
        export_tab, _ = create_export_tab(proxy, page)
        label_tab, _ = create_label_tab(proxy, page)
        receipt_tab, _ = create_receipt_tab(proxy, page)
        return {
            "label": label_tab,
            "export": export_tab,
            "receipt": receipt_tab,
            "config": config_tab,
        }
    except Exception as ex:
        print(f"[WARN] プリンタープロキシのロードに失敗しました: {ex}")
        return {}


def main(page: ft.Page):
    """Notionオペレーターのメイン関数"""
    page.title = "Notionオペレーター"
    page.window.width = 1100
    page.window.height = 750
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0

    proxy_tabs = {}
    try:
        from brother_ql_proxy.core import PrinterProxy

        proxy = PrinterProxy()
        proxy_tabs = _try_load_proxy_tabs(proxy, page)
    except Exception as ex:
        print(f"[WARN] プリンタープロキシの初期化に失敗しました: {ex}")

    all_tabs = []
    for key in ["label", "export", "receipt", "config"]:
        if key in proxy_tabs:
            all_tabs.append(proxy_tabs[key])

    tabs = ft.Tabs(
        selected_index=0,
        animation_duration=300,
        tabs=all_tabs,
        expand=True,
    )

    page.appbar = ft.AppBar(
        title=ft.Text("Notionオペレーター"),
        center_title=True,
        bgcolor=ft.Colors.BLUE_GREY_900,
    )

    page.add(tabs)


if __name__ == "__main__":
    ft.app(target=main, assets_dir=DOWNLOADS_DIR)
