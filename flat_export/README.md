# Flat在庫管理システム - Excel出力

Notionデータベースから「売却済み」の物件データを取得し、Excelファイルとして出力するStreamlitアプリケーションです。

## 機能

- 年月による期間指定
- 「在庫状態」が「売却済み」のデータのみをフィルタリング
- 取得データのプレビュー表示
- Excel形式でのエクスポート

## セットアップ

1. 必要なパッケージをインストール:
```bash
pip install -r requirements.txt
```

2. 環境変数を設定:
`.env.example`を`.env`にコピーして、以下の値を設定してください:
```
NOTION_API_KEY=your_notion_api_key_here
NOTION_DATABASE_ID=your_database_id_here
```

## 実行方法

```bash
cd flat_export
streamlit run app.py
```

## 使い方

1. アプリを起動すると、ブラウザが自動的に開きます
2. 年と月を選択
3. 「データを取得」ボタンをクリック
4. データプレビューを確認
5. 「Excelファイルをダウンロード」ボタンでエクスポート

## 注意事項

- Notionデータベースには以下のプロパティが必要です:
  - `在庫状態`: セレクトプロパティ（「売却済み」オプションを含む）
  - `売却日`: 日付プロパティ
- プロパティ名が異なる場合は、`app.py`内の該当箇所を修正してください
