"""
ヤフオク自動出品ツール - エントリーポイント
Notion共有URLから商品情報を取得し、ヤフオク出品フォームに自動入力する

使い方:
    python -m yahoo_auction.main <Notion共有URL>
    python -m yahoo_auction.main  (テスト用URLを使用)
"""

import sys
import os

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from fetch_notion_page import extract_page_id, fetch_all_properties
from yahoo_auction.login import YahooLogin
from yahoo_auction.listing import YahooAuctionListing


def main():
    notion_api_key = os.getenv("NOTION_API_KEY")
    if not notion_api_key:
        print("エラー: NOTION_API_KEY が .env に設定されていません")
        sys.exit(1)

    # URL取得
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = "https://www.notion.so/30454e6206d880619fa7f9510bb20ede?source=copy_link"
        print(f"テスト用URLを使用: {url}")

    # 1. Notionからデータ取得
    print("\n【Step 1】Notionからデータを取得中...")
    page_id = extract_page_id(url)
    notion_data = fetch_all_properties(page_id)

    title = notion_data["properties"].get("商品名", {}).get("value", "不明")
    print(f"  商品名: {title}")
    print(f"  ページID: {page_id}")

    # プロパティ一覧を表示
    print("\n  --- 取得したプロパティ ---")
    for name, info in notion_data["properties"].items():
        value = info.get("value")
        if value is not None and value != "" and value != []:
            print(f"  {name}: {value}")

    # 2. Yahooにログイン
    print("\n【Step 2】Yahoo!にログイン中...")
    login = YahooLogin()

    try:
        if not login.ensure_login():
            print("ログインに失敗しました。終了します。")
            login.quit()
            sys.exit(1)

        # 3. 出品フォームに自動入力
        print("\n【Step 3】出品フォームに自動入力中...")
        listing = YahooAuctionListing(login.get_driver())

        try:
            listing.fill_form(notion_data)
        finally:
            listing.cleanup()

    finally:
        login.quit()
        print("\nブラウザを閉じました。完了です。")


if __name__ == "__main__":
    main()
