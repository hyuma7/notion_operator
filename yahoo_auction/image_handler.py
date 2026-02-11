"""
Notion画像のダウンロード・ヤフオクへのアップロード処理
"""

import os
import tempfile
import time
from pathlib import Path
from typing import List
from urllib.parse import urlparse

import requests
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from .config import WAIT_SHORT


class ImageHandler:
    """Notion画像をダウンロードしてヤフオクにアップロード"""

    def __init__(self, driver: WebDriver):
        self.driver = driver
        self.temp_dir = Path(tempfile.mkdtemp(prefix="yahoo_auction_"))
        self._downloaded_files: List[Path] = []

    def download_from_notion(self, files_data: list) -> List[Path]:
        """Notionのfilesプロパティから画像をダウンロード"""
        downloaded = []

        for i, file_info in enumerate(files_data):
            url = file_info.get("url")
            if not url:
                continue

            try:
                ext = self._get_extension(url, file_info.get("name", ""))
                filename = f"image_{i:02d}{ext}"
                filepath = self.temp_dir / filename

                response = requests.get(url, timeout=30)
                response.raise_for_status()

                filepath.write_bytes(response.content)
                downloaded.append(filepath)
                print(f"  画像ダウンロード完了: {filename}")

            except Exception as e:
                print(f"  画像ダウンロードエラー: {e}")

        self._downloaded_files = downloaded
        return downloaded

    def upload_to_form(self, image_paths: List[Path]) -> int:
        """ヤフオク出品フォームに画像をアップロード"""
        uploaded_count = 0

        # 複数画像を一度にアップロード（セミコロン区切りは不可なので1枚ずつ）
        for path in image_paths:
            try:
                # selectFileMultiple IDのinputを優先、なければtype=fileを探す
                file_input = None
                try:
                    file_input = self.driver.find_element(By.ID, "selectFileMultiple")
                except Exception:
                    pass
                if not file_input:
                    file_inputs = self.driver.find_elements(By.CSS_SELECTOR, "#ImageUpload input[type='file']")
                    if file_inputs:
                        file_input = file_inputs[0]
                if not file_input:
                    file_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
                    if file_inputs:
                        file_input = file_inputs[0]

                if not file_input:
                    print("  画像アップロードのinput要素が見つかりません")
                    break

                file_input.send_keys(str(path.resolve()))
                uploaded_count += 1
                print(f"  画像アップロード: {path.name}")
                time.sleep(WAIT_SHORT)

            except Exception as e:
                print(f"  画像アップロードエラー ({path.name}): {e}")

        return uploaded_count

    def cleanup(self):
        """一時ファイルを削除"""
        for filepath in self._downloaded_files:
            try:
                filepath.unlink(missing_ok=True)
            except Exception:
                pass
        try:
            self.temp_dir.rmdir()
        except Exception:
            pass

    @staticmethod
    def _get_extension(url: str, name: str) -> str:
        """URLまたはファイル名から拡張子を取得"""
        # ファイル名から取得
        if name:
            _, ext = os.path.splitext(name)
            if ext:
                return ext

        # URLパスから取得
        parsed = urlparse(url)
        path = parsed.path
        _, ext = os.path.splitext(path)
        if ext and len(ext) <= 5:
            return ext

        return ".jpg"  # デフォルト
