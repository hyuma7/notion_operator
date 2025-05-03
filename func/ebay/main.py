import os
import json
from datetime import datetime
from flask import Flask, request, jsonify
from ebaysdk.trading import Connection as Trading
from ebaysdk.exception import ConnectionError
from functools import wraps

from func.common.db.models import Product, Phase, StockStatus, Platform
from func.common.notion_auth import NotionAuth, require_notion_auth
from func.ebay.notifier import NotionNotifier

app = Flask(__name__)

# eBay API接続設定
def get_ebay_api():
    try:
        return Trading(
            domain='api.ebay.com',
            appid=os.environ.get('EBAY_APP_ID'),
            devid=os.environ.get('EBAY_DEV_ID'),
            certid=os.environ.get('EBAY_CERT_ID'),
            token=os.environ.get('EBAY_TOKEN'),
            config_file=None
        )
    except Exception as e:
        print(f"eBay API接続エラー: {str(e)}")
        return None

# Notionから商品を取得
def get_products_for_sale():
    notion_auth = NotionAuth()
    client = notion_auth.get_client()
    
    # 販売中またはON_SALE状態の商品を検索
    results = []
    
    # ここではFilterを使用して「販売中」の商品だけを取得
    filter_params = {
        "filter": {
            "and": [
                {
                    "property": "phase",
                    "select": {
                        "equals": Phase.ON_SALE
                    }
                },
                {
                    "property": "stock_status",
                    "select": {
                        "equals": StockStatus.IN_STOCK
                    }
                }
            ]
        }
    }
    
    # NotionクライアントでDBIDを取得し、そこから商品を検索
    # 環境変数またはシステム設定からDB IDを取得する必要があります
    products_db_id = os.environ.get('NOTION_PRODUCTS_DB_ID')
    if not products_db_id:
        raise ValueError("NOTION_PRODUCTS_DB_ID environment variable is not set")
    
    response = client.databases.query(database_id=products_db_id, **filter_params)
    
    for item in response.get('results', []):
        # NotionからのレスポンスをProductオブジェクトに変換
        product = Product.from_notion_page(item)
        results.append(product)
    
    return results

# eBayに商品を出品
def list_item_on_ebay(product):
    api = get_ebay_api()
    if not api:
        return {"success": False, "error": "eBay API connection failed"}
    
    try:
        # 出品情報を設定
        item = {
            "Item": {
                "Title": product.name,
                "Description": product.description or "",
                "PrimaryCategory": {"CategoryID": "100"}, # カテゴリーIDは適切に設定する必要があります
                "StartPrice": str(product.selling_price),
                "Currency": "JPY",
                "Country": "JP",
                "ListingDuration": "Days_7",
                "Location": "Tokyo, Japan",
                "PaymentMethods": "PayPal",
                "PayPalEmailAddress": os.environ.get('PAYPAL_EMAIL'),
                "ReturnPolicy": {
                    "ReturnsAcceptedOption": "ReturnsAccepted",
                    "RefundOption": "MoneyBack",
                    "ReturnsWithinOption": "Days_14",
                    "ShippingCostPaidByOption": "Buyer"
                },
                "ShippingDetails": {
                    "ShippingType": "Flat",
                    "ShippingServiceOptions": {
                        "ShippingServicePriority": "1",
                        "ShippingService": "ShippingMethodStandard",
                        "ShippingServiceCost": "0.00"
                    }
                },
                "DispatchTimeMax": "3",
                "ConditionID": "1000", # 商品の状態コードを設定
                "PictureDetails": {
                    "PictureURL": product.images[:12] if product.images else []  # eBayでは最大12枚
                },
            }
        }
        
        # eBayに出品
        response = api.execute('AddItem', item)
        item_id = response.reply.ItemID
        
        # Notionの商品情報を更新（eBay URLを追加）
        notion_auth = NotionAuth()
        client = notion_auth.get_client()
        
        # 商品のNotion IDを取得する必要があります
        ebay_url = f"https://www.ebay.com/itm/{item_id}"
        
        # selling_platformsに「YAHOO」を追加（既存の値を保持）
        platforms = product.selling_platforms if product.selling_platforms else []
        if Platform.YAHOO not in platforms:
            platforms.append(Platform.YAHOO)
        
        # Notionの商品情報を更新
        client.pages.update(
            page_id=product.id,
            properties={
                "ebay_url": {"url": ebay_url},
                "selling_platforms": {"multi_select": [{"name": platform} for platform in platforms]}
            }
        )
        
        return {"success": True, "item_id": item_id, "ebay_url": ebay_url}
    
    except ConnectionError as e:
        # エラー通知を作成
        notifier = NotionNotifier()
        notifier.create_error_notification(
            f"eBay出品エラー: {str(e)}", 
            context={"product_id": product.id, "product_name": product.name}
        )
        return {"success": False, "error": str(e)}

