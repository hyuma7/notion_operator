import os
import json
import logging
import socket
import time
from datetime import datetime
from contextlib import contextmanager
from typing import Dict, Any, Optional, List

import functions_framework
from flask import jsonify, Request
from notion_client import Client
from PIL import Image, ImageDraw, ImageFont
import qrcode
from brother_ql import BrotherQLRaster, create_label
from brother_ql.backends import backend_factory

# ロギング設定
logging.basicConfig(level=logging.INFO)

# 環境変数
NOTION_API_KEY = os.environ.get("NOTION_API_KEY")
PRINTER_IP = os.environ.get('PRINTER_IP', '192.168.1.100')
PRINTER_MODEL = os.environ.get('PRINTER_MODEL', 'QL-820NWB')
LABEL_SIZE = os.environ.get('LABEL_SIZE', '62x29')

# Notionクライアントの初期化
notion = Client(auth=NOTION_API_KEY)

class PrinterError(Exception):
    pass

@contextmanager
def printer_connection_test(printer_ip: str, port: int = 9100, timeout: int = 10):
    """プリンター接続をテスト"""
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((printer_ip, port))
        yield sock
    except socket.timeout:
        raise PrinterError(f"{printer_ip}:{port}への接続タイムアウト")
    except socket.error as e:
        raise PrinterError(f"プリンターに到達できません: {e}")
    finally:
        if sock:
            sock.close()

def extract_notion_data(webhook_data: Dict[str, Any]) -> Dict[str, Any]:
    """Notionウェブフックからデータを抽出して正規化"""
    
    # Notion自動化からのデータ形式の場合
    if "data" in webhook_data and isinstance(webhook_data["data"], dict):
        notion_data = webhook_data["data"]
        properties = notion_data.get("properties", {})
        
        # ページ情報を抽出
        page_id = notion_data.get("id", "")
        page_url = notion_data.get("url") or notion_data.get("public_url") or ""
        
        # タイトルを取得（複数の形式に対応）
        title = ""
        if page_url:
            # URLからタイトルを抽出
            title = page_url.split("/")[-1].replace("-", " ")
            # ページIDを除去
            if len(title) > 32 and title[-32:].replace(" ", "").isalnum():
                title = title[:-33]
        
        # アイコンの取得
        icon = ""
        if "icon" in notion_data and notion_data["icon"]:
            if notion_data["icon"]["type"] == "emoji":
                icon = notion_data["icon"].get("emoji", "")
        
        # カテゴリーやその他のプロパティを取得
        category = ""
        date = datetime.utcnow().strftime("%Y-%m-%d")
        
        # プロパティから追加情報を取得（あれば）
        for prop_name, prop_data in properties.items():
            if isinstance(prop_data, dict):
                if "select" in prop_data and prop_data["select"]:
                    category = prop_data["select"].get("name", "")
                elif "date" in prop_data and prop_data["date"]:
                    date = prop_data["date"].get("start", date)
        
        return {
            'name': f"{icon} {title}".strip() if icon else title,
            'id': page_id[:8] if page_id else "NO_ID",
            'category': category or "未分類",
            'date': date,
            'page_id': page_id,
            'page_url': page_url
        }
    
    # 従来の形式
    return {
        'name': webhook_data.get('name', 'アイテム'),
        'id': webhook_data.get('id', 'NO_ID'),
        'category': webhook_data.get('category', '未分類'),
        'date': webhook_data.get('date', datetime.utcnow().strftime("%Y-%m-%d")),
        'page_id': webhook_data.get('page_id', ''),
        'page_url': webhook_data.get('page_url', '')
    }

def create_notion_label(qr_data: Dict[str, Any], title: str, details: List[str]) -> Image.Image:
    """Notionアイテム専用のラベルを作成"""
    
    # ラベルサイズに応じた寸法を設定
    if LABEL_SIZE == '62x29':
        width_px, height_px = 696, 271
    elif LABEL_SIZE == '62x100':
        width_px, height_px = 696, 1109
    else:
        # デフォルトは50mm高さの連続62mm
        width_px = 696
        height_px = int(50 * 300 / 25.4)
    
    # 白い背景でラベルを作成
    label = Image.new('RGB', (width_px, height_px), 'white')
    draw = ImageDraw.Draw(label)
    
    # QRコードを生成
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(json.dumps(qr_data))
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    
    # レイアウトとフォント設定
    if LABEL_SIZE == '62x29':
        # 横並びレイアウト（左にQR、右にテキスト）
        qr_size = height_px - 40
        try:
            qr_img = qr_img.resize((qr_size, qr_size), Image.Resampling.LANCZOS)
        except AttributeError:
            qr_img = qr_img.resize((qr_size, qr_size), Image.LANCZOS)
        label.paste(qr_img, (20, 20))
        
        text_x = qr_size + 40
        text_y = 30
        
        # コンパクトなフォントサイズ
        font_sizes = {'title': 20, 'details': 14}
    else:
        # 縦レイアウト（上にQR、下にテキスト）
        qr_size = min(width_px - 40, int(height_px * 0.5))
        try:
            qr_img = qr_img.resize((qr_size, qr_size), Image.Resampling.LANCZOS)
        except AttributeError:
            qr_img = qr_img.resize((qr_size, qr_size), Image.LANCZOS)
        qr_x = (width_px - qr_size) // 2
        label.paste(qr_img, (qr_x, 20))
        
        text_x = 20
        text_y = qr_size + 40
        
        font_sizes = {'title': 24, 'details': 18}
    
    # フォントを設定（日本語対応）
    try:
        font_path = os.path.join(os.path.dirname(__file__), '..', 'add_qr_info_code', 'fonts', 'NotoSansJP-Regular.otf')
        if os.path.exists(font_path):
            font_title = ImageFont.truetype(font_path, font_sizes['title'])
            font_details = ImageFont.truetype(font_path, font_sizes['details'])
        else:
            raise FileNotFoundError("Font file not found")
    except:
        try:
            font_title = ImageFont.truetype("DejaVuSans-Bold.ttf", font_sizes['title'])
            font_details = ImageFont.truetype("DejaVuSans.ttf", font_sizes['details'])
        except:
            font_title = ImageFont.load_default()
            font_details = ImageFont.load_default()
    
    # タイトルを描画
    draw.text((text_x, text_y), title[:30], fill='black', font=font_title)
    
    # 詳細を描画
    detail_y = text_y + 30
    for detail in details:
        if detail and detail_y < height_px - 20:
            draw.text((text_x, detail_y), detail[:40], fill='black', font=font_details)
            detail_y += 22
    
    return label

