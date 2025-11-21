#!/bin/bash

# 修正版 Google Cloud Functions デプロイスクリプト
# Notion QR Print Webhook

set -e

print_info() { echo -e "\e[34mℹ️  $1\e[0m"; }
print_success() { echo -e "\e[32m✅ $1\e[0m"; }
print_warning() { echo -e "\e[33m⚠️  $1\e[0m"; }
print_error() { echo -e "\e[31m❌ $1\e[0m"; }

# 設定
FUNCTION_NAME="notion-qr-print"
REGION="asia-northeast1"
RUNTIME="python311"
MEMORY="512MB"
TIMEOUT="180s"
SOURCE_DIR="."
ENTRY_POINT="process_notion_webhook"  # 正しい関数名に修正

# 環境変数
ALLOWED_DATABASE_IDS="${ALLOWED_DATABASE_IDS:-}"  # 許可するデータベースID（カンマ区切り）
PRINTER_IP="${PRINTER_IP:-192.168.1.100}"
PRINTER_MODEL="${PRINTER_MODEL:-QL-820NWB}"
LABEL_SIZE="${LABEL_SIZE:-62x29}"

echo "🔧 修正版 Cloud Functions デプロイスクリプト"
echo "========================================="
echo "関数名: $FUNCTION_NAME"
echo "リージョン: $REGION"
echo "ランタイム: $RUNTIME"
echo "メモリ: $MEMORY"
echo "タイムアウト: $TIMEOUT"
echo "エントリーポイント: $ENTRY_POINT"
echo "========================================="
echo ""

# データベースIDの確認（オプション）
if [[ -n "$ALLOWED_DATABASE_IDS" ]]; then
    print_info "許可データベースID: 設定済み"
else
    print_warning "許可データベースID: 未設定（全データベース許可）"
fi

# 既存の関数を削除
print_info "既存の関数を確認中..."
if gcloud functions describe "$FUNCTION_NAME" --region="$REGION" &>/dev/null; then
    print_warning "既存の関数が見つかりました。削除します..."
    gcloud functions delete "$FUNCTION_NAME" --region="$REGION" --quiet
    print_success "既存の関数を削除しました"
    # 削除後、少し待機
    sleep 5
else
    print_info "既存の関数は見つかりませんでした"
fi

echo ""

# ファイル確認
print_info "必要なファイルの確認..."
if [[ ! -f "main.py" ]]; then
    print_error "main.py が見つかりません"
    exit 1
fi

if [[ ! -f "requirements.txt" ]]; then
    print_error "requirements.txt が見つかりません"
    exit 1
fi

# Python構文チェック
if command -v python3 &> /dev/null; then
    print_info "Python構文をチェック中..."
    if ! python3 -m py_compile main.py 2>/dev/null; then
        print_error "main.py に構文エラーがあります"
        exit 1
    fi
    print_success "構文チェック完了"
    # コンパイル済みファイルを削除
    rm -rf __pycache__
fi

echo ""

# requirements.txt の内容確認
print_info "requirements.txt の内容:"
cat requirements.txt
echo ""

# デプロイ確認
read -p "デプロイを実行しますか? (y/N): " confirm
if [[ $confirm != [yY] ]]; then
    print_warning "デプロイを中止しました"
    exit 0
fi

echo ""
print_info "Cloud Functions をデプロイ中..."

# デプロイ実行
if gcloud functions deploy "$FUNCTION_NAME" \
    --gen2 \
    --runtime="$RUNTIME" \
    --region="$REGION" \
    --source="$SOURCE_DIR" \
    --entry-point="$ENTRY_POINT" \
    --trigger-http \
    --allow-unauthenticated \
    --memory="$MEMORY" \
    --timeout="$TIMEOUT" \
    --set-env-vars="ALLOWED_DATABASE_IDS=$ALLOWED_DATABASE_IDS,PRINTER_IP=$PRINTER_IP,PRINTER_MODEL=$PRINTER_MODEL,LABEL_SIZE=$LABEL_SIZE" \
    --max-instances=10 \
    --min-instances=0 \
    --cpu=1 \
    --no-user-output-enabled; then
    
    echo ""
    print_success "デプロイが完了しました!"
    
    # 関数の状態確認（少し待機）
    sleep 10
    print_info "関数の状態を確認中..."
    gcloud functions describe "$FUNCTION_NAME" --region="$REGION" --format="table(name,state,updateTime)"
    
    # 関数URLの取得
    FUNCTION_URL=$(gcloud functions describe "$FUNCTION_NAME" --region="$REGION" --format="value(serviceConfig.uri)")
    
    echo ""
    echo "📡 関数URL:"
    echo "$FUNCTION_URL"
    
    echo ""
    print_info "テストリクエストを送信中..."
    
    # テストリクエスト
    TEST_DATA='{
        "商品名": "テストアイテム",
        "ID": "TEST123",
        "年式": "2024",
        "仕入れ先": "テスト仕入先",
        "カテゴリー": "テスト"
    }'
    
    if RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$FUNCTION_URL" \
        -H "Content-Type: application/json" \
        -d "$TEST_DATA" 2>/dev/null); then
        
        HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
        BODY=$(echo "$RESPONSE" | sed '$d')
        
        if [[ "$HTTP_CODE" == "200" ]]; then
            print_success "関数は正常に動作しています"
            echo "レスポンス: $BODY"
        else
            print_warning "HTTPステータスコード: $HTTP_CODE"
            echo "レスポンス: $BODY"
        fi
    else
        print_warning "テストリクエストが失敗しました"
    fi
    
    echo ""
    print_info "ログを確認するには:"
    echo "gcloud functions logs read $FUNCTION_NAME --region=$REGION --limit=50"
    
else
    print_error "デプロイに失敗しました"
    echo ""
    print_info "トラブルシューティング:"
    echo "1. 最新のログを確認:"
    echo "   gcloud functions logs read $FUNCTION_NAME --region=$REGION --limit=50"
    echo ""
    echo "2. 環境変数を確認:"
    echo "   - WORKSPACE_ID が正しく設定されているか（オプション）"
    echo "   - その他の環境変数が適切か"
    echo ""
    echo "3. main.py の関数名を確認:"
    echo "   grep -n \"def process_notion_webhook\" main.py"
    echo ""
    echo "4. Notionの自動化設定:"
    echo "   - WebhookのURLが正しいか確認"
    echo "   - 送信するプロパティが選択されているか確認"
    exit 1
fi