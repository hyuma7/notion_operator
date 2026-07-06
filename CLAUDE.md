# notion_operator

Notion連携のラベル印刷・データ出力デスクトップアプリ（Python + Flet、PyInstallerでビルド）。
recycle-system モノリポのサブモジュールとして使われる。

## ブランチ戦略

- **dev** — 作業ブランチ。日常のコミット・push はすべてここ。親リポジトリの `.gitmodules` も dev を追跡している
- **main** — 安定ブランチ。dev からのマージのみ（直接コミットしない）
- feature ブランチは任意。作ったら dev にマージする

## リリース手順（アプリ配布・自動アップデート）

バージョンの唯一のソースは `version.py` の `__version__`。詳細は [docs/AUTO_UPDATE.md](docs/AUTO_UPDATE.md)。

1. `version.py` の `__version__` を上げる（`pyproject.toml` の version も同じ値に揃える）
2. dev にコミットして push
3. タグを push（**タグとversion.pyが一致しないとCIが落ちる**）:

   ```bash
   git tag v0.4.3
   git push origin v0.4.3
   ```

4. GitHub Actions（`.github/workflows/release.yml`）が macOS / Windows をビルドして
   GitHub Release に添付する。`gh run watch` で通過を確認すること
5. 配布済みアプリは起動時に releases/latest を照会し、設定タブ（起動エラー時はエラータブ）から自己更新する

## main への push（リリース確定後の運用）

リリースが実機で問題ないことを確認したら main を dev に追従させる:

```bash
git checkout main
git pull origin main
git merge dev
git push origin main
git checkout dev
```

その後、親リポジトリ（recycle-system）でサブモジュール参照を更新:

```bash
cd ..   # recycle-system 直下
git add notion_operator
git commit -m "chore: notion_operator サブモジュール参照を更新（vX.Y.Z）"
git push origin main
```

## 開発メモ

- テスト: `uv run --with pytest pytest tests/ -q`（コミット前に全通過を確認）
- ローカル起動: `uv run python main.py`
- ビルド済みアプリの設定・ログ: `~/Library/Application Support/Notion Operator/`（mac）
- アプリは未署名（ad-hoc署名のみ）。初回配布をブラウザ経由で渡すと quarantine で
  ブロックされるので `右クリック→開く` を案内する。自動アップデート経由は問題ない
