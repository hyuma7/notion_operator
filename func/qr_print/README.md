# Notion QR Print - Cloud Functions

## 📋 概要

NotionのWebhookを受信してQRコード付きラベルデータを生成するGoogle Cloud Functions です。

## 🏗️ アーキテクチャ

```
Notion Automation → Cloud Functions → QRラベルデータ → ローカル印刷
```

## 📁 ディレクトリ構成

```
qr_print/
├── 📦 Cloud Functions デプロイ用
│   ├── main_deploy.py          # エントリーポイント
│   ├── requirements_deploy.txt # 依存関係
│   ├── deploy.sh              # デプロイスクリプト
│   ├── README_DEPLOY.md       # デプロイガイド
│   └── .gcloudignore          # デプロイ除外設定
│
├── 🛠️ local_tools/ - ローカルツール
│   ├── notion_qr_html.py      # HTMLプレビュー版
│   ├── notion_qr_image_large.py # 高品質画像生成版
│   ├── test_image_print.py    # Brother QL印刷テスト
│   └── README.md              # ツール説明
│
├── 🧪 test/ - テスト用ファイル
│   ├── label_*.png            # テスト画像
│   ├── requirements.txt       # ローカル用依存関係
│   └── README_TEST.md         # テストファイル説明
│
└── main.py                    # 元のメインファイル（保持）
```

## 🚀 クイックスタート

### 1. ローカルでプレビュー
```bash
cd local_tools
python3 notion_qr_html.py
```

### 2. Cloud Functions デプロイ
```bash
./deploy.sh
```

### 3. 印刷テスト
```bash
cd local_tools
python3 test_image_print.py ../test/label_example.png
```

## 🔧 環境変数

| 変数名 | デフォルト値 | 説明 |
|--------|-------------|------|
| `PRINTER_IP` | `192.168.1.100` | Brother QLプリンターのIP |
| `PRINTER_MODEL` | `QL-820NWB` | プリンターモデル |
| `DEFAULT_LABEL_SIZE` | `62x29` | デフォルトラベルサイズ |

## 📡 API エンドポイント

### POST `/`

```bash
curl -X POST 'https://YOUR-FUNCTION-URL?fields=title,category,date' \
  -H 'Content-Type: application/json' \
  -d '{"data":{"properties":{"Name":{"type":"title","title":[{"plain_text":"商品名"}]}}}}'
```

## 📝 主な機能

✅ **Notionウェブフック受信** - JSON ペイロード処理  
✅ **QRデータ生成** - ページ情報をJSON形式でエンコード  
✅ **カスタムフィールド対応** - 任意のNotionプロパティを表示  
✅ **大きなフォント対応** - 見やすいサイズに調整済み  
✅ **CORS対応** - ブラウザからのリクエスト可能  
✅ **エラーハンドリング** - 詳細なエラーレスポンス  

## 🖨️ 印刷フロー

1. **Notion Automation** → Cloud Functions でラベルデータ生成
2. **ローカル受信** → `local_tools/` でプレビュー・画像生成
3. **Brother QL印刷** → 実際のQRラベル出力

## 📚 詳細ドキュメント

- [デプロイガイド](README_DEPLOY.md)
- [ローカルツール](local_tools/README.md)
- [テストファイル](test/README_TEST.md)