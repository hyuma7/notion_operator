# 自動アップデート機能

GitHub Releases を配布元として、アプリが自分で新バージョンを確認・ダウンロード・置き換えする。

## 仕組み

```
タグ push (v0.4.1)
   └→ GitHub Actions が macOS / Windows 両方をビルドし Release に添付
        └→ アプリ起動時に releases/latest を照会（バックグラウンド）
             └→ 新バージョンあり → スナックバー通知 + 設定タブに更新ボタン
                  └→ zip ダウンロード → sha256 検証 → ヘルパースクリプトが
                     アプリ終了を待って .app / .exe を差し替え → 自動再起動
```

- 更新チェックは起動時（失敗は無視）と、設定タブの「アップデートを確認」ボタン
- 置き換え対象は mac が `.app` バンドル丸ごと、Windows が `.exe` 1ファイル
- ソース実行（`python main.py`）では確認のみで自動更新は無効

## リリース手順

1. `version.py` の `__version__` を上げる（例: `0.4.1`）
2. コミットして push
3. タグを打って push:

   ```bash
   git tag v0.4.1
   git push origin v0.4.1
   ```

タグとバージョンが一致しないと CI が落ちる。あとは Actions が
`NotionOperator-0.4.1-macos-arm64.zip` / `NotionOperator-0.4.1-windows-x64.zip`
（+ それぞれの `.sha256`）を Release に添付する。

## セキュリティまわりの注意

自動更新経由では OS の警告は出ない。quarantine 属性（mac）や
Mark of the Web（Windows SmartScreen）はブラウザ経由のダウンロードでしか
付かず、アップデーターは Python の HTTP で取得するため対象外。
mac 側は保険としてヘルパースクリプト内で `xattr -dr com.apple.quarantine` も実行する。

**初回配布のみ**手動対応が必要:

- mac: ブラウザで落とした zip は quarantine 付き。`右クリック → 開く`、
  または `xattr -dr com.apple.quarantine "Notion Operator.app"`
- Windows: SmartScreen が出たら `詳細情報 → 実行`。
  Defender が誤検知した場合は除外設定に追加

## 実機での更新テスト手順

リリースフローを初めて動かすときは以下で通しの動作確認をする:

1. `version.py` を `0.4.0` のまま `v0.4.0` をタグ push → Release ができることを確認
2. その Release の zip からアプリを起動（旧バージョン扱いにするため、
   一時的に `version.py` を `0.3.x` に下げてビルドしたものでもよい）
3. `version.py` を `0.4.1` に上げて `v0.4.1` をタグ push
4. 手元のアプリで「アップデートを確認」→ 更新 → 自動再起動後、
   AppBar のバージョン表示が `v0.4.1` になっていることを確認

## 関連ファイル

- `version.py` — バージョン定義（唯一のソース）
- `updater/checker.py` — GitHub API 照会・バージョン比較
- `updater/downloader.py` — ダウンロード・sha256 検証
- `updater/installer.py` + `_install_mac.py` / `_install_win.py` — 置き換え処理
- `updater/ui.py` — 設定タブのカードと起動時チェック
- `.github/workflows/release.yml` — リリースビルド
