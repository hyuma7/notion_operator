# Flat在庫管理システム - Notionデータベース設計書

## データベース基本情報

- **データベース名**: 商品一覧
- **データベースID**: `1d254e6206d881bb9e88d2e7ffb90444`
- **作成日**: 2025-04-11
- **最終更新日**: 2025-11-07
- **データベースURL**: https://www.notion.so/1d254e6206d881bb9e88d2e7ffb90444

## プロパティ構造詳細

### 1. 基本情報プロパティ

| プロパティ名 | プロパティID | 型 | 説明 |
|------------|-------------|-----|------|
| 商品名 | title | title | 商品の名前(タイトルプロパティ) |
| ID | hSa~ | unique_id | 自動生成ID(接頭辞: PDT) |
| 商品ID | Ctit | number | 商品管理用数値ID(円形式) |
| 製番 | iUpx | rich_text | 製造番号 |
| 写真 | \CbYx | files | 商品画像ファイル |
| 備考 | ucC^ | rich_text | その他特記事項 |
| 作成日時 | vuV? | created_time | レコード作成日時(自動) |
| 作業担当 | likS | people | 担当者 |

### 2. 在庫管理プロパティ

| プロパティ名 | プロパティID | 型 | 説明 | 重要度 |
|------------|-------------|-----|------|--------|
| **在庫状況** | qFjR | status | 商品の在庫状態 | ⭐️⭐️⭐️ |

#### 在庫状況の値一覧

