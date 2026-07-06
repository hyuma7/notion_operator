# Macアプリのビルド手順

## ビルド

リポジトリ直下の `notion_operator` で実行します。

```bash
uv run --with pyinstaller flet pack main.py \
  --name "Notion Operator" \
  --product-name "Notion Operator" \
  --product-version 0.1.0 \
  --bundle-id com.hyuma7.notion-operator \
  --distpath dist \
  --hidden-import selenium.webdriver.chrome.webdriver \
  --hidden-import selenium.webdriver.chrome.options \
  --hidden-import selenium.webdriver.chrome.service \
  --hidden-import selenium.webdriver.common.by \
  --hidden-import selenium.webdriver.common.keys \
  --hidden-import selenium.webdriver.support.ui \
  --hidden-import selenium.webdriver.support.expected_conditions \
  --hidden-import webdriver_manager.chrome \
  --hidden-import webdriver_manager.core.driver_cache \
  -y
```

成果物は以下に作成されます。

- `dist/Notion Operator.app`
- `dist/Notion Operator`

配布用zipは以下で作成します。

```bash
ditto -c -k --sequesterRsrc --keepParent \
  "dist/Notion Operator.app" \
  "dist/Notion Operator-macos-arm64.zip"
```

## 起動確認

```bash
codesign --verify --deep --strict --verbose=2 "dist/Notion Operator.app"
open -n "dist/Notion Operator.app"
```

画面に `ラベル印刷`、`Excel出力`、`領収書`、`設定` のタブが表示されれば正常です。

## 設定ファイルとログ

Macアプリとして起動した場合、設定とログは以下に保存されます。

```text
~/Library/Application Support/Notion Operator/printer_proxy_config.json
~/Library/Application Support/Notion Operator/printer_proxy.log
```

コードから起動する場合は、従来どおりリポジトリ直下の以下を使います。

```text
printer_proxy_config.json
printer_proxy.log
```

`NOTION_OPERATOR_CONFIG_FILE` または `NOTION_OPERATOR_LOG_FILE` を指定すると保存先を上書きできます。

## 注意

FinderやLaunchServicesから `.app` を起動すると、作業ディレクトリがリポジトリ直下とは限りません。設定・ログを相対パスだけで扱うと、`/printer_proxy.log` の作成に失敗してタブ初期化が止まり、Fletの枠だけ表示される状態になります。
