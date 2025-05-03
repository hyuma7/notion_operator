# eBay連携機能

このモジュールはNotionデータベースの商品をeBayに出品し、売却時にNotionの商品情報を自動更新する機能を提供します。

## 機能

1. Notionデータベースから販売可能な商品を取得
2. 商品をeBayに出品
3. eBayからの売却通知を受け取り、Notionの商品ステータスを更新

## セットアップ

### 必要な環境変数

以下の環境変数を設定してください：

```
# Notion API設定
NOTION_API_KEY=your_notion_api_key
NOTION_PRODUCTS_DB_ID=your_notion_products_database_id
ALLOWED_NOTION_WORKSPACES=workspace_id1,workspace_id2

# eBay API設定
EBAY_APP_ID=your_ebay_app_id
EBAY_DEV_ID=your_ebay_dev_id
EBAY_CERT_ID=your_ebay_cert_id
EBAY_TOKEN=your_ebay_token
PAYPAL_EMAIL=your_paypal_email
```

### インストール

```bash
pip install -r requirements.txt
```

## 使用方法

### 商品をeBayに出品

特定の商品をeBayに出品する場合：

```
POST /ebay/list
Content-Type: application/json

{
  "product_id": "notion_page_id_of_product"
}
```

販売待ち状態の全商品を出品する場合：

```
POST /ebay/list
Content-Type: application/json

{}
```

### eBayからの売却通知受信

eBayからの通知を受け取るエンドポイント：

```
POST /ebay/notification
Content-Type: application/json

{
  "ItemID": "ebay_item_id",
  "TransactionID": "transaction_id"
}
```

## ワークスペース認証

このアプリケーションはNotionのワークスペース認証を使用して、許可されたワークスペースからのリクエストのみを処理します。
`ALLOWED_NOTION_WORKSPACES`環境変数に許可するワークスペースIDをカンマ区切りで設定してください。 