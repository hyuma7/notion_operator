import unittest
from unittest.mock import patch, MagicMock
import json
from datetime import datetime

from func.ebay.main import get_products_for_sale, list_item_on_ebay, app

class TestEbayIntegration(unittest.TestCase):
    
    @patch('func.ebay.main.NotionAuth')
    def test_get_products_for_sale(self, mock_notion_auth):
        # モックの設定
        mock_client = MagicMock()
        mock_notion_auth.return_value.get_client.return_value = mock_client
        
        # テスト用レスポンスの作成
        test_response = {
            'results': [
                {
                    'id': 'page_id_1',
                    'properties': {
                        'name': {'title': [{'text': {'content': 'テスト商品1'}}]},
                        'selling_price': {'number': 1000},
                        'description': {'rich_text': [{'text': {'content': '商品説明1'}}]},
                        'images': {'files': [{'file': {'url': 'http://example.com/image1.jpg'}}]}
                    }
                }
            ]
        }
        mock_client.databases.query.return_value = test_response
        
        # Product.from_notion_pageをモック
        mock_product = MagicMock()
        mock_product.name = 'テスト商品1'
        mock_product.selling_price = 1000
        
        with patch('func.ebay.main.Product.from_notion_page', return_value=mock_product):
            # テスト対象の関数を実行
            with patch('func.ebay.main.os.environ.get', return_value='test_db_id'):
                products = get_products_for_sale()
                
                # アサーション
                self.assertEqual(len(products), 1)
                self.assertEqual(products[0].name, 'テスト商品1')
                self.assertEqual(products[0].selling_price, 1000)
    
    @patch('func.ebay.main.get_ebay_api')
    @patch('func.ebay.main.NotionAuth')
    def test_list_item_on_ebay(self, mock_notion_auth, mock_get_ebay_api):
        # モックの設定
        mock_api = MagicMock()
        mock_get_ebay_api.return_value = mock_api
        
        mock_product = MagicMock()
        mock_product.name = 'テスト商品1'
        mock_product.description = '商品説明1'
        mock_product.selling_price = 1000
        mock_product.images = ['http://example.com/image1.jpg']
        mock_product.id = 'page_id_1'
        
        # eBay APIのレスポンスをモック
        mock_response = MagicMock()
        mock_response.reply.ItemID = '123456789'
        mock_api.execute.return_value = mock_response
        
        # Notionクライアントをモック
        mock_client = MagicMock()
        mock_notion_auth.return_value.get_client.return_value = mock_client
        
        # テスト対象の関数を実行
        result = list_item_on_ebay(mock_product)
        
        # アサーション
        self.assertTrue(result['success'])
        self.assertEqual(result['item_id'], '123456789')
        self.assertEqual(result['ebay_url'], 'https://www.ebay.com/itm/123456789')
        
        # eBay APIが正しく呼び出されたことを確認
        mock_api.execute.assert_called_once()
        
        # Notionクライアントが正しく呼び出されたことを確認
        mock_client.pages.update.assert_called_once()

    def test_ebay_notification_endpoint(self):
        # テスト用クライアント
        client = app.test_client()
        
        # NotionAuthとクライアントのモック
        with patch('func.ebay.main.NotionAuth') as mock_notion_auth, \
             patch('func.ebay.main.require_notion_auth', lambda f: f):  # デコレータをスキップ
            
            mock_client = MagicMock()
            mock_notion_auth.return_value.get_client.return_value = mock_client
            
            # テスト用レスポンスの作成
            test_response = {
                'results': [
                    {'id': 'page_id_1'}
                ]
            }
            mock_client.databases.query.return_value = test_response
            
            # 環境変数をモック
            with patch('func.ebay.main.os.environ.get', return_value='test_db_id'):
                # テスト対象のエンドポイントを呼び出し
                response = client.post(
                    '/ebay/notification',
                    data=json.dumps({'ItemID': '123456789'}),
                    content_type='application/json'
                )
                
                # アサーション
                self.assertEqual(response.status_code, 200)
                data = json.loads(response.data)
                self.assertTrue(data['success'])
                
                # Notionが正しく更新されたことを確認
                mock_client.pages.update.assert_called_once()

if __name__ == '__main__':
    unittest.main() 