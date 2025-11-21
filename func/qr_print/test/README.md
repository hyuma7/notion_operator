# QRコード付きラベル印刷システム

Notionページの情報からQRコード付きラベルを生成し、Brother QLプリンターに印刷するCloud Functionsです。

## 機能

- Notion自動化からのWebhook受信
- QRコード生成（ページ情報をJSON形式で埋め込み）
- 日本語対応ラベル生成
- Brother QLシリーズプリンターへの直接印刷
- 複数ラベルサイズ対応（62x29mm、62x100mm、62mm連続）
- エラーハンドリングとリトライ機能

## デプロイ方法

```bash
gcloud functions deploy notion-label-printer \
  --runtime python312 \
  --trigger-http \
  --allow-unauthenticated \
  --region asia-northeast1 \
  --entry-point process_notion_webhook \
  --memory 1GB \
  --timeout 300s \
  --set-env-vars NOTION_API_KEY=YOUR_NOTION_API_KEY,PRINTER_IP=192.168.1.100,PRINTER_MODEL=QL-820NWB,LABEL_SIZE=62x29
```

## 環境変数

| 変数名 | 必須 | デフォルト値 | 説明 |
|--------|------|-------------|------|
| NOTION_API_KEY | ✓ | - | Notion APIキー |
| PRINTER_IP | ✓ | 192.168.1.100 | プリンターのIPアドレス |
| PRINTER_MODEL | - | QL-820NWB | プリンターモデル |
| LABEL_SIZE | - | 62x29 | ラベルサイズ |

## サポートされるプリンター

- QL-500, QL-550, QL-560, QL-570, QL-580N
- QL-650TD, QL-700, QL-710W, QL-720NW
- QL-800, QL-810W, QL-820NWB
- QL-1050, QL-1060N

## ラベルサイズ

| サイズ | 寸法 | 用途 |
|--------|------|------|
| 62x29 | 62×29mm | 住所ラベル |
| 62x100 | 62×100mm | 宛名ラベル |
| 62 | 62mm連続 | カスタム長さ |

## 使用方法

### Notion自動化の設定

1. Notionでデータベースの自動化を作成
2. トリガー: 「ページが更新されたとき」
3. アクション: 「Webhookを送信」
4. URL: `https://REGION-PROJECT_ID.cloudfunctions.net/notion-label-printer`

### 手動テスト

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "data": {
      "id": "test-page-id",
      "url": "https://www.notion.so/Test-Item-12345",
      "icon": {"type": "emoji", "emoji": "📱"},
      "properties": {
        "Category": {"select": {"name": "電子機器"}},
        "Date": {"date": {"start": "2025-01-06"}}
      }
    }
  }' \
  https://REGION-PROJECT_ID.cloudfunctions.net/notion-label-printer
```

### ローカルテスト

```bash
cd func/qr_print
python test_local.py
```

## レスポンス形式

### 成功時
```json
{
  "status": "success",
  "message": "ラベルが正常に印刷されました",
  "label_id": "1d454e62",
  "printed_data": {
    "title": "🎮 Nintendo Switch",
    "id": "1d454e62",
    "category": "ゲーム機",
    "date": "2025-01-06"
  }
}
```

### エラー時
```json
{
  "status": "error",
  "message": "プリンターに到達できません: Connection refused"
}
```

## トラブルシューティング

### プリンター接続エラー
1. IPアドレスが正しいか確認
2. プリンターが同じネットワークにあるか確認
3. ポート9100が開いているか確認

### ラベルサイズエラー
1. プリンターにセットされているラベルサイズと環境変数が一致しているか確認
2. サポートされているサイズかどうか確認

### 日本語フォントが表示されない
- フォントファイル（NotoSansJP-Regular.otf）が正しいパスにあるか確認
- デフォルトフォントにフォールバックされる
