# 設計: 年間集計（財務集計）の仕入れ集計を「仕入れ日」ベースに変更

対象: `brother_ql_proxy/ui/export/`（年間ピボット＝「財務集計」Excel エクスポート）
日別エクスポート（`generate_daily_excel` / `pdf_service.py` / ui.py の日別セクション）には**一切手を触れないこと**。別作業者が同時に改修中。

## 背景と目的

現状の年間集計の仕入れ（入庫）側には次の問題がある。

1. 帰属月が Notion ページの **Created time**（登録日時）で決まる。実際の入庫日と登録日がずれると計上月がずれる。DB には日付プロパティ **「仕入れ日」** が存在する（`docs/商品管理テーブル項目一覧.md` 参照）ので、これを使うべき。
2. `fetch_purchase_data` が **DB の全アイテムを無フィルタで取得**してからローカルで期間フィルタしている。Notion API は遅いので、サーバーサイドフィルタで必要な分だけ取得したい。
3. 仕入データが 0 件のときだけ売却レコードから仕入高を計算する**フォールバックがある**（`service.py` の `process_pivot_data` 内）。件数によって仕様が変わるのは混乱の元なので**フォールバックごと削除**する。
4. シート先頭の「全体合算」ブロックに**「仕入高」行を追加**する。既存の「原価」行（売却月ベースの売上対応原価）はそのまま残す。

## 変更内容

### 1. `schemas.py` — `PurchaseRecord.purchase_date` のエイリアス変更

```python
# 変更前
purchase_date: Optional[datetime] = Field(alias="Created time", default=None)
# 変更後
purchase_date: Optional[date] = Field(alias="仕入れ日", default=None)
```

- 型は `SoldRecord.sold_date`（alias="売却日"）に合わせて `Optional[date]` にする。
  `_flatten_notion_page` は date プロパティを `start` 文字列（例 `"2025-07-01"`）で返すので pydantic がそのままパースできる。
- `datetime` import が他で未使用になったら整理する（DailyRecord 等が使っていれば残す）。
- `Created time` → `row["Created time"]` のマッピング（`_flatten_notion_page` 冒頭）は他スキーマが使う可能性があるため**削除しない**。

### 2. `service.py` — `fetch_purchase_data` をサーバーサイドフィルタ化

変更前: 無フィルタで全件取得 → ローカルで `created_time` を期間フィルタ。

変更後:

```python
query_params = {
    "database_id": self.database_id,
    "filter": {
        "and": [
            {"property": "仕入れ日", "date": {"on_or_after": start_date}},
            {"property": "仕入れ日", "date": {"before": end_date}},
        ]
    },
    "page_size": 100,
}
```

- ローカルの `created_time` フィルタ（`pd.to_datetime` での `start_dt`/`end_dt` 比較ブロック）は**丸ごと削除**。
- 帰属月の計算は既存どおり `record.purchase_date` から `purchase_year_month` を組み立てる（エイリアス変更により自動的に仕入れ日ベースになる）。
- `purchase_date is None` のレコードはフィルタにより来ないはずだが、既存の `if record.purchase_date:` ガードは残してよい。
- **仕様上の注意（ドキュメント化のみ、コードは不要）**: 仕入れ日が未入力のアイテムは集計対象外になる。これは意図した仕様。

### 3. `service.py` — API 取得の軽量化（filter_properties）

`PurchaseRecord` が必要とするプロパティだけを返させて転送量を削る。

- 必要プロパティ: `仕入れ原価` / `仕入れ先名` / `仕入先カテゴリ` / `作業担当` / `仕入れ日`
- Notion API では `POST /databases/{id}/query?filter_properties=<property_id>&filter_properties=...` のように**クエリ文字列**で渡す（body ではない点に注意）。値はプロパティ名ではなく **property ID**。
- 実装方針:
  1. `GET databases/{database_id}`（`self.notion.request(path=..., method="GET")`）を 1 回呼び、`properties` からプロパティ名 → id のマップを作るヘルパー `_get_property_ids(names: List[str]) -> List[str]` を追加。結果はインスタンス変数にキャッシュ。
  2. `_query_with_retry` に省略可能引数 `filter_properties: Optional[List[str]] = None` を追加し、指定時は `path` に `?filter_properties=<id>` を URL エンコードして連結（複数はパラメータ繰り返し）。
  3. `fetch_purchase_data` からのみ使用する。`fetch_sales_data` は今回スコープ外（変更しない）。
