import os
from dotenv import load_dotenv
from models import NotionDB

def main():
    # 環境変数の読み込み
    load_dotenv()
    notion_token = os.getenv("NOTION_TOKEN")
    
    if not notion_token:
        raise ValueError("NOTION_TOKEN environment variable is not set")
    
    # Notionデータベースの初期化
    db = NotionDB(token=notion_token)
    databases = db.create_databases()
    
    print("Notionデータベースの初期化が完了しました。")
    print("作成されたデータベース:")
    for name, database in databases.items():
        print(f"- {name}: {database.title}")

if __name__ == "__main__":
    main() 