import os
from dotenv import load_dotenv

# .envファイルがあれば読み込む
load_dotenv()

# Notion API設定
NOTION_API_KEY = os.environ.get('NOTION_API_KEY')
NOTION_PRODUCTS_DB_ID = os.environ.get('NOTION_PRODUCTS_DB_ID')
NOTION_NOTIFICATIONS_DB_ID = os.environ.get('NOTION_NOTIFICATIONS_DB_ID')
ALLOWED_NOTION_WORKSPACES = os.environ.get('ALLOWED_NOTION_WORKSPACES', '').split(',')

# eBay API設定
EBAY_APP_ID = os.environ.get('EBAY_APP_ID')
EBAY_DEV_ID = os.environ.get('EBAY_DEV_ID')
EBAY_CERT_ID = os.environ.get('EBAY_CERT_ID')
EBAY_TOKEN = os.environ.get('EBAY_TOKEN')
PAYPAL_EMAIL = os.environ.get('PAYPAL_EMAIL')

# アプリケーション設定
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
PORT = int(os.environ.get('PORT', 8080))

# 設定の検証
def validate_config():
    """必要な環境変数が設定されているか検証する"""
    required_vars = [
        'NOTION_API_KEY',
        'NOTION_PRODUCTS_DB_ID',
        'EBAY_APP_ID',
        'EBAY_DEV_ID',
        'EBAY_CERT_ID',
        'EBAY_TOKEN'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not globals().get(var):
            missing_vars.append(var)
    
    if missing_vars:
        raise EnvironmentError(f"必要な環境変数が設定されていません: {', '.join(missing_vars)}") 