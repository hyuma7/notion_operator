"""
Notion APIデータの解析モジュール
"""

import json
from typing import Dict, Any, List, Optional
from datetime import datetime


class NotionPageParser:
    """Notionページデータを解析するクラス"""
    
    def __init__(self, notion_client=None):
        self.notion_client = notion_client
    
    def parse_webhook_data(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """Notionウェブフックのデータを解析"""
        try:
            # ウェブフックの基本情報
            event_type = webhook_data.get('event_type', 'unknown')
            event_time = webhook_data.get('event_time', '')
            
            # ページデータの取得
            data = webhook_data.get('data', {})
            page_data = data.get('page', {}) if event_type == 'page_property_updated' else data
            
            if not page_data:
                return {
                    'error': 'ページデータが見つかりません',
                    'event_type': event_type,
                    'event_time': event_time
                }
            
            # ページの基本情報
            page_id = page_data.get('id', '')
            page_url = page_data.get('url', '')
            created_time = page_data.get('created_time', '')
            last_edited_time = page_data.get('last_edited_time', '')
            
            # プロパティの解析
            properties = self.parse_properties(page_data.get('properties', {}))
            
            # タイトルの取得
            title = self.extract_title(page_data)
            
            return {
                'success': True,
                'event_type': event_type,
                'event_time': event_time,
                'page_id': page_id,
                'page_url': page_url,
                'title': title,
                'created_time': created_time,
                'last_edited_time': last_edited_time,
                'properties': properties
            }
            
        except Exception as e:
            return {
                'error': f'解析エラー: {str(e)}',
                'raw_data': webhook_data
            }
    
    def parse_properties(self, properties: Dict[str, Any]) -> Dict[str, Any]:
        """Notionページのプロパティを解析"""
        parsed_properties = {}
        
        for prop_name, prop_data in properties.items():
            prop_type = prop_data.get('type', 'unknown')
            prop_value = self.extract_property_value(prop_data, prop_type)
            
            parsed_properties[prop_name] = {
                'type': prop_type,
                'value': prop_value,
                'raw': prop_data
            }
        
        return parsed_properties
    
    def extract_property_value(self, prop_data: Dict[str, Any], prop_type: str) -> Any:
        """プロパティタイプに応じて値を抽出"""
        try:
            if prop_type == 'title':
                title_array = prop_data.get('title', [])
                return ''.join([t.get('plain_text', '') for t in title_array])
            
            elif prop_type == 'rich_text':
                text_array = prop_data.get('rich_text', [])
                return ''.join([t.get('plain_text', '') for t in text_array])
            
            elif prop_type == 'number':
                return prop_data.get('number')
            
            elif prop_type == 'select':
                select_data = prop_data.get('select')
                return select_data.get('name') if select_data else None
            
            elif prop_type == 'multi_select':
                multi_select_data = prop_data.get('multi_select', [])
                return [item.get('name') for item in multi_select_data]
            
            elif prop_type == 'date':
                date_data = prop_data.get('date')
                if date_data:
                    return {
                        'start': date_data.get('start'),
                        'end': date_data.get('end'),
                        'time_zone': date_data.get('time_zone')
                    }
                return None
            
            elif prop_type == 'checkbox':
                return prop_data.get('checkbox', False)
            
            elif prop_type == 'url':
                return prop_data.get('url')
            
            elif prop_type == 'email':
                return prop_data.get('email')
            
            elif prop_type == 'phone_number':
                return prop_data.get('phone_number')
            
            elif prop_type == 'people':
                people_data = prop_data.get('people', [])
                return [person.get('name', person.get('id')) for person in people_data]
            
            elif prop_type == 'files':
                files_data = prop_data.get('files', [])
                return [file.get('name', file.get('file', {}).get('url')) for file in files_data]
            
            elif prop_type == 'created_time' or prop_type == 'last_edited_time':
                return prop_data.get(prop_type)
            
            elif prop_type == 'created_by' or prop_type == 'last_edited_by':
                user_data = prop_data.get(prop_type, {})
                return user_data.get('name', user_data.get('id'))
            
            elif prop_type == 'formula':
                formula_data = prop_data.get('formula', {})
                formula_type = formula_data.get('type')
                if formula_type:
                    return formula_data.get(formula_type)
                return None
            
            elif prop_type == 'rollup':
                rollup_data = prop_data.get('rollup', {})
                rollup_type = rollup_data.get('type')
                if rollup_type == 'array':
                    array_data = rollup_data.get('array', [])
                    results = []
                    for item in array_data:
                        item_type = item.get('type')
                        if item_type == 'title':
                            title_array = item.get('title', [])
                            title_text = ''.join([t.get('plain_text', '') for t in title_array])
                            if title_text:
                                results.append(title_text)
                        elif item_type == 'rich_text':
                            rich_text_array = item.get('rich_text', [])
                            rich_text = ''.join([t.get('plain_text', '') for t in rich_text_array])
                            if rich_text:
                                results.append(rich_text)
                        elif item_type == 'number':
                            number_val = item.get('number')
                            if number_val is not None:
                                results.append(str(number_val))
                        else:
                            # その他のタイプはそのまま追加
                            results.append(str(item))
                    return ', '.join(results) if results else None
                elif rollup_type:
                    rollup_content = rollup_data.get(rollup_type)
                    # titleタイプの場合は、contentを取得
                    if rollup_type == 'title' and isinstance(rollup_content, list):
                        return ''.join([item.get('plain_text', '') for item in rollup_content])
                    return rollup_content
                return None
            
            elif prop_type == 'relation':
                relation_data = prop_data.get('relation', [])
                if relation_data:
                    relation_titles = []
                    for rel_obj in relation_data:
                        rel_id = rel_obj.get('id')
                        if rel_id:
                            title = self._get_relation_title(rel_id)
                            relation_titles.append(title)
                    return ', '.join(relation_titles) if relation_titles else []
                return []
            
            elif prop_type == 'unique_id':
                unique_id_data = prop_data.get('unique_id', {})
                prefix = unique_id_data.get('prefix', '')
                number = unique_id_data.get('number', '')
                return f"{prefix}-{number}" if prefix and number else str(number)
            
            else:
                return f"未対応のタイプ: {prop_type}"
                
        except Exception as e:
            return f"解析エラー: {str(e)}"
    
    def _get_relation_title(self, relation_id: str) -> str:
        """関連ページのタイトルを取得する"""
        try:
            if hasattr(self, 'notion_client') and self.notion_client:
                rel_page = self.notion_client.pages.retrieve(page_id=relation_id)
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
    
    def extract_title(self, page_data: Dict[str, Any]) -> str:
        """ページのタイトルを抽出"""
        properties = page_data.get('properties', {})
        
        # タイトルプロパティを探す
        for prop_name, prop_data in properties.items():
            if prop_data.get('type') == 'title':
                title_array = prop_data.get('title', [])
                return ''.join([t.get('plain_text', '') for t in title_array])
        
        return 'タイトルなし'
    
    def print_request_data(self, webhook_data: Dict[str, Any]) -> None:
        """受信したリクエストデータを整形して出力"""
        print("=" * 50)
        print("Notionリクエストデータ (JSON):")
        print("-" * 50)
        
        try:
            # JSONとして整形して出力
            print(json.dumps(webhook_data, indent=2, ensure_ascii=False))
            print("=" * 50)
            
        except Exception as e:
            print(f"データ出力エラー: {str(e)}")
            print("元のデータ:")
            print(str(webhook_data))
            print("=" * 50)
    
    def get_printable_fields(self, parsed_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """印刷可能なフィールドを取得"""
        printable_fields = []
        
        if parsed_data.get('success'):
            # タイトルは商品名と重複するため除外
            
            # プロパティ
            properties = parsed_data.get('properties', {})
            for prop_name, prop_info in properties.items():
                prop_value = prop_info.get('value')
                prop_type = prop_info.get('type')
                
                # 空の値や特定のタイプは除外
                if prop_value is not None and prop_value != '' and prop_type not in ['created_time', 'last_edited_time', 'created_by', 'last_edited_by']:
                    # 値を文字列に変換
                    if isinstance(prop_value, list):
                        display_value = ', '.join(str(v) for v in prop_value)
                    elif isinstance(prop_value, dict):
                        display_value = str(prop_value)
                    else:
                        display_value = str(prop_value)
                    
                    printable_fields.append({
                        'name': prop_name,
                        'value': display_value,
                        'type': prop_type
                    })
        
        return printable_fields