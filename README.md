# notion_operator

NotionのAPIとPythonを使用して各種業務を自動化するためのリポジトリです。

## 機能一覧

### メインアプリ: Brother QL プリンター連携 (local_server/)
- ローカルプロキシサーバー
- ラベル印刷機能
- Notion連携・データエクスポート
- Flet UIで操作

### Cloud Functions (func/)
- QRコード生成・Notionページ追加
- サーバーレス実行

## 技術スタック

- **言語**: Python 3.10+
- **UI**: Flet
- **API**: Notion API, Flask
- **クラウド**: Google Cloud Platform (Cloud Functions, Cloud Storage)

## プロジェクト構造

```
notion_operator/
├── local_server/           # メインアプリ
│   ├── run_proxy.py        # エントリポイント
│   ├── brother_ql_proxy/   # プリンター連携コード
│   └── requirements.txt
├── func/                   # Cloud Functions
│   ├── add_qr_info_code/
│   └── qr_print/
├── flat_export/            # エクスポート関連
├── docs/                   # ドキュメント
└── requirements.txt        # 全体の依存関係
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
cd local_server
python run_proxy.py
```

詳細は `local_server/README.md` と `local_server/SETUP.md` を参照してください。

## ライセンス

MIT License
