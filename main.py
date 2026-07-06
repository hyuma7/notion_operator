import os
import traceback
import flet as ft
from dotenv import load_dotenv

from version import __version__

load_dotenv()

# PDF一時ダウンロード用ディレクトリ（Fletがweb modeでstatic配信する）
DOWNLOADS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)


def _create_startup_error_tab(message: str, details: str) -> ft.Tab:
    return ft.Tab(
        text="起動エラー",
        icon=ft.Icons.ERROR_OUTLINE,
        content=ft.Container(
            padding=ft.padding.all(20),
            content=ft.Column(
                [
                    ft.Text(message, size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.RED),
                    ft.Text(details, selectable=True),
                ],
                scroll=ft.ScrollMode.AUTO,
            ),
        ),
    )


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
        details = traceback.format_exc()
        print(f"[WARN] プリンタープロキシのロードに失敗しました: {ex}\n{details}")
        return {
            "error": _create_startup_error_tab(
                "プリンタープロキシのロードに失敗しました",
                details,
            )
        }


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
        details = traceback.format_exc()
        print(f"[WARN] プリンタープロキシの初期化に失敗しました: {ex}\n{details}")
        proxy_tabs = {
            "error": _create_startup_error_tab(
                "プリンタープロキシの初期化に失敗しました",
                details,
            )
        }

    all_tabs = []
    for key in ["label", "export", "receipt", "config", "error"]:
        if key in proxy_tabs:
            all_tabs.append(proxy_tabs[key])

    tabs = ft.Tabs(
        selected_index=0,
        animation_duration=300,
        tabs=all_tabs,
        expand=True,
    )

    page.appbar = ft.AppBar(
        title=ft.Text(f"Notionオペレーター v{__version__}"),
        center_title=True,
        bgcolor=ft.Colors.BLUE_GREY_900,
    )

    page.add(tabs)

    try:
        from updater.ui import check_on_startup, get_update_section

        check_on_startup(page, get_update_section(page))
    except Exception as ex:
        print(f"[WARN] 更新チェックの開始に失敗しました: {ex}")


if __name__ == "__main__":
    ft.app(target=main, assets_dir=DOWNLOADS_DIR)