# eBayからの売上通知処理
@app.route('/ebay/notification', methods=['POST'])
@require_notion_auth
def ebay_notification():
    data = request.get_json()
    
    # eBayから通知データを解析
    item_id = data.get('ItemID')
    transaction_id = data.get('TransactionID')
    
    if not item_id:
        return jsonify({"error": "ItemID is required"}), 400
    
    try:
        # NotionからeBay URLで該当商品を検索
        notion_auth = NotionAuth()
        client = notion_auth.get_client()
        
        products_db_id = os.environ.get('NOTION_PRODUCTS_DB_ID')
        if not products_db_id:
            return jsonify({"error": "NOTION_PRODUCTS_DB_ID environment variable is not set"}), 500
        
        # eBay URLから商品を検索
        ebay_url = f"https://www.ebay.com/itm/{item_id}"
        filter_params = {
            "filter": {
                "property": "ebay_url",
                "url": {
                    "equals": ebay_url
                }
            }
        }
        
        response = client.databases.query(database_id=products_db_id, **filter_params)
        
        if not response.get('results'):
            return jsonify({"error": f"Product with eBay URL {ebay_url} not found"}), 404
        
        # 商品情報の更新
        page_id = response['results'][0]['id']
        
        # 商品データを取得
        page = client.pages.retrieve(page_id=page_id)
        product = Product.from_notion_page(page)
        
        # フェーズと在庫状態を更新
        client.pages.update(
            page_id=page_id,
            properties={
                "phase": {"select": {"name": Phase.SOLD}},
                "stock_status": {"select": {"name": StockStatus.SOLD}},
                "sold_date": {"date": {"start": datetime.now().isoformat()}}
            }
        )
        
        # 売上通知を作成
        notifier = NotionNotifier()
        notification_result = notifier.create_sale_notification(
            product_id=page_id,
            product_name=product.name,
            platform="EBAY",
            sale_price=product.selling_price,
            transaction_id=transaction_id
        )
        
        return jsonify({
            "success": True, 
            "message": "Product status updated successfully",
            "notification": notification_result
        })
    
    except Exception as e:
        # エラー通知を作成
        notifier = NotionNotifier()
        notifier.create_error_notification(f"売却通知処理エラー: {str(e)}", context={"item_id": item_id})
        return jsonify({"error": str(e)}), 500

# 商品をeBayに出品するエンドポイント
@app.route('/ebay/list', methods=['POST'])
@require_notion_auth
def list_to_ebay():
    data = request.get_json()
    product_id = data.get('product_id')
    
    if not product_id:
        # IDが指定されていない場合、販売待ちの商品を全て取得して出品
        try:
            products = get_products_for_sale()
            results = []
            
            for product in products:
                result = list_item_on_ebay(product)
                results.append({
                    "product_name": product.name,
                    "result": result
                })
            
            return jsonify({"success": True, "results": results})
        
        except Exception as e:
            # エラー通知を作成
            notifier = NotionNotifier()
            notifier.create_error_notification(f"一括出品エラー: {str(e)}")
            return jsonify({"error": str(e)}), 500
    else:
        # 特定の商品を取得して出品
        try:
            notion_auth = NotionAuth()
            client = notion_auth.get_client()
            
            # 商品IDから商品を取得
            page = client.pages.retrieve(page_id=product_id)
            product = Product.from_notion_page(page)
            
            result = list_item_on_ebay(product)
            return jsonify({"success": True, "product_name": product.name, "result": result})
        
        except Exception as e:
            # エラー通知を作成
            notifier = NotionNotifier()
            notifier.create_error_notification(f"商品出品エラー: {str(e)}", context={"product_id": product_id})
            return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080))) 