def print_label_to_brother(label_image: Image.Image, printer_ip: str, label_size: str = '62', max_retries: int = 3) -> Dict[str, Any]:
    """
    リトライロジック付きでBrother QL-820NWBにラベルを印刷
    
    戻り値:
        dict: {'success': bool, 'message': str}
    """
    printer_identifier = f"tcp://{printer_ip}:9100"
    model = PRINTER_MODEL
    
    # 接続テスト
    try:
        with printer_connection_test(printer_ip):
            logging.info(f"プリンター {printer_ip} に到達可能")
    except PrinterError as e:
        return {'success': False, 'message': str(e)}
    
    # 印刷指示を作成
    try:
        qlr = BrotherQLRaster(model)
        instructions = create_label(
            qlr, 
            label_image, 
            label_size=label_size,
            cut=True,
            compress=True,
            red=False
        )
    except Exception as e:
        return {'success': False, 'message': f"ラベル作成エラー: {e}"}
    
    # リトライ付きで印刷
    for attempt in range(max_retries):
        try:
            backend = backend_factory('network')
            send_function = backend['writer']
            send_function(instructions, printer_identifier)
            
            logging.info(f"試行 {attempt + 1} で印刷成功")
            return {'success': True, 'message': 'ラベルが正常に印刷されました'}
            
        except Exception as e:
            logging.warning(f"印刷試行 {attempt + 1} 失敗: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                return {'success': False, 'message': f"{max_retries}回の試行後に印刷失敗: {e}"}

@functions_framework.http
def process_notion_webhook(request: Request):
    """
    Notionウェブフックを処理してラベルを印刷
    """
    try:
        # リクエストデータの取得
        request_data = request.get_json(silent=True)
        if not request_data:
            request_data = request.data.decode('utf-8')
        
        logging.info(f"受信データ: {request_data}")
        
        # データの検証
        if not request_data:
            return jsonify({"error": "リクエストデータが必要です"}), 400
        
        # 文字列の場合はJSONに変換
        if isinstance(request_data, str):
            try:
                # シングルクォートをダブルクォートに置換
                try:
                    cleaned_data = request_data.replace("'", '"')
                    request_data = json.loads(cleaned_data)
                except json.JSONDecodeError:
                    # ast.literal_evalを試す
                    import ast
                    request_data = ast.literal_eval(request_data)
            except Exception as e:
                logging.error(f"JSON解析エラー: {e}")
                return jsonify({"error": f"JSONの解析に失敗しました: {e}"}), 400
        
        logging.info(f"解析後のデータ: {request_data}")
        
        # Notionデータを抽出
        label_data = extract_notion_data(request_data)
        
        # QRコードデータを生成
        qr_data = {
            'id': label_data['id'],
            'name': label_data['name'],
            'timestamp': datetime.utcnow().isoformat(),
            'page_id': label_data['page_id'],
            'page_url': label_data['page_url']
        }
        
        # ラベルを作成
        label_image = create_notion_label(
            qr_data=qr_data,
            title=label_data['name'],
            details=[
                f"ID: {label_data['id']}",
                f"カテゴリ: {label_data['category']}",
                f"日付: {label_data['date']}"
            ]
        )
        
        # ラベルを印刷
        result = print_label_to_brother(label_image, PRINTER_IP, LABEL_SIZE)
        
        if result['success']:
            return jsonify({
                "status": "success",
                "message": result['message'],
                "label_id": label_data['id'],
                "printed_data": {
                    "title": label_data['name'],
                    "id": label_data['id'],
                    "category": label_data['category'],
                    "date": label_data['date']
                }
            }), 200
        else:
            return jsonify({
                "status": "error",
                "message": result['message']
            }), 500
            
    except Exception as e:
        logging.error(f"ウェブフック処理エラー: {str(e)}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

# エイリアス（後方互換性のため）
add_qr_code = process_notion_webhook