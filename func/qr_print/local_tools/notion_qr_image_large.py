#!/usr/bin/env python3
"""
Notion QR Label Printer with Large Fonts and QR Code
大きな文字とQRコードでの画像生成版
"""

import os
import json
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
import logging

# ロガー設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ライブラリの動的インポート
try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
    logger.info("PIL (Pillow) ライブラリが利用可能です")
except ImportError:
    HAS_PIL = False
    logger.warning("PIL (Pillow) ライブラリがインストールされていません")
    logger.warning("インストール: pip install pillow")

try:
    import qrcode
    HAS_QRCODE = True
    logger.info("QRCode ライブラリが利用可能です")
except ImportError:
    HAS_QRCODE = False
    logger.warning("QRCode ライブラリがインストールされていません")
    logger.warning("インストール: pip install qrcode[pil]")


class NotionQRLabelPrinterLarge:
    """大きな文字とQRコード対応の画像生成クラス"""
    
    def __init__(self, label_size: str = "62x29"):
        self.label_size = label_size
        self.label_sizes = {
            "62x29": (696, 271),   # 62mm x 29mm
            "62x100": (696, 1109)  # 62mm x 100mm
        }
        
        if label_size not in self.label_sizes:
            raise ValueError(f"Unsupported label size: {label_size}")
            
        self.width, self.height = self.label_sizes[label_size]
    
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
        else:
            return str(prop)
    
    def generate_qr_code(self, data: Dict[str, Any], size: int = 250):
        """QRコードを生成（大きめサイズ）"""
        if not HAS_QRCODE:
            return None
        
        try:
            # QRコードデータ
            qr_data = {
                "id": data.get("page_id", ""),
                "title": data.get("title", ""),
                "category": data.get("category", ""),
                "date": data.get("date", ""),
                "url": data.get("url", "")
            }
            
            # QRコード生成
            qr = qrcode.QRCode(
                version=None,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=12,  # 少し大きく
                border=2,     # ボーダーも少し大きく
            )
            
            qr.add_data(json.dumps(qr_data, ensure_ascii=False))
            qr.make(fit=True)
            
            qr_img = qr.make_image(fill_color="black", back_color="white")
            return qr_img.resize((size, size), Image.Resampling.LANCZOS)
        except Exception as e:
            logger.error(f"QRコード生成エラー: {e}")
            return None
    
    def create_label_image(self, data: Dict[str, Any], display_fields: List[str] = None):
        """ラベル画像を作成（大きな文字とQRコード）"""
        if not HAS_PIL:
            logger.error("画像生成にはPIL (Pillow) ライブラリが必要です")
            return None
        
        try:
            # 白い背景画像を作成
            img = Image.new('RGB', (self.width, self.height), color='white')
            draw = ImageDraw.Draw(img)
            
            # フォント設定（サイズを大きく）
            try:
                # 日本語フォントを試す
                font_paths = [
                    "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",  # macOS
                    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",  # Linux
                    "C:/Windows/Fonts/msgothic.ttc",  # Windows
                ]
                font_extra_large = None
                font_large = None
                font_medium = None
                font_small = None
                
                for font_path in font_paths:
                    if os.path.exists(font_path):
                        font_extra_large = ImageFont.truetype(font_path, 32)  # より大きく
                        font_large = ImageFont.truetype(font_path, 28)        # 大きく
                        font_medium = ImageFont.truetype(font_path, 22)       # 中
                        font_small = ImageFont.truetype(font_path, 16)        # 小
                        logger.info(f"日本語フォントを使用: {font_path}")
                        break
                
                if font_extra_large is None:
                    # デフォルトフォントを使用
                    font_extra_large = ImageFont.load_default()
                    font_large = ImageFont.load_default()
                    font_medium = ImageFont.load_default()
                    font_small = ImageFont.load_default()
                    logger.warning("デフォルトフォントを使用（日本語が正しく表示されない可能性があります）")
            
            except Exception as e:
                logger.error(f"フォント読み込みエラー: {e}")
                font_extra_large = ImageFont.load_default()
                font_large = ImageFont.load_default()
                font_medium = ImageFont.load_default()
                font_small = ImageFont.load_default()
            
            # レイアウト設定（QRコードサイズを大きく）
            padding = 15
            qr_size = min(self.height - 2 * padding, 250)  # 250pxに拡大
            
            # QRコード生成と配置
            qr_img = self.generate_qr_code(data, qr_size)
            if qr_img:
                qr_x = padding
                qr_y = (self.height - qr_size) // 2
                img.paste(qr_img, (qr_x, qr_y))
                text_x = qr_x + qr_size + padding * 2
            else:
                # QRコードがない場合は代替表示
                draw.rectangle([padding, padding, padding + qr_size, padding + qr_size], 
                             outline='black', width=3)
                draw.text((padding + 30, padding + qr_size//2), 
                         "QR Code\nNot Available", fill='black', font=font_medium, align='center')
                text_x = padding + qr_size + padding * 2
            
            text_y = padding
            max_text_width = self.width - text_x - padding
            
            # デフォルトの表示フィールド
            if display_fields is None:
                display_fields = ["title", "category", "date", "page_id"]
            
            # タイトル（大きなフォント）
            if "title" in display_fields:
                title = data.get("title", "無題")
                
                # タイトルを折り返し
                title_lines = self._wrap_text(title, font_extra_large, max_text_width)
                for line in title_lines[:2]:  # 最大2行
                    try:
                        draw.text((text_x, text_y), line, font=font_extra_large, fill='black')
                    except UnicodeEncodeError:
                        # ASCII文字のみで描画
                        safe_line = ''.join(c if ord(c) < 128 else '?' for c in line)
                        draw.text((text_x, text_y), safe_line, font=font_extra_large, fill='black')
                    text_y += 38  # 行間を大きく
            
            # その他のフィールド（大きなフォント）
            field_labels = {
                "category": "Category",
                "date": "Date", 
                "status": "Status",
                "tags": "Tags",
                "page_id": "ID"
            }
            
            for field in display_fields:
                if field == "title":
                    continue
                    
                value = data.get(field)
                if value is None and field in data.get("custom_fields", {}):
                    value = data["custom_fields"][field]
                
                if value is not None:
                    label = field_labels.get(field, field)
                    
                    if isinstance(value, list):
                        value = ", ".join(str(v) for v in value)
                    else:
                        value = str(value)
                    
                    if value:
                        text = f"{label}: {value}"
                        
                        # テキストを折り返し
                        lines = self._wrap_text(text, font_large, max_text_width)
                        for line in lines[:1]:  # 1行のみ
                            try:
                                draw.text((text_x, text_y), line, font=font_large, fill='black')
                            except UnicodeEncodeError:
                                # ASCII文字のみで描画
                                safe_line = ''.join(c if ord(c) < 128 else '?' for c in line)
                                draw.text((text_x, text_y), safe_line, font=font_large, fill='black')
                            text_y += 32  # 行間を大きく
                            
                            if text_y > self.height - 50:
                                break
            
            # 印刷日時（下部）
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            try:
                draw.text((text_x, self.height - 30), timestamp, font=font_small, fill='gray')
            except UnicodeEncodeError:
                draw.text((text_x, self.height - 30), "2025-01-18 00:00", font=font_small, fill='gray')
            
            # 枠線を描画
            draw.rectangle([0, 0, self.width-1, self.height-1], outline='black', width=3)
            
            return img
            
        except Exception as e:
            logger.error(f"画像生成エラー: {e}")
            return None
    
    def _wrap_text(self, text: str, font, max_width: int) -> List[str]:
        """テキストを指定幅で折り返し"""
        lines = []
        words = text.split()
        current_line = ""
        
        for word in words:
            test_line = current_line + " " + word if current_line else word
            try:
                bbox = font.getbbox(test_line)
                text_width = bbox[2] - bbox[0]
            except:
                # フォールバック
                text_width = len(test_line) * 20
            
            if text_width <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        
        if current_line:
            lines.append(current_line)
        
        return lines


def process_notion_webhook_large(payload: Dict[str, Any], display_fields: List[str] = None,
                                label_size: str = "62x29", save_image: bool = True) -> Dict[str, Any]:
    """
    Notionウェブフックを処理してラベルを生成（大きなフォント版）
    """
    try:
        # プリンターインスタンス作成
        printer = NotionQRLabelPrinterLarge(label_size=label_size)
        
        # データ抽出
        data = printer.extract_notion_data(payload)
        logger.info(f"抽出されたデータ: {json.dumps(data, ensure_ascii=False, indent=2)}")
        
        # 画像生成
        image_path = None
        if HAS_PIL and save_image:
            try:
                label_img = printer.create_label_image(data, display_fields)
                if label_img:
                    image_path = f"label_large_{data.get('page_id', 'unknown')[:8]}.png"
                    label_img.save(image_path, 'PNG')
                    logger.info(f"大きなフォントのラベル画像を保存: {image_path}")
                    
                    # 画像の詳細情報も表示
                    logger.info(f"画像サイズ: {label_img.size[0]}x{label_img.size[1]} ピクセル")
                    logger.info(f"実際のサイズ: {label_size}mm")
            except Exception as e:
                logger.error(f"画像保存エラー: {e}")
        
        result = {
            "success": True,
            "message": "大きなフォントのラベルを生成しました",
            "data": data,
            "image_path": image_path,
            "has_pil": HAS_PIL,
            "has_qrcode": HAS_QRCODE,
            "libraries_needed": []
        }
        
        # 不足しているライブラリの情報
        if not HAS_PIL:
            result["libraries_needed"].append("pillow")
        if not HAS_QRCODE:
            result["libraries_needed"].append("qrcode[pil]")
        
        return result
        
    except Exception as e:
        logger.error(f"処理エラー: {e}")
        return {
            "success": False,
            "message": str(e),
            "data": None,
            "image_path": None,
            "has_pil": HAS_PIL,
            "has_qrcode": HAS_QRCODE,
            "libraries_needed": ["pillow", "qrcode[pil]"] if not HAS_PIL else ["qrcode[pil]"] if not HAS_QRCODE else []
        }


if __name__ == "__main__":
    # テスト用のサンプルペイロード
    sample_payload = {
        "data": {
            "id": "12345678-1234-1234-1234-123456789012",
            "url": "https://www.notion.so/Test-Page-123456789012",
            "icon": {"emoji": "🔧"},
            "properties": {
                "Name": {"type": "title", "title": [{"plain_text": "テスト機器 ABC-123"}]},
                "Category": {"type": "select", "select": {"name": "電子機器"}},
                "Date": {"type": "date", "date": {"start": "2025-01-17"}},
                "Status": {"type": "status", "status": {"name": "使用中"}},
                "Location": {"type": "rich_text", "rich_text": [{"plain_text": "研究室A-101"}]},
                "SerialNumber": {"type": "rich_text", "rich_text": [{"plain_text": "SN-2025-0001"}]}
            }
        }
    }
    
    print("🖼️  大きなフォント版 - Notionラベル生成テスト")
    print("=" * 50)
    
    # ライブラリ状況確認
    print(f"PIL (Pillow): {'✅ 利用可能' if HAS_PIL else '❌ 未インストール'}")
    print(f"QRCode: {'✅ 利用可能' if HAS_QRCODE else '❌ 未インストール'}")
    print()
    
    if not HAS_PIL:
        print("📦 必要なライブラリをインストールしてください:")
        print("   pip install pillow qrcode[pil]")
        print()
    
    # テスト実行
    display_fields = ["title", "category", "date", "Location", "SerialNumber", "page_id"]
    
    result = process_notion_webhook_large(
        sample_payload,
        display_fields=display_fields,
        label_size="62x29",
        save_image=True
    )
    
    print("📊 処理結果:")
    print(f"  成功: {'✅' if result['success'] else '❌'} {result['success']}")
    print(f"  メッセージ: {result['message']}")
    
    if result['image_path']:
        print(f"  🖼️  画像ファイル: {result['image_path']}")
        print(f"  📂 現在のディレクトリに保存されました")
        print()
        print("📱 画像を確認する方法:")
        print(f"  - ファイルマネージャで {result['image_path']} を開く")
        print(f"  - 画像ビューアで {result['image_path']} を開く")
        print(f"  - ブラウザで file://{os.path.abspath(result['image_path'])} にアクセス")
        print()
        print("🖨️  Brother QLで印刷:")
        print(f"  python3 test_image_print.py {result['image_path']}")
    else:
        print("  ❌ 画像は生成されませんでした")
        if result['libraries_needed']:
            print(f"  📦 必要なライブラリ: {', '.join(result['libraries_needed'])}")
    
    print("\n💡 変更点:")
    print("  ✅ QRコードサイズ: 200px → 250px")
    print("  ✅ タイトルフォント: 24px → 32px")
    print("  ✅ フィールドフォント: 18px → 28px")
    print("  ✅ 行間: より大きく調整")
    print("  ✅ QRコードボックスサイズ: 10 → 12")