- **フェイルセーフ**: プロパティ ID の取得に失敗した場合（プロパティ名変更など）は `filter_properties` なしで全プロパティ取得にフォールバックし、動作は継続すること（ここは「取得の最適化」であり仕様ではないため）。ログ or print で警告を出す。

### 4. `service.py` — `process_pivot_data` のフォールバック削除

```python
# 削除対象（現 436〜440 行あたり）
elif not df_sales.empty:
    # Fallback: calculate purchase cost from sales records (legacy behavior)
    pivot_purchase = df_sales.pivot_table(index='supplier', columns='sold_year_month', values='cost_price', aggfunc='sum', fill_value=0)
    purchase_company_category_map = {k: v for k, v in company_category_map.items()}
```

- 仕入データが 0 件なら `pivot_purchase` は空のまま。`generate_excel` は空ピボットのセクションをスキップする既存実装（`if pivot is None or pivot.empty: continue`）なので追加対応不要。

### 5. `service.py` — `generate_excel` の「全体合算」に「仕入高」行を追加

- `summary_items` を `["売上", "原価", "粗利", "販売手数料", "送料", "販売利益", "仕入高"]` にする（仕入高は最終行）。
- 「仕入高」だけはデータ源が違う: `data['purchase_records']`（DataFrame）を `purchase_year_month` でグルーピングし `cost_price` を月別合計する。他の行は従来どおり売却レコード起点。
- 現状この合算ブロックは `df_sales` が空だと丸ごとスキップされる。ガードを「**売上か仕入のどちらかがあれば描画**」に変更し、売上ゼロ月・仕入ゼロ月は 0 表示とする。売上ループ・仕入ループそれぞれ空 DataFrame ガードを入れること。
- 行の書式（`total_fill`、`#,##0`、右端の「計」列）は既存行と同じ。

### 6. テスト更新（`tests/test_property_fetch.py` ほか）

- `test_Created_timeがpurchase_dateにマッピングされる` → 「仕入れ日がpurchase_dateにマッピングされる」に書き換え。テストデータに date プロパティ `仕入れ日` を追加する。
- 550 行付近の統合系テスト（`created_time="2025-09-05..."` で purchase_date を検証しているもの）も同様に `仕入れ日` プロパティ基準へ修正。
- 追加すべきテスト:
  - `fetch_purchase_data` が `仕入れ日` の date フィルタ付きクエリを組み立てること（`_query_with_retry` をモックして query_params を検証）。
  - フォールバック削除の確認: purchases 空 + sales ありのとき `pivot_purchase` が空であること。
  - 「全体合算」に「仕入高」行が出力され、値が purchase_records の月別 cost_price 合計と一致すること（openpyxl で読み戻して検証、既存テストのスタイルに合わせる）。
  - `_get_property_ids` の名前→ID 解決と、解決失敗時に filter_properties なしで続行すること。
- 実行: `uv run --with pytest pytest tests/ -q`（全通過を確認）。

## 触ってはいけない場所（コンフリクト回避）

- `ui.py` — 変更不要のはず。年間側の呼び出しシグネチャは変えないこと（`fetch_purchase_data(start, end)` / `process_pivot_data(...)` / `generate_excel(...)` のインターフェース維持）。
- `pdf_service.py`、日別エクスポート関連（`fetch_daily_data` 系、`DailyRecord`、`generate_daily_excel`）— 別作業者が改修中。**diff に含めない**。
- `EXCEL_EXPORT_SPEC.md` に年間集計の記載があれば「仕入れ日ベース」「仕入高行」「フォールバック廃止」を反映して更新する。

## コミット方針

- ブランチ: `dev`（このリポジトリの運用どおり）
- この変更のみで 1 コミット。メッセージ例:
  `feat: 年間集計の仕入れを「仕入れ日」ベースに変更（サーバーフィルタ化・仕入高行追加・フォールバック削除）`
- version.py は触らない（リリースは別途）。
