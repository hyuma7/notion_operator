# Brother QL プリンタープロキシ セットアップガイド

## 必要な環境

- Python 3.8以上
- pip (Pythonパッケージマネージャー)

## インストール手順

### 1. 必要なパッケージをインストール

```bash
# Windows
pip install flet flask flask-cors requests Pillow qrcode pystray pyngrok werkzeug

# macOS/Linux
pip3 install flet flask flask-cors requests Pillow qrcode pystray pyngrok werkzeug
```

### 2. アプリケーションの実行

```bash
# local_server ディレクトリに移動
cd local_server

# アプリケーションを起動
python run_proxy.py

# または
python3 run_proxy.py
```

## トラブルシューティング

### ImportError が発生する場合

1. **Pythonのバージョン確認**
   ```bash
   python --version
   python3 --version
   ```

2. **pipの確認**
   ```bash
   pip --version
   python -m pip --version
   ```

3. **パッケージの再インストール**
   ```bash
   python -m pip install --upgrade flet flask flask-cors requests Pillow qrcode pystray pyngrok werkzeug
   ```

### 仮想環境を使用する場合

```bash
# 仮想環境の作成
python -m venv brother_ql_env

# 仮想環境の有効化
# Windows
brother_ql_env\Scripts\activate
# macOS/Linux
source brother_ql_env/bin/activate

# パッケージのインストール
pip install flet flask flask-cors requests Pillow qrcode pystray pyngrok werkzeug

# アプリケーションの実行
python run_proxy.py
```

## 初回設定

1. アプリケーションを起動
2. 「設定」タブでプリンターのIPアドレスを入力
3. 「設定を保存」をクリック
4. 「ステータス」タブで「接続テスト」を実行
5. 「サーバー開始」でプロキシサーバーを起動

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
- エラーやデバッグ情報の表示