# notion_operator

NotionのAPIとPythonを使用して各種業務を自動化するためのリポジトリです。

## 機能一覧

### 1. Flat在庫管理システム (app.py)
- Notionデータベースから売却済みデータを取得
- Excel形式でエクスポート
- Streamlit UIで簡単操作

### 2. QRコード生成 (func/)
- Notionページへのカスタムのコードブロック追加
- Cloud Functions でサーバーレス実行

### 3. Brother QLプリンター連携 (local_server/)
- ローカルプロキシサーバー
- ラベル印刷機能

## 技術スタック

- **言語**: Python 3.10+
- **クラウド**: Google Cloud Platform (Cloud Functions, Cloud Storage)
- **API**: Notion API
- **UI**: Streamlit

## プロジェクト構造

```
notion_operator/
├── app.py              # Streamlit在庫管理アプリ
├── requirements.txt    # 依存関係
├── func/               # Cloud Functions
│   ├── add_qr_info_code/
│   └── qr_print/
├── local_server/       # ローカルサーバー
│   └── brother_ql_proxy/
├── flat_export/        # エクスポート関連
└── docs/               # ドキュメント
```

## セットアップ

1. 依存関係のインストール
```bash
pip install -r requirements.txt
```

2. 環境変数の設定
```bash
NOTION_API_KEY=your_api_key
NOTION_DATABASE_ID=your_database_id
```

3. アプリの起動
```bash
streamlit run app.py
```

## ライセンス

MIT License
