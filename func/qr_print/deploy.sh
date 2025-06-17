#!/bin/bash

# Google Cloud Functions デプロイスクリプト
# Notion QR Print Webhook

set -e

# 設定
FUNCTION_NAME="notion-qr-print"
REGION="asia-northeast1"  # 東京リージョン
RUNTIME="python311"
MEMORY="256MB"
TIMEOUT="60s"
SOURCE_DIR="."
ENTRY_POINT="notion_qr_webhook"

# 環境変数（実際の値に変更してください）
PRINTER_IP="${PRINTER_IP:-192.168.1.100}"
PRINTER_MODEL="${PRINTER_MODEL:-QL-820NWB}"
DEFAULT_LABEL_SIZE="${DEFAULT_LABEL_SIZE:-62x29}"

echo "🚀 Google Cloud Functions にデプロイを開始します"
echo "================================"
echo "関数名: $FUNCTION_NAME"
echo "リージョン: $REGION"
echo "ランタイム: $RUNTIME"
echo "メモリ: $MEMORY"
echo "タイムアウト: $TIMEOUT"
echo "プリンターIP: $PRINTER_IP"
echo "プリンターモデル: $PRINTER_MODEL"
echo "デフォルトラベルサイズ: $DEFAULT_LABEL_SIZE"
echo "================================"

# プロジェクト設定確認
echo "📋 現在のGCPプロジェクト:"
gcloud config get-value project

read -p "このプロジェクトでデプロイしますか? (y/N): " confirm
if [[ $confirm != [yY] ]]; then
    echo "❌ デプロイを中止しました"
    exit 1
fi

echo ""
echo "🔧 デプロイ中..."

# Cloud Functions デプロイ
gcloud functions deploy $FUNCTION_NAME \
    --gen2 \
    --runtime=$RUNTIME \
    --region=$REGION \
    --source=$SOURCE_DIR \
    --entry-point=$ENTRY_POINT \
    --trigger=http \
    --allow-unauthenticated \
    --memory=$MEMORY \
    --timeout=$TIMEOUT \
    --set-env-vars="PRINTER_IP=$PRINTER_IP,PRINTER_MODEL=$PRINTER_MODEL,DEFAULT_LABEL_SIZE=$DEFAULT_LABEL_SIZE" \
    --max-instances=10 \
    --min-instances=0

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ デプロイが完了しました!"
    echo ""
    echo "📡 関数URL:"
    gcloud functions describe $FUNCTION_NAME --region=$REGION --format="value(serviceConfig.uri)"
    echo ""
    echo "🔗 使用方法:"
    echo "POST リクエストを以下のエンドポイントに送信:"
    echo "$(gcloud functions describe $FUNCTION_NAME --region=$REGION --format="value(serviceConfig.uri)")"
    echo ""
    echo "📋 パラメータ:"
    echo "  ?fields=title,category,date,Location  # 表示するフィールド"
    echo "  ?size=62x29                          # ラベルサイズ"
    echo ""
    echo "📦 テスト用cURLコマンド例:"
    FUNCTION_URL=$(gcloud functions describe $FUNCTION_NAME --region=$REGION --format="value(serviceConfig.uri)")
    echo "curl -X POST '$FUNCTION_URL?fields=title,category,date' \\"
    echo "  -H 'Content-Type: application/json' \\"
    echo "  -d '{\"data\":{\"id\":\"test\",\"properties\":{\"Name\":{\"type\":\"title\",\"title\":[{\"plain_text\":\"テスト商品\"}]}}}}'"
else
    echo "❌ デプロイに失敗しました"
    exit 1
fi