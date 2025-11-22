# Notion QR Print - Google Cloud Functions デプロイガイド

## 📋 概要

NotionのWebhookを受信してQRコード付きラベルデータを生成するCloud Functions です。

## 🏗️ アーキテクチャ

```
Notion Automation → Cloud Functions → QRラベルデータ → ローカル印刷
```

## 🚀 デプロイ手順

### 1. 前提条件

- Google Cloud SDK (`gcloud`) がインストール済み
- Google Cloud プロジェクトが作成済み
- Cloud Functions API が有効化済み

```bash
# Google Cloud SDK ログイン
gcloud auth login

# プロジェクト設定
gcloud config set project YOUR_PROJECT_ID

# 必要なAPIを有効化
gcloud services enable cloudfunctions.googleapis.com
gcloud services enable cloudbuild.googleapis.com
```

### 2. ローカルテスト

```bash
# ローカル開発サーバー起動
python3 main_deploy.py

# 別ターミナルでテスト実行
python3 test_deploy.py
```

### 3. デプロイ実行

```bash
# 環境変数を設定してデプロイ
export PRINTER_IP="192.168.1.100"
export PRINTER_MODEL="QL-820NWB"
export DEFAULT_LABEL_SIZE="62x29"

# デプロイ実行
./deploy.sh
```

### 4. デプロイ後テスト

```bash
# Cloud Functionのテスト
python3 test_deploy.py --cloud https://YOUR-FUNCTION-URL
```

## 🔧 環境変数

| 変数名 | デフォルト値 | 説明 |
|--------|-------------|------|
| `PRINTER_IP` | `192.168.1.100` | Brother QLプリンターのIPアドレス |
| `PRINTER_MODEL` | `QL-820NWB` | プリンターモデル |
| `DEFAULT_LABEL_SIZE` | `62x29` | デフォルトのラベルサイズ (mm) |

## 📡 API エンドポイント

### POST `/`

Notionウェブフックを受信してラベルデータを生成

#### クエリパラメータ

- `fields` (配列): 表示するフィールド名
  - 例: `?fields=title&fields=category&fields=date`
- `size` (文字列): ラベルサイズ
  - 例: `?size=62x29` または `?size=62x100`

#### リクエスト例

```bash
curl -X POST 'https://YOUR-FUNCTION-URL?fields=title,category,date' \
  -H 'Content-Type: application/json' \
  -d '{
    "data": {
      "id": "page-id",
      "url": "https://notion.so/page",
      "properties": {
        "Name": {"type": "title", "title": [{"plain_text": "商品名"}]},
        "Category": {"type": "select", "select": {"name": "カテゴリ"}}
      }
    }
  }'
```

#### レスポンス例

```json
{
  "success": true,
  "message": "ラベルデータを生成しました",
  "data": {
    "title": "商品名",
    "icon": "📦",
    "fields": [
      {"label": "📂 カテゴリ", "value": "カテゴリ"}
    ],
    "qr_data": {
      "id": "page-id",
      "title": "商品名",
      "category": "カテゴリ",
      "url": "https://notion.so/page"
    },
    "label_size": "62x29",
    "print_command": "brother_ql -b network -m QL-820NWB -p tcp://192.168.1.100:9100 print -l 62 label.png"
  },
  "metadata": {
    "function_name": "notion_qr_webhook",
    "version": "1.0.0",
    "timestamp": "2025-01-18T12:00:00Z"
  }
}
```

## 🖨️ ローカル印刷との連携

Cloud Functionsから返されるデータを使って、ローカルで印刷を実行：

```python
import requests

# Cloud Functionからデータ取得
response = requests.post('https://YOUR-FUNCTION-URL', json=notion_payload)
label_data = response.json()['data']

# 画像生成 (ローカル)
from notion_qr_html import create_html_preview
html_file = create_html_preview(label_data)

# 印刷実行 (ローカル)
import subprocess
subprocess.run([
    'brother_ql', '-b', 'network', '-m', 'QL-820NWB',
    '-p', 'tcp://192.168.1.100:9100',
    'print', '-l', '62', 'label.png'
])
```

## 🔗 Notion Automation 設定

1. Notionで Automation を作成
2. Trigger: ページ作成・更新
3. Action: Webhook
4. Webhook URL: `https://YOUR-FUNCTION-URL?fields=title,category,date,Location`

## 📊 監視・ログ

```bash
# Cloud Functions のログ確認
gcloud functions logs read notion-qr-print --region=asia-northeast1

# リアルタイムログ監視
gcloud functions logs tail notion-qr-print --region=asia-northeast1
```

## 🛠️ トラブルシューティング

### デプロイエラー

```bash
# 権限確認
gcloud auth list
gcloud config list

# APIの有効化確認
gcloud services list --enabled | grep functions
```

### 実行時エラー

```bash
# 詳細ログ確認
gcloud functions logs read notion-qr-print --region=asia-northeast1 --limit=50
```

### テスト用コマンド

```bash
# 基本テスト
curl -X POST 'https://YOUR-FUNCTION-URL' \
  -H 'Content-Type: application/json' \
  -d '{"data":{"id":"test","properties":{"Name":{"type":"title","title":[{"plain_text":"テスト"}]}}}}'

# エラーテスト
curl -X GET 'https://YOUR-FUNCTION-URL'  # Method not allowed

# 空ペイロードテスト  
curl -X POST 'https://YOUR-FUNCTION-URL' \
  -H 'Content-Type: application/json' \
  -d '{}'
```

## 📝 ファイル構成

```
func/qr_print/
├── main_deploy.py          # Cloud Functions メインファイル
├── requirements_deploy.txt # デプロイ用依存関係
├── deploy.sh              # デプロイスクリプト
├── test_deploy.py          # テストスクリプト
├── .gcloudignore          # デプロイ除外ファイル
├── README_DEPLOY.md       # このファイル
│
├── main.py                # ローカル版メイン
├── notion_qr_japanese.py  # ローカル テキスト版
├── notion_qr_html.py      # ローカル HTML版
├── test_image_print.py    # ローカル 印刷テスト
└── requirements.txt       # ローカル用依存関係
```

## 🔄 更新・削除

```bash
# 関数更新 (再デプロイ)
./deploy.sh

# 関数削除
gcloud functions delete notion-qr-print --region=asia-northeast1
```