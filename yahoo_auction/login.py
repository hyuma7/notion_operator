"""
Yahoo! ログイン管理（Cookie方式）
"""

import os
import pickle
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from .config import (
    YAHOO_AUCTION_URL,
    YAHOO_LOGIN_URL,
    CHROME_PROFILE_DIR,
    COOKIE_FILE,
    WAIT_MEDIUM,
)


class YahooLogin:
    """Yahoo!アカウントのログイン管理"""

    def __init__(self, profile_dir: str = None, cookie_file: str = None):
        self.profile_dir = Path(profile_dir or CHROME_PROFILE_DIR).resolve()
        self.cookie_file = Path(cookie_file or COOKIE_FILE).resolve()
        self.driver = None

    def init_driver(self) -> webdriver.Chrome:
        """Chrome WebDriverを初期化"""
        options = webdriver.ChromeOptions()
        options.add_argument(f"--user-data-dir={self.profile_dir}")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.implicitly_wait(10)
        return self.driver

    def ensure_login(self) -> bool:
        """ログイン状態を確保して返す"""
        if not self.driver:
            self.init_driver()

        self.driver.get(YAHOO_AUCTION_URL)
        time.sleep(WAIT_MEDIUM)

        # 既にログイン済みか確認
        if self._is_logged_in():
            print("ログイン済みです")
            return True

        # Cookie読み込みを試行
        if self._load_cookies():
            self.driver.get(YAHOO_AUCTION_URL)
            time.sleep(WAIT_MEDIUM)
            if self._is_logged_in():
                print("Cookieでログイン復元しました")
                return True

        # 手動ログイン
        print("手動ログインが必要です")
        self.driver.get(YAHOO_LOGIN_URL)
        input("ブラウザでログインを完了し、Enterキーを押してください...")

        self.driver.get(YAHOO_AUCTION_URL)
        time.sleep(WAIT_MEDIUM)

        if self._is_logged_in():
            self._save_cookies()
            print("ログイン成功、Cookieを保存しました")
            return True

        print("ログインに失敗しました")
        return False

    def _is_logged_in(self) -> bool:
        """ログイン状態を確認（ログインリンクの有無で判定）"""
        from selenium.webdriver.common.by import By

        # mhdPcLogin__link（ログインリンク）が存在する = 未ログイン
        # ログイン済みだとこの要素がユーザー情報に置き換わる
        login_links = self.driver.find_elements(By.CSS_SELECTOR, ".mhdPcLogin__link")
        return len(login_links) == 0

    def _save_cookies(self):
        """Cookieをファイルに保存"""
        self.cookie_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cookie_file, "wb") as f:
            pickle.dump(self.driver.get_cookies(), f)

    def _load_cookies(self) -> bool:
        """保存済みCookieを読み込み"""
        if not self.cookie_file.exists():
            return False
        try:
            self.driver.get(YAHOO_AUCTION_URL)
            time.sleep(1)
            with open(self.cookie_file, "rb") as f:
                cookies = pickle.load(f)
            for cookie in cookies:
                try:
                    self.driver.add_cookie(cookie)
                except Exception:
                    pass
            self.driver.refresh()
            return True
        except Exception as e:
            print(f"Cookie読み込みエラー: {e}")
            return False

    def check_login_status(self) -> bool:
        """ログイン状態を高速確認（Yahooページ上なら遷移なし）"""
        if not self.driver:
            return False
        try:
            current_url = self.driver.current_url
            if "yahoo.co.jp" in current_url:
                return self._is_logged_in()
            # 別ドメインにいる場合だけ遷移
            self.driver.get(YAHOO_AUCTION_URL)
            time.sleep(1)
            return self._is_logged_in()
        except Exception:
            return False

    def get_driver(self) -> webdriver.Chrome:
        """現在のWebDriverインスタンスを返す"""
        return self.driver

    def quit(self):
        """WebDriverを終了"""
        if self.driver:
            self.driver.quit()
            self.driver = None
