# notion_operator

NotionのAPIとPythonを使用して色々なことを実現するためのリポジトリです。

## Flat在庫管理システム

Notionデータベースから「売却済み」の物件データを取得し、Excelファイルとして出力するStreamlitアプリケーションです。

### 機能

- 📅 年月による期間指定
- 🔍 「在庫状態」が「売却済み」のデータのみをフィルタリング
- 📊 取得データのプレビュー表示
- 💾 Excel形式でのエクスポート

### セットアップ

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

### Notion APIキーの取得方法

1. [Notion Integrations](https://www.notion.so/my-integrations)にアクセス
2. 「New integration」をクリック
3. インテグレーション名を入力し、「Submit」をクリック
4. 「Internal Integration Token」をコピーして`.env`ファイルに設定

### データベースIDの取得方法

1. Notionでデータベースを開く
2. URLから以下の部分をコピー:
   `https://www.notion.so/workspace/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx?v=...`
   `xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`の部分がデータベースIDです
3. データベースをインテグレーションと共有（データベースの右上「...」→「Add connections」→作成したインテグレーションを選択）

### 実行方法

```bash
streamlit run app.py
```

### 使い方

1. アプリを起動すると、ブラウザが自動的に開きます
2. 年と月を選択
3. 「データを取得」ボタンをクリック
4. データプレビューを確認
5. 「Excelファイルをダウンロード」ボタンでエクスポート

### 注意事項

- Notionデータベースには以下のプロパティが必要です:
  - `在庫状態`: セレクトプロパティ（「売却済み」オプションを含む）
  - `売却日`: 日付プロパティ
- プロパティ名が異なる場合は、`app.py`内の該当箇所を修正してください

### トラブルシューティング

- **データが取得できない場合**:
  - Notion APIキーとデータベースIDが正しく設定されているか確認
  - データベースがインテグレーションと共有されているか確認
  - プロパティ名が正しいか確認

- **エラーが表示される場合**:
  - 環境変数が正しく読み込まれているか確認
  - 必要なパッケージがすべてインストールされているか確認
