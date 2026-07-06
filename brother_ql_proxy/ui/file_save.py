import os
import platform
import subprocess
from typing import Callable, Optional

import flet as ft


def should_save_directly(page: ft.Page) -> bool:
    return platform.system() == "Darwin" and not getattr(page, "web", False)


def get_downloads_dir() -> str:
    return os.path.expanduser("~/Downloads")


def unique_file_path(directory: str, filename: str) -> str:
    path = os.path.join(directory, filename)
    if not os.path.exists(path):
        return path

    stem, ext = os.path.splitext(filename)
    index = 2
    while True:
        candidate = os.path.join(directory, f"{stem}_{index}{ext}")
        if not os.path.exists(candidate):
            return candidate
        index += 1


def default_download_path(filename: str) -> str:
    downloads_dir = get_downloads_dir()
    os.makedirs(downloads_dir, exist_ok=True)
    return unique_file_path(downloads_dir, filename)


def open_containing_folder(file_path: str):
    folder = os.path.dirname(os.path.abspath(file_path))
    system = platform.system()

    if system == "Darwin":
        subprocess.Popen(["open", folder])
    elif system == "Windows":
        os.startfile(folder)  # type: ignore[attr-defined]
    else:
        subprocess.Popen(["xdg-open", folder])


def clear_saved_file_status_action(status_text: ft.Text):
    status_text.on_tap = None
    status_text.tooltip = None
    status_text.color = None
    status_text.spans = None


def set_saved_file_status(status_text: ft.Text, page: ft.Page, file_path: str):
    folder = os.path.dirname(os.path.abspath(file_path))
    status_text.value = "ファイルを保存しました。 "
    status_text.color = ft.Colors.GREEN
    status_text.tooltip = None

    def open_folder(_):
        try:
            open_containing_folder(file_path)
        except Exception as ex:
            snack = ft.SnackBar(
                content=ft.Text(f"保存先フォルダを開けませんでした: {str(ex)}"),
                bgcolor=ft.Colors.RED,
            )
            page.snack_bar = snack
            page.snack_bar.open = True
            page.update()

    status_text.spans = [
        ft.TextSpan(
            text="保存したフォルダを開く",
            style=ft.TextStyle(
                color=ft.Colors.BLUE_700,
                decoration=ft.TextDecoration.UNDERLINE,
            ),
            on_click=open_folder,
        ),
        ft.TextSpan(
            text=f" ({folder})",
            style=ft.TextStyle(color=ft.Colors.GREEN),
        ),
    ]


def save_file_for_platform(
    page: ft.Page,
    dialog_title: str,
    file_name: str,
    allowed_extensions: list[str],
    write_file: Callable[[str], None],
    on_saved: Callable[[str], None],
    on_error: Callable[[Exception], None],
) -> Optional[ft.FilePicker]:
    if should_save_directly(page):
        try:
            path = default_download_path(file_name)
            write_file(path)
            on_saved(path)
        except Exception as ex:
            on_error(ex)
        return None

    def save_file(ev: ft.FilePickerResultEvent):
        if not ev.path:
            return
        try:
            write_file(ev.path)
            on_saved(ev.path)
        except Exception as ex:
            on_error(ex)

    file_picker = ft.FilePicker(on_result=save_file)
    page.overlay.append(file_picker)
    page.update()
    file_picker.save_file(
        dialog_title=dialog_title,
        file_name=file_name,
        file_type=ft.FilePickerFileType.CUSTOM,
        allowed_extensions=allowed_extensions,
    )
    return file_picker
