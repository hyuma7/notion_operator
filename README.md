# Brother QL プリンタープロキシサーバー

ローカルネットワーク内のBrother QLプリンターをインターネット経由でアクセス可能にするプロキシサーバーです。

## 必要な環境

- Python 3.8以上

## セットアップ

### 1. 依存関係のインストール

```bash
pip install -r requirements.txt
```

または個別にインストール:
```bash
pip install flet flask flask-cors requests Pillow qrcode pystray pyngrok werkzeug notion-client pandas openpyxl
```

### 2. アプリケーションの起動

```bash
cd local_server
python run_proxy.py
```

Macアプリとして配布する場合の手順は [docs/MAC_APP_BUILD.md](docs/MAC_APP_BUILD.md) を参照してください。

## 使用方法

### ステータスタブ
- サーバーの開始/停止
- プリンター接続状態の確認
- Webインターフェースへのアクセス

### 設定タブ
- プリンターIP/ポートの設定
- プロキシサーバーポートの設定
- ngrok設定（外部アクセス用）

### ログタブ
- システムの動作ログを確認

### エクスポートタブ
- Notion連携・データエクスポート

## API エンドポイント

- `GET /` - Webインターフェース
- `GET /status` - ステータス確認
- `POST /print/raw` - 生データ印刷
- `POST /print/label` - ラベル印刷

## トラブルシューティング

### プリンターに接続できない
1. プリンターのIPアドレスが正しいか確認
2. プリンターとPCが同じネットワークにあるか確認
3. ファイアウォールでポート9100がブロックされていないか確認

### ngrokが動作しない
1. ngrok認証トークンが正しく設定されているか確認
2. pyngrokがインストールされているか確認

### ImportError が発生する場合
```bash
python -m pip install --upgrade -r requirements.txt
```

## ライセンス

MIT License
