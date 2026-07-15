# 財務集計 Excel エクスポート

Notion の商品一覧データベースから売上・仕入データを取得し、企業別・月別に集計した
Excel（`財務集計` シート）を出力する機能のドキュメント。

実装: `brother_ql_proxy/ui/export/service.py`（`ExportService.process_pivot_data` /
`ExportService.generate_excel`）、スキーマ: `brother_ql_proxy/ui/export/schemas.py`。
日別出力（`generate_daily_excel`）は別機能で、本ドキュメントの対象外。

---

## シート構成（`財務集計`）

上から順に次のブロックを縦に並べて出力する。

### 1. 全体合算

売却レコード（在庫状況=売却済み・売却日ベース）から集計する売上ベースの合算表。
行は次の 6 項目。列は開始月から 12 ヶ月分＋「計」列。

| 行 | 内容 |
|----|------|
| 売上 | 売却レコードの売上金の月別合計（生値） |
| 原価 | 仕入れ原価の月別合計（生値） |
| 粗利 | **Excel 数式** `= 売上 − 原価` |
| 販売手数料 | 販売手数料の月別合計（生値） |
| 送料 | 配送料の月別合計（生値） |
| 販売利益 | **Excel 数式** `= 粗利 − 販売手数料 − 送料` |

- 「計」列は各行とも **Excel 数式** `=SUM(先頭月:最終月)`。
- 粗利・販売利益・計列を数式にしているため、フィルタや手修正が Excel 上で追随する。
- 全体合算ブロックは**売上（売却レコード）がある場合のみ**描画される
  （`generate_excel` の `if has_sales:`）。

### 2. 企業別セクション

`generate_excel` の `sections` リストの順に出力する。各セクションは
企業（販売媒体 / 仕入れ先）行 → 担当者計・カテゴリ計 → 合計、の構成。
月別セルは生値、「計」列は `=SUM(...)` 数式。

- 企業別売上（市場・業販）
- 企業別販売利益（市場・業販）
- 企業別売上（小売り）
- 企業別販売利益（小売り）
- 企業別仕入高（仕入れ先ごと・仕入れ日ベース。カテゴリ小計付き）

売上・販売利益は**販売媒体**を対象に「市場・業販」と「小売り」に分けて集計する。
仕入高は**仕入れ先**を対象に集計する（小売りカテゴリは除外）。

---

## 2026-07-15 の変更内容

### 全体合算の数式化

粗利・販売利益・計列を生値から Excel 数式に変更した（`粗利=売上−原価`、
`販売利益=粗利−販売手数料−送料`、`計=SUM(各月)`）。

- **注意**: Notion 側の「販売利益」プロパティの単純合計とは、各レコードの丸め処理の
  積み重ねにより数十円ずれることがある。全体合算の数式は月別合算値どうしの引き算なので、
  レコード単位で丸めた Notion の合計とは一致しないことがある（仕様）。

### 全体合算から「仕入高」行を削除

全体合算は売却レコードベースの項目のみに整理し、「仕入高」行を廃止した。
仕入は従来どおり「企業別仕入高」セクションで集計・出力する（このセクションは存続）。
これに伴い、全体合算ブロックの描画条件を `if has_sales or has_purchases:` から
`if has_sales:` に変更した（売上がある場合のみ描画）。

### 企業別粗利ピボットを計算に追加（シート出力は見送り）

`process_pivot_data` に販売媒体の粗利ピボットを追加した:

- `pivot_gross_wholesale`（市場・業販）
- `pivot_gross_retail`（小売り）
- `category_gross_wholesale`（市場・業販のカテゴリ小計）

これらの**計算と返り値は残している**が、シートへの出力は現状**見送り**にしている。
再有効化する場合は、`generate_excel` の `sections` リストに次の 2 エントリを
該当位置（各販売利益セクションの直前）に追加するだけでよい:

```python
("企業別粗利(市場・業販)", data.get('pivot_gross_wholesale'), data.get('category_gross_wholesale')),
("企業別粗利(小売り)", data.get('pivot_gross_retail'), None),
```

### 販売側カテゴリのハードコードから「ネット」を削除

`process_pivot_data` の `wholesale_categories` を `{'市場', '業販', 'ネット'}` から
`{'市場', '業販'}` に変更した。**販売先一覧のカテゴリは「業販」「市場」「小売り」のみ**で、
販売側に「ネット」は存在しないため。
一方、**仕入側のカテゴリ「市場」「業販」「ネット」「その他」の「ネット」は正当**なので、
仕入側の集計では存続させている（`purchase_category_list` は小売りのみ除外）。

### 開始月のデフォルトと永続化

- 開始月のデフォルトを **2026 年 6 月** にした。
- 選択した開始月を config（`pivot_start_month`、`"YYYY-MM"` 形式）に永続化する
  （`brother_ql_proxy/core/config.py` の `DEFAULT_CONFIG`、UI は
  `brother_ql_proxy/ui/export/ui.py` の `_load_pivot_start_date` / `on_pivot_date_change`）。
  値が無い・不正な場合は 2026 年 6 月にフォールバックする。

### relation 二重リンク時は先頭値を採用する防御を追加

Notion の rollup が複数値を返し `_flatten_notion_page` が `", "` で join した場合に備え、
`SoldRecord` / `PurchaseRecord` の企業名（`supplier` / `sales_channel`）と
カテゴリ（`supplier_category` / `sales_channel_category`）は、URL 除去後に `","` が
含まれていれば**先頭の値のみ**を採用するようにした（企業名は空になったら「不明」、
カテゴリは空になったら「その他」）。

- **原因事例**: 商品「ドラム式洗濯機」（仕入れ日 2026-06-19、仕入れ原価 3,540 円、
  <https://app.notion.com/p/38754e6206d880b58abff3c63189dd3e>）の「仕入れ先」relation が
  仕入れ先一覧の「RE」と「REO」の 2 ページに二重リンクされていた。
  そのため rollup「仕入れ先名」が 2 値を返し、企業名 `"RE, REO"`・
  カテゴリ `"ネット, ネット"` という行が企業別仕入高セクションに出現していた。
  この防御により先頭値（`"RE"` / `"ネット"`）に正規化される。
- **根本対応**: これはあくまで表示上の防御であり、正しくは **Notion 側で relation を
  1 つに直す**こと。二重リンクを解消しない限り、その商品の仕入高が正しい 1 社に
  集計されない可能性がある点に注意。
- 日別出力（`DailySoldRecord` / `DailyPurchaseRecord`）にも同じ防御を適用済み
  （対象フィールド: 仕入れ先名・販売媒体名・型番名・メーカー・カテゴリー・サイズ・
  仕入先カテゴリ）。

---

## テスト

- `tests/test_export_tab.py`
  - `TestGrossProfitSection`: 全体合算の数式化・仕入高行の廃止・粗利セクション非出力・
    企業別仕入高セクションの存続を検証。
  - `TestRelationDoubleLinkNormalization`: `"RE, REO"` / `"ネット, ネット"` が
    先頭値に正規化されることを検証。
- `tests/test_property_fetch.py`
  - `TestSummaryPurchaseRow`: 全体合算に仕入高行が無いこと・売上 0 件では全体合算が
    描画されず企業別仕入高のみ出力されることを検証。

実行:

```bash
uv run --with pytest pytest tests/test_export_tab.py tests/test_property_fetch.py -q
```
