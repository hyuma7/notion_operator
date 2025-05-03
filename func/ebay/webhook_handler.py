import os
import json
import logging
from datetime import datetime
from flask import Flask, request, jsonify
from func.common.notion_auth import NotionAuth, require_notion_auth
from func.common.db.models import Product, Phase, StockStatus
from func.ebay.notifier import NotionNotifier

# ロガーの設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

class WebhookHandler:
    """eBayからのWebhook通知を処理するクラス"""
    
    def __init__(self):
        self.notion_auth = NotionAuth()
        self.client = self.notion_auth.get_client()
        self.products_db_id = os.environ.get('NOTION_PRODUCTS_DB_ID')
        self.notifier = NotionNotifier()
        if not self.products_db_id:
            raise ValueError("NOTION_PRODUCTS_DB_ID environment variable is not set")
    
    def handle_item_sold(self, item_id, transaction_id=None):
        """
        商品が売れた時の処理
        
        Args:
            item_id: eBayの商品ID
            transaction_id: 取引ID (オプション)
            
        Returns:
            dict: 処理結果
        """
        logger.info(f"商品売却通知を受信: ItemID={item_id}, TransactionID={transaction_id}")
        
        try:
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
            
            response = self.client.databases.query(database_id=self.products_db_id, **filter_params)
            
            if not response.get('results'):
                logger.warning(f"商品が見つかりません: eBay URL={ebay_url}")
                return {"success": False, "error": f"Product with eBay URL {ebay_url} not found"}
            
            # 商品情報の更新
            page_id = response['results'][0]['id']
            
            # 商品データを取得
            page = self.client.pages.retrieve(page_id=page_id)
            product = Product.from_notion_page(page)
            
            # 現在の日時を取得
            now = datetime.now().isoformat()
            
            # 商品情報の更新
            update_data = {
                "phase": {"select": {"name": Phase.SOLD}},
                "stock_status": {"select": {"name": StockStatus.SOLD}},
                "sold_date": {"date": {"start": now}}
            }
            
            logger.info(f"商品情報を更新します: PageID={page_id}")
            self.client.pages.update(page_id=page_id, properties=update_data)
            
            # 売却通知を作成
            notification_result = self.notifier.create_sale_notification(
                product_id=page_id,
                product_name=product.name,
                platform="EBAY",
                sale_price=product.selling_price,
                transaction_id=transaction_id
            )
            
            logger.info(f"売却通知を作成しました: {notification_result.get('success', False)}")
            
            return {
                "success": True, 
                "message": "Product status updated successfully",
                "page_id": page_id,
                "notification": notification_result
            }
            
        except Exception as e:
            logger.error(f"エラーが発生しました: {str(e)}")
            
            # エラー通知を作成
            self.notifier.create_error_notification(
                f"売却通知処理エラー: {str(e)}", 
                context={"item_id": item_id, "transaction_id": transaction_id}
            )
            
            return {"success": False, "error": str(e)}
    
    def handle_order_notification(self, data):
        """
        注文通知を処理
        
        Args:
            data: 通知データ
            
        Returns:
            dict: 処理結果
        """
        logger.info("注文通知を受信しました")
        
        try:
            # 注文に関連する商品IDを取得（データ形式に応じて調整が必要）
            order_items = data.get('OrderItems', [])
            
            for item in order_items:
                item_id = item.get('ItemID')
                if item_id:
                    # 各商品に対して売却処理を実行
                    self.handle_item_sold(item_id, data.get('OrderID'))
            
            return {"success": True, "message": "Order notification processed"}
            
        except Exception as e:
            logger.error(f"注文通知処理エラー: {str(e)}")
            
            # エラー通知を作成
            self.notifier.create_error_notification(
                f"注文通知処理エラー: {str(e)}", 
                context={"order_data": json.dumps(data)}
            )
            
            return {"success": False, "error": str(e)}

# Webhookエンドポイント
@app.route('/ebay/webhook', methods=['POST'])
@require_notion_auth
def ebay_webhook():
    """eBayからのWebhook通知を処理するエンドポイント"""
    data = request.get_json()
    
    # 通知タイプの判定
    notification_type = data.get('notification_type')
    
    # WebhookHandlerのインスタンスを作成
    handler = WebhookHandler()
    
    if notification_type == 'ITEM_SOLD':
        # 商品売却通知
        item_id = data.get('ItemID')
        transaction_id = data.get('TransactionID')
        
        if not item_id:
            return jsonify({"error": "ItemID is required"}), 400
        
        result = handler.handle_item_sold(item_id, transaction_id)
        return jsonify(result)
    
    elif notification_type == 'ORDER_PLACED':
        # 注文通知
        result = handler.handle_order_notification(data)
        return jsonify(result)
    
    else:
        # 未対応の通知タイプ
        logger.warning(f"未対応の通知タイプです: {notification_type}")
        
        # エラー通知を作成
        notifier = NotionNotifier()
        notifier.create_error_notification(
            f"未対応の通知タイプ: {notification_type}", 
            context={"data": json.dumps(data)}
        )
        
        return jsonify({"error": f"Unsupported notification type: {notification_type}"}), 400

if __name__ == '__main__':
    app.run(debug=True) 