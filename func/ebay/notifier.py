import os
import logging
from datetime import datetime
from func.common.notion_auth import NotionAuth

# ロガーの設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NotionNotifier:
    """
    Notion内で通知を作成するクラス
    売上通知などのイベントをNotionデータベースに記録します
    """
    
    def __init__(self):
        self.notion_auth = NotionAuth()
        self.client = self.notion_auth.get_client()
        
        # 通知用データベースIDを環境変数から取得
        self.notifications_db_id = os.environ.get('NOTION_NOTIFICATIONS_DB_ID')
        if not self.notifications_db_id:
            logger.warning("NOTION_NOTIFICATIONS_DB_ID is not set. Notifications will not be created.")
    
    def create_sale_notification(self, product_id, product_name, platform, sale_price, transaction_id=None):
        """
        商品の売上通知を作成する
        
        Args:
            product_id: 商品のNotion ページID
            product_name: 商品名
            platform: 販売プラットフォーム (EBAY, MERCARIなど)
            sale_price: 販売価格
            transaction_id: 取引ID (オプション)
            
        Returns:
            dict: 作成された通知情報
        """
        if not self.notifications_db_id:
            logger.warning("通知データベースIDが設定されていないため、通知を作成できません")
            return {"success": False, "error": "Notification database ID is not set"}
        
        try:
            # 現在の日時
            now = datetime.now().isoformat()
            
            # 通知データの作成
            notification_data = {
                "parent": {"database_id": self.notifications_db_id},
                "properties": {
                    "title": {
                        "title": [
                            {
                                "text": {
                                    "content": f"{product_name}が{platform}で売却されました"
                                }
                            }
                        ]
                    },
                    "type": {
                        "select": {
                            "name": "売上通知"
                        }
                    },
                    "platform": {
                        "select": {
                            "name": platform
                        }
                    },
                    "price": {
                        "number": float(sale_price)
                    },
                    "date": {
                        "date": {
                            "start": now
                        }
                    },
                    "product": {
                        "relation": [
                            {
                                "id": product_id
                            }
                        ]
                    }
                }
            }
            
            # 取引IDが存在する場合は追加
            if transaction_id:
                notification_data["properties"]["transaction_id"] = {
                    "rich_text": [
                        {
                            "text": {
                                "content": transaction_id
                            }
                        }
                    ]
                }
            
            # 通知をNotionに作成
            response = self.client.pages.create(**notification_data)
            logger.info(f"売上通知を作成しました: {product_name}")
            
            return {
                "success": True,
                "notification_id": response["id"],
                "product_name": product_name,
                "platform": platform
            }
            
        except Exception as e:
            logger.error(f"通知作成中にエラーが発生しました: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def create_error_notification(self, error_message, context=None):
        """
        エラー通知を作成する
        
        Args:
            error_message: エラーメッセージ
            context: エラーのコンテキスト情報 (オプション)
            
        Returns:
            dict: 作成された通知情報
        """
        if not self.notifications_db_id:
            logger.warning("通知データベースIDが設定されていないため、通知を作成できません")
            return {"success": False, "error": "Notification database ID is not set"}
        
        try:
            # 現在の日時
            now = datetime.now().isoformat()
            
            # 通知データの作成
            notification_data = {
                "parent": {"database_id": self.notifications_db_id},
                "properties": {
                    "title": {
                        "title": [
                            {
                                "text": {
                                    "content": f"エラー: {error_message[:50]}..."
                                }
                            }
                        ]
                    },
                    "type": {
                        "select": {
                            "name": "エラー"
                        }
                    },
                    "date": {
                        "date": {
                            "start": now
                        }
                    },
                    "details": {
                        "rich_text": [
                            {
                                "text": {
                                    "content": error_message
                                }
                            }
                        ]
                    }
                }
            }
            
            # コンテキスト情報がある場合は追加
            if context:
                notification_data["properties"]["context"] = {
                    "rich_text": [
                        {
                            "text": {
                                "content": str(context)
                            }
                        }
                    ]
                }
            
            # 通知をNotionに作成
            response = self.client.pages.create(**notification_data)
            logger.info(f"エラー通知を作成しました")
            
            return {
                "success": True,
                "notification_id": response["id"]
            }
            
        except Exception as e:
            logger.error(f"通知作成中にエラーが発生しました: {str(e)}")
            return {"success": False, "error": str(e)} 