| ステータス名 | ステータスID | カラー | グループ | 説明 |
|------------|-------------|--------|---------|------|
| 入庫中 | ed9a4ef2-3f5a-4535-b9a8-27cd694a108b | blue | To-do | 入庫処理中 |
| 販売中 | a~Ra | blue | In progress | 現在販売中 |
| 販売待機中 | lGje | yellow | In progress | 販売準備中 |
| 減額中 | ~x>T | pink | In progress | 価格調整中 |
| 状態確認中 | d8549072-e174-43a2-8bc5-f1427035e94f | purple | In progress | 商品状態チェック中 |
| 梱包中 | RB={ | orange | In progress | 発送準備中 |
| 返品中 | yHK\| | red | Complete | 返品処理中 |
| 廃棄 | P?{y | gray | Complete | 廃棄済み |
| **売却済み** | 4c93b9e7-6e8f-4228-a827-fc3e50e8002b | green | Complete | 販売完了 |

### 3. 日付プロパティ

| プロパティ名 | プロパティID | 型 | 説明 |
|------------|-------------|-----|------|
| 仕入れ日 | \A;G | date | 商品を仕入れた日付 |
| **売却日** | \ep:H | date | 商品が売却された日付 |

### 4. 金額関連プロパティ

| プロパティ名 | プロパティID | 型 | フォーマット | 説明 |
|------------|-------------|-----|------------|------|
| 仕入れ金 | QpJZ | number | yen | 商品の仕入れ価格 |
| 売上金 | sduA | number | yen | 商品の販売価格 |
| 送料 | hHuS | number | yen | 配送料金 |
| 仕入れ手数料 | Vk\[O | formula | yen | 計算: 仕入れ金 × 仕入れ手数料率 |
| 販売手数料 | ExUw | formula | yen | 計算: 売上金 × 販売手数料率(送料計算方法により変動) |
| 仕入れ原価 | YH{X | formula | yen | 計算: 仕入れ金 + 仕入れ手数料 |
| 純利益 | yFVX | formula | yen | 計算: 売上金 - 仕入れ原価 - 販売手数料 - 送料 |
| 利益率 | ?~@b | formula | percent | 計算: (純利益 / 売上金) × 100 |

### 5. 商品情報プロパティ(Relationによる参照)

| プロパティ名 | プロパティID | 型 | 参照元 | 説明 |
|------------|-------------|-----|--------|------|
| 型番 | Os?> | relation | 型番マスタDB | 商品の型番情報へのリレーション |
| 型番名 | WR>E | rollup | 型番.製品番号 | 型番の名称 |
| メーカー | w_cR | rollup | 型番.メーカー | メーカー名 |
| カテゴリー | E^^` | rollup | 型番.カテゴリー | 商品カテゴリー |
| サイズ | U\~o | rollup | 型番.サイズ | 商品サイズ |
| 年式 | GFV\ | rollup | 型番.年式 | 製造年式 |
| 接続方法 | KrQm | rollup | 型番.接続方法 | 接続方式 |
| 説明文 | :\\_K | rollup | 型番.商品説明 | 商品説明テキスト |
| 説明文HTML | SAgD | rollup | 型番.商品説明HTML | HTML形式の説明文 |
| 画像URL | AGya | rollup | 型番.アルバムURL | 商品画像のURL |

### 6. その他プロパティ

| プロパティ名 | プロパティID | 型 | 説明 |
|------------|-------------|-----|------|
| ランク | r@{H | select | 商品ランク(A/B/C/D/E) |
| 送料計算方法 | ;uBW | select | メルカリ家財便 or 通常 |
| 寸法/インチ | ERBQ | number | サイズ(インチ) |
| 追加説明文 | aHGM | rich_text | 追加の説明文 |
| 伝票番号 | Qefh | email | 配送伝票番号 |
| 購入者名 | VV@B | email | 購入者の名前 |

## データ取得時の注意点

### ⚠️ プロパティ名の正確な指定

**重要**: APIでデータを取得する際は、以下の正確なプロパティ名を使用する必要があります。

| ❌ 誤った名前 | ✅ 正しい名前 | 型 |
|-------------|-------------|-----|
| 在庫状態 | **在庫状況** | status |
| 販売日 | **売却日** | date |

### フィルタリング例

#### 売却済み商品の取得(正しい方法)

```python
results = notion.databases.query(
    database_id=database_id,
    filter={
        "property": "在庫状況",  # ⭐️ 正しいプロパティ名
        "status": {             # ⭐️ 型は status
            "equals": "売却済み"
        }
    }
)
```

#### 特定期間の売却済み商品取得

```python
results = notion.databases.query(
    database_id=database_id,
    filter={
        "and": [
            {
                "property": "在庫状況",
                "status": {
                    "equals": "売却済み"
                }
            },
            {
                "property": "売却日",
                "date": {
                    "on_or_after": "2025-01-01"
                }
            },
            {
                "property": "売却日",
                "date": {
                    "before": "2025-02-01"
                }
            }
        ]
    }
)
```

## リレーション先データベース

### 型番マスタデータベース
- **データベースID**: `1d754e62-06d8-8107-825a-c4b8fe24d57f`
- **データソースID**: `1d754e62-06d8-81fd-bc67-000b1d94db88`
- **関係**: Single Property(1対1)

## 数式の詳細

### 販売手数料の計算ロジック

```
if(送料計算方法 == "メルカリ家財便",
  (売上金 - 送料) × 販売手数料率,
  売上金 × 販売手数料率
)
```

### 純利益の計算ロジック

```
round(売上金 - 仕入れ原価 - 販売手数料 - 送料, 0)
```

### 利益率の計算ロジック

```
if(売上金 > 0,
  round(((売上金 - 仕入れ金 - 仕入れ手数料 - 販売手数料) / 売上金) × 100, 2) + "%",
  "0%"
)
```

## データ型の対応表

| Notion型 | Python処理 | 説明 |
|----------|-----------|------|
| title | text[0]["plain_text"] | タイトルプロパティ |
| rich_text | rich_text[0]["plain_text"] | リッチテキスト |
| number | number | 数値 |
| select | select["name"] | 単一選択 |
| status | status["name"] | ステータス |
| date | date["start"] | 日付 |
| people | people[]["name"] | ユーザー |
| files | files[]["name"] | ファイル |
| email | email | メールアドレス |
| formula | formula["string"]/["number"] | 数式(結果型による) |
| rollup | rollup["array"] | ロールアップ |
| relation | relation[]["id"] | リレーション |
| unique_id | unique_id["prefix"] + unique_id["number"] | ユニークID |
| created_time | created_time | 作成日時 |

## 更新履歴

| 日付 | 内容 |
|------|------|
| 2025-11-21 | 初版作成 - データベース構造解析完了 |

---

**作成者**: Hyuma  
**部署**: AD3部  
**目的**: Flat在庫管理システムのNotion連携開発
