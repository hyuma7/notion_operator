### 使用技術
- NotionのSDKとPythonを使用
- クラウドはGcloudを使用
- Cloud Functionsを使用

### 機能一覧
- 自分自身のQRブロック追加

# Notion QRコード生成ツール

Notionページに簡単にQRコードを追加するためのGoogle Cloud Functions実装です。

## 機能概要

- Notionページへのカスタム QRコードブロック追加
- 指定されたデータから動的にQRコード生成
- カスタムキャプション対応
- クラウドベースのサーバーレスアーキテクチャ

## 技術スタック

### バックエンド
- **言語**: Python 3.10
- **クラウド環境**: Google Cloud Platform (GCP)
- **サーバーレス**: Google Cloud Functions
- **ストレージ**: Google Cloud Storage
- **APIクライアント**: Notion SDK for Python

### ライブラリ
- **notion-client**: Notion APIとの連携
- **qrcode**: QRコード生成
- **Pillow**: 画像処理
- **functions-framework**: Cloud Functionsローカル開発環境
- **google-cloud-storage**: GCSとの連携

### APIと連携
- **Notion API**: ページへのコンテンツ追加
- **Google Cloud Storage API**: 画像ファイル保存と公開URL生成

### 開発ツール
- **gcloud CLI**: デプロイと管理
- **Git**: バージョン管理

## セットアップと展開方法

1. Notion API統合の設定 (詳細は `Notion API 統合セットアップ.md` 参照)
2. GCPプロジェクトの設定
3. Cloud Functionsのデプロイ (詳細は `Cloud Functions デプロイ手順.md` 参照)

## 使用方法

デプロイされたCloud FunctionsのエンドポイントにPOSTリクエストを送信します：

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"page_id": "YOUR_PAGE_ID", "data": "https://example.com", "caption": "Webサイトへのリンク"}' \
  https://REGION-PROJECT_ID.cloudfunctions.net/add_qr_code
```

## ライセンス

MITライセンス

## 貢献方法

1. リポジトリをフォーク
2. 機能ブランチを作成 (`git checkout -b feature/amazing-feature`)
3. 変更をコミット (`git commit -m 'Add some amazing feature'`)
4. ブランチにプッシュ (`git push origin feature/amazing-feature`)
5. プルリクエストを開く

## プロジェクト構造

```
notion-qr-tool/
├── main.py          # Cloud Functions エントリーポイント
├── requirements.txt # 依存関係
├── README.md        # このファイル
└── docs/            # ドキュメント
    ├── notion-integration.md
    └── deployment-instructions.md
```