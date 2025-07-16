import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from flask import Flask, request, jsonify
import functions_framework

# ロガー設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 環境変数
PRINTER_IP = os.environ.get('PRINTER_IP', '192.168.1.100')
PRINTER_MODEL = os.environ.get('PRINTER_MODEL', 'QL-820NWB')
DEFAULT_LABEL_SIZE = os.environ.get('DEFAULT_LABEL_SIZE', '62x29')

class NotionQRLabelProcessor:
    """Cloud Functions用のNotionペイロード処理クラス"""
    
    def __init__(self, label_size: str = "62x29"):
        self.label_size = label_size
        self.label_sizes = {
            "62x29": (62, 29),
            "62x100": (62, 100)
        }
        
        if label_size not in self.label_sizes:
            raise ValueError(f"Unsupported label size: {label_size}")
            
        self.width_mm, self.height_mm = self.label_sizes[label_size]
    
    def extract_notion_data(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Notionペイロードからデータ抽出"""
        data = payload.get("data", {})
        properties = data.get("properties", {})
        
        # 絵文字を安全に処理
        icon_data = data.get("icon", {})
        if isinstance(icon_data, dict):
            icon = icon_data.get("emoji", "📦")
        else:
            icon = "📦"
        
        # 基本情報の抽出
        extracted = {
            "page_id": data.get("id", ""),
            "url": data.get("url", ""),
            "icon": icon,
            "title": self._extract_title(properties),
            "category": self._extract_property(properties, "Category", "select"),
            "date": self._extract_property(properties, "Date", "date"),
            "status": self._extract_property(properties, "Status", "status"),
            "tags": self._extract_tags(properties),
            "custom_fields": {}
        }
        
        # カスタムフィールドの抽出
        known_fields = {"Name", "Category", "Date", "Status", "Tags"}
        for prop_name, prop_value in properties.items():
            if prop_name not in known_fields:
                value = self._extract_any_property(prop_value)
                extracted["custom_fields"][prop_name] = value
        
        return extracted
    
    def _extract_title(self, properties: Dict[str, Any]) -> str:
        title_prop = properties.get("Name", {})
        if title_prop.get("type") == "title" and title_prop.get("title"):
            return title_prop["title"][0].get("plain_text", "無題")
        return "無題"
    
    def _extract_property(self, properties: Dict[str, Any], name: str, prop_type: str) -> Optional[str]:
        prop = properties.get(name, {})
        if prop.get("type") == prop_type:
            if prop_type == "select":
                return prop.get("select", {}).get("name")
            elif prop_type == "date":
                date_obj = prop.get("date", {})
                if date_obj:
                    return date_obj.get("start")
            elif prop_type == "status":
                return prop.get("status", {}).get("name")
        return None
    
    def _extract_tags(self, properties: Dict[str, Any]) -> List[str]:
        tags_prop = properties.get("Tags", {})
        if tags_prop.get("type") == "multi_select":
            return [tag.get("name", "") for tag in tags_prop.get("multi_select", [])]
        return []
    
    def _extract_any_property(self, prop: Dict[str, Any]) -> Any:
        prop_type = prop.get("type")
        
        if prop_type == "title":
            titles = prop.get("title", [])
            return titles[0].get("plain_text", "") if titles else ""
        elif prop_type == "rich_text":
            texts = prop.get("rich_text", [])
            return texts[0].get("plain_text", "") if texts else ""
        elif prop_type == "number":
            return prop.get("number")
        elif prop_type == "checkbox":
            return prop.get("checkbox", False)
        elif prop_type == "select":
            return prop.get("select", {}).get("name", "")
        elif prop_type == "multi_select":
            return [item.get("name", "") for item in prop.get("multi_select", [])]
        elif prop_type == "date":
            date_obj = prop.get("date", {})
            return date_obj.get("start", "") if date_obj else ""
        elif prop_type == "people":
            return [person.get("name", "") for person in prop.get("people", [])]
        elif prop_type == "url":
            return prop.get("url", "")
        elif prop_type == "email":
            return prop.get("email", "")
        elif prop_type == "phone_number":
            return prop.get("phone_number", "")
        elif prop_type == "relation":
            relation_data = prop.get("relation", [])
            if relation_data:
                relation_titles = []
                for rel_obj in relation_data:
                    rel_id = rel_obj.get("id")
                    if rel_id:
                        title = self._get_relation_title(rel_id)
                        relation_titles.append(title)
                return ", ".join(relation_titles) if relation_titles else []
            return []
        elif prop_type == "unique_id":
            unique_id_data = prop.get("unique_id", {})
            prefix = unique_id_data.get("prefix", "")
            number = unique_id_data.get("number", "")
            return f"{prefix}-{number}" if prefix and number else str(number)
        else:
            return str(prop)
    
    def _get_relation_title(self, relation_id: str) -> str:
        """関連ページのタイトルを取得する"""
        try:
            if hasattr(self, 'notion') and self.notion:
                rel_page = self.notion.pages.retrieve(page_id=relation_id)
                rel_props = rel_page.get("properties", {})
                
                # タイトルプロパティを探す
                for prop_name, prop_data in rel_props.items():
                    if prop_data.get("type") == "title":
                        title_array = prop_data.get("title", [])
                        if title_array:
                            return title_array[0].get("plain_text", "")
                
                return "タイトル不明"
            else:
                return f"関連ID: {relation_id}"
        except Exception as e:
            return f"関連ID: {relation_id}"
    
    def create_label_data(self, data: Dict[str, Any], display_fields: List[str] = None) -> Dict[str, Any]:
        """ラベル用データを作成"""
        
        if display_fields is None:
            display_fields = ["title", "category", "date", "page_id"]
        
        # QRコードデータ
        qr_data = {
            "id": data.get("page_id", ""),
            "title": data.get("title", ""),
            "category": data.get("category", ""),
            "date": data.get("date", ""),
            "url": data.get("url", "")
        }
        
        # 表示フィールドデータ
        fields = []
        field_labels = {
            "category": "📂 カテゴリ",
            "date": "📅 日付",
            "status": "📊 ステータス",
            "tags": "🏷️ タグ",
            "page_id": "🆔 ID"
        }
        
        for field in display_fields:
            if field == "title":
                continue
                
            value = data.get(field)
            if value is None and field in data.get("custom_fields", {}):
                value = data["custom_fields"][field]
            
            if value is not None:
                label = field_labels.get(field, f"📄 {field}")
                
                if isinstance(value, list):
                    value = ", ".join(str(v) for v in value)
                else:
                    value = str(value)
                
                if value:
                    fields.append({
                        "label": label,
                        "value": value
                    })
        
        return {
            "title": data.get("title", "無題"),
            "icon": data.get("icon", "📦"),
            "fields": fields,
            "qr_data": qr_data,
            "label_size": self.label_size,
            "print_command": self._generate_print_command(),
            "timestamp": datetime.now().isoformat()
        }
    
    def _generate_print_command(self) -> str:
        """印刷コマンドを生成"""
        label_size_num = self.label_size.split('x')[0]
        return f"brother_ql -b network -m {PRINTER_MODEL} -p tcp://{PRINTER_IP}:9100 print -l {label_size_num} label.png"


@functions_framework.http
def notion_qr_webhook(request):
    """Cloud Functions のエントリーポイント"""
    
    # CORS設定
    if request.method == 'OPTIONS':
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization',
            'Access-Control-Max-Age': '3600'
        }
        return ('', 204, headers)
    
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Content-Type': 'application/json'
    }
    
    try:
        # リクエスト検証
        if request.method != 'POST':
            return jsonify({
                "error": "Method not allowed",
                "message": "Only POST requests are supported"
            }), 405, headers
        
        # JSONペイロード取得
        if not request.is_json:
            return jsonify({
                "error": "Invalid content type",
                "message": "Content-Type must be application/json"
            }), 400, headers
        
        payload = request.get_json()
        
        if not payload:
            return jsonify({
                "error": "Empty payload",
                "message": "Request body is empty"
            }), 400, headers
        
        logger.info(f"受信したペイロード: {json.dumps(payload, ensure_ascii=False)}")
        
        # パラメータ取得
        display_fields = request.args.getlist('fields') or ["title", "category", "date"]
        label_size = request.args.get('size', DEFAULT_LABEL_SIZE)
        
        # プロセッサー作成
        processor = NotionQRLabelProcessor(label_size=label_size)
        
        # データ抽出
        notion_data = processor.extract_notion_data(payload)
        
        # ラベルデータ作成
        label_data = processor.create_label_data(notion_data, display_fields)
        
        logger.info(f"生成されたラベルデータ: {json.dumps(label_data, ensure_ascii=False)}")
        
        # レスポンス
        response = {
            "success": True,
            "message": "ラベルデータを生成しました",
            "data": label_data,
            "metadata": {
                "function_name": "notion_qr_webhook",
                "version": "1.0.0",
                "timestamp": datetime.now().isoformat(),
                "display_fields": display_fields,
                "label_size": label_size
            }
        }
        
        return jsonify(response), 200, headers
        
    except ValueError as e:
        logger.error(f"バリデーションエラー: {e}")
        return jsonify({
            "error": "Validation error",
            "message": str(e)
        }), 400, headers
        
    except Exception as e:
        logger.error(f"処理エラー: {e}")
        return jsonify({
            "error": "Internal server error",
            "message": "ラベル生成中にエラーが発生しました"
        }), 500, headers


# ローカルテスト用
if __name__ == "__main__":
    from flask import Flask
    
    app = Flask(__name__)
    app.route('/webhook', methods=['POST', 'OPTIONS'])(notion_qr_webhook)
    
    print("🚀 Cloud Functions テスト用サーバー起動")
    print("📡 エンドポイント: http://localhost:8080/webhook")
    print("📄 テスト用ペイロードでPOSTリクエストを送信してください")
    
    app.run(host='0.0.0.0', port=8080, debug=True)