import os
import json
import logging
import socket
import time
import struct
import base64
from datetime import datetime
from contextlib import contextmanager
from typing import Dict, Any, Optional, List, Tuple

import functions_framework
from flask import jsonify, Request
from PIL import Image, ImageDraw, ImageFont
import qrcode

# ロギング設定
logging.basicConfig(level=logging.INFO)

# 環境変数
PRINTER_IP = os.environ.get('PRINTER_IP', '192.168.1.100')
PRINTER_MODEL = os.environ.get('PRINTER_MODEL', 'QL-820NWB')
LABEL_SIZE = os.environ.get('LABEL_SIZE', '62x29')
ALLOWED_DATABASE_IDS = os.environ.get('ALLOWED_DATABASE_IDS', '').split(',')
ALLOWED_DATABASE_IDS = [id.strip() for id in ALLOWED_DATABASE_IDS if id.strip()]

class PrinterError(Exception):
    pass

# Brother QL プリンター用の定数
QL_MODELS = {
    'QL-820NWB': {
        'model_code': 0x20,
        'tape_width': {
            '62': 62,
            '62x29': 62,
            '62x100': 62,
        }
    }
}

# ESC/P コマンド
ESC = b'\x1b'
QL_INIT = ESC + b'@'  # 初期化
QL_RASTER_MODE = ESC + b'ia\x01'  # ラスターモードに切り替え
QL_PRINT_INFO = ESC + b'iz'  # 印刷情報設定
QL_MEDIA_INFO = ESC + b'iS'  # メディア情報設定
QL_MARGINS = ESC + b'id\x00\x00'  # マージン設定
QL_COMPRESSION = b'M\x02'  # 圧縮モード設定

def test_printer_connectivity(printer_ip: str, port: int = 9100) -> Dict[str, Any]:
    """プリンターへの接続性をテスト"""
    results = {
        "ping_test": False,
        "port_test": False,
        "raw_socket_test": False,
        "details": []
    }
    
    # Pingテスト（簡易的なもの）
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex((printer_ip, port))
        if result == 0:
            results["ping_test"] = True
            results["port_test"] = True
            results["details"].append(f"ポート {port} は開いています")
        else:
            results["details"].append(f"ポート {port} への接続に失敗: エラーコード {result}")
        sock.close()
    except Exception as e:
        results["details"].append(f"接続テストエラー: {e}")
    
    return results

@contextmanager
def printer_connection(printer_ip: str, port: int = 9100, timeout: int = 30):
    """プリンター接続コンテキストマネージャー（改善版）"""
    sock = None
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            # ソケットの作成
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            
            # ソケットオプションの設定
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            
            # タイムアウトの設定（段階的に増やす）
            current_timeout = timeout * (attempt + 1)
            sock.settimeout(current_timeout)
            
            logging.info(f"プリンター接続試行 {attempt + 1}/{max_retries}: {printer_ip}:{port} (タイムアウト: {current_timeout}秒)")
            
            # 接続
            sock.connect((printer_ip, port))
            
            # 接続成功後、少し待機（プリンターの準備時間）
            time.sleep(0.5)
            
            logging.info(f"プリンター {printer_ip}:{port} に正常に接続しました")
            yield sock
            return
            
        except socket.timeout:
            logging.warning(f"接続タイムアウト (試行 {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
            else:
                # 最後の試行で接続性テストを実行
                test_results = test_printer_connectivity(printer_ip, port)
                logging.error(f"接続性テスト結果: {test_results}")
                raise PrinterError(f"{printer_ip}:{port}への接続タイムアウト。詳細: {test_results['details']}")
                
        except socket.error as e:
            logging.error(f"ソケットエラー: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
            else:
                raise PrinterError(f"プリンターに到達できません: {e}")
                
        except Exception as e:
            logging.error(f"予期しないエラー: {e}")
            raise PrinterError(f"プリンター接続中にエラーが発生しました: {e}")
            
        finally:
            if sock and not sock._closed:
                try:
                    sock.close()
                    logging.info("プリンター接続を閉じました")
                except:
                    pass

def pack_raster_line(line: bytes) -> bytes:
    """ラスターラインをパック（RLE圧縮）"""
    if not line:
        return b'Z\x00'
    
    # 非圧縮モードを使用
    return b'g\x00' + struct.pack('<H', len(line)) + line

def convert_image_to_raster(image: Image.Image, width_px: int) -> List[bytes]:
    """画像をラスターデータに変換"""
    # 画像を1ビット（白黒）に変換
    if image.mode != '1':
        image = image.convert('1')
    
    # 必要に応じてリサイズ
    if image.width != width_px:
        height = int(image.height * width_px / image.width)
        image = image.resize((width_px, height), Image.Resampling.LANCZOS)
    
    # ラスターデータを生成
    raster_lines = []
    for y in range(image.height):
        line_data = bytearray()
        for x in range(0, image.width, 8):
            byte = 0
            for bit in range(8):
                if x + bit < image.width:
                    # 黒ピクセルを1としてビットを設定
                    if image.getpixel((x + bit, y)) == 0:
                        byte |= (1 << (7 - bit))
            line_data.append(byte)
        raster_lines.append(bytes(line_data))
    
    return raster_lines

def send_to_printer(printer_ip: str, raster_lines: List[bytes], label_size: str = '62x29') -> bool:
    """プリンターにデータを送信（改善版）"""
    try:
        with printer_connection(printer_ip) as sock:
            # 送信バッファサイズを設定
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 8192)
            
            # ステータスリクエスト（オプション）
            # 一部のBrotherプリンターはステータス確認後の方が安定する
            try:
                sock.send(ESC + b'i' + b'S')
                time.sleep(0.2)
                # ステータスレスポンスを読み取る（ブロッキングを避けるため短いタイムアウト）
                sock.settimeout(1)
                try:
                    status = sock.recv(32)
                    logging.info(f"プリンターステータス: {status.hex()}")
                except socket.timeout:
                    pass
                sock.settimeout(30)
            except:
                pass
            
            # プリンター初期化
            sock.send(QL_INIT)
            time.sleep(0.2)
            
            # ラスターモードに設定
            sock.send(QL_RASTER_MODE)
            time.sleep(0.1)
            
            # 印刷情報設定
            print_info = QL_PRINT_INFO + bytes([
                0x80, 0x00, 0x00, 0x00,  # 印刷品質など
                0x00, 0x00, 0x00, 0x00,  # 予約
                0x00, 0x00, 0x00, 0x00   # 予約
            ])
            sock.send(print_info)
            time.sleep(0.1)
            
            # メディア情報設定（62mmラベル）
            media_info = QL_MEDIA_INFO + bytes([
                0x0e,  # メディアタイプ
                0x0b,  # メディア幅 (62mm)
                0x00,  # メディア長さ（連続）
                0x00, 0x00, 0x00, 0x00,  # 予約
                0x00,  # 予約
                0x00,  # 予約
                0x00,  # 予約
            ])
            sock.send(media_info)
            time.sleep(0.1)
            
            # マージン設定
            sock.send(QL_MARGINS)
            time.sleep(0.1)
            
            # 圧縮モード設定
            sock.send(QL_COMPRESSION)
            time.sleep(0.1)
            
            # ラスターデータ送信（バッチ処理）
            batch_size = 100  # 一度に送信するライン数
            for i in range(0, len(raster_lines), batch_size):
                batch = raster_lines[i:i+batch_size]
                batch_data = b''
                for line in batch:
                    batch_data += pack_raster_line(line)
                
                # バッチデータを送信
                sock.send(batch_data)
                
                # 送信間隔を調整（プリンターのバッファオーバーフロー防止）
                if i % (batch_size * 10) == 0:
                    time.sleep(0.1)
            
            # 印刷実行
            sock.send(b'\x1a')  # 印刷コマンド
            time.sleep(0.1)
            
            # フィード（必要に応じて）
            if '29' in label_size:
                sock.send(b'\x0c')  # フォームフィード
            
            logging.info("印刷データを正常に送信しました")
            return True
            
    except PrinterError as e:
        logging.error(f"プリンターエラー: {e}")
        return False
    except Exception as e:
        logging.error(f"印刷エラー: {e}", exc_info=True)
        return False

# 以下の関数は変更なし
def extract_notion_webhook_data(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """Notion自動化Webhookからデータを抽出"""
    
    # デバッグ用にリクエストデータをログ出力
    logging.info(f"Webhook payload structure: {json.dumps(request_data, indent=2, ensure_ascii=False)}")
    
    # エラーが含まれている場合
    if 'error' in request_data:
        logging.error(f"Request data contains error: {request_data['error']}")
    
    # 期待されるプロパティ名（日本語対応）
    property_mappings = {
        'name': ['商品名', 'Name', '名前', 'Title', 'タイトル', '名称'],
        'id': ['ID', 'id', '商品ID', 'ItemID'],
        'year': ['年式', 'Year', '年度', '製造年'],
        'supplier': ['仕入れ先', 'Supplier', '仕入先', '供給元', 'Vendor'],
        'category': ['カテゴリー', 'Category', '分類', 'Type', 'タイプ'],
        'date': ['日付', 'Date', '登録日', 'CreatedAt'],
    }
    
    # デフォルト値
    result = {
        'name': 'アイテム',
        'id': 'NO_ID',
        'year': '',
        'supplier': '',
        'category': '未分類',
        'date': datetime.utcnow().strftime("%Y-%m-%d"),
        'database_id': '',
        'page_id': '',
        'page_url': ''
    }
    
    # raw_dataが含まれている場合（フォールバック）
    if 'raw_data' in request_data and isinstance(request_data['raw_data'], str):
        # 簡単なキー=値形式のパースを試みる
        raw = request_data['raw_data']
        for line in raw.split('&'):
            if '=' in line:
                key, value = line.split('=', 1)
                # URLデコード
                from urllib.parse import unquote
                key = unquote(key)
                value = unquote(value)
                request_data[key] = value
    
    # データベースID、ページIDとURLの取得
    if 'database_id' in request_data:
        result['database_id'] = request_data['database_id']
    if 'page_id' in request_data:
        result['page_id'] = request_data['page_id']
    if 'page_url' in request_data:
        result['page_url'] = request_data['page_url']
    
    # プロパティの取得（Notion自動化はプロパティを直接送信）
    # 様々な可能性のある構造に対応
    properties = {}
    
    # ケース1: プロパティが直接ルートレベルにある場合
    if any(key in request_data for mapping in property_mappings.values() for key in mapping):
        properties = request_data
    
    # ケース2: 'properties' キーの下にある場合
    elif 'properties' in request_data:
        properties = request_data['properties']
    
    # ケース3: 'data' キーの下にある場合
    elif 'data' in request_data:
        if isinstance(request_data['data'], dict):
            if 'properties' in request_data['data']:
                properties = request_data['data']['properties']
            else:
                properties = request_data['data']
    
    # プロパティから値を抽出
    for key, possible_names in property_mappings.items():
        for prop_name in possible_names:
            if prop_name in properties:
                value = properties[prop_name]
                
                # 値が辞書の場合（Notionの構造化データ）
                if isinstance(value, dict):
                    # タイトル型
                    if 'title' in value and isinstance(value['title'], list) and value['title']:
                        result[key] = value['title'][0].get('plain_text', '')
                    # リッチテキスト型
                    elif 'rich_text' in value and isinstance(value['rich_text'], list) and value['rich_text']:
                        result[key] = value['rich_text'][0].get('plain_text', '')
                    # セレクト型
                    elif 'select' in value and value['select']:
                        result[key] = value['select'].get('name', '')
                    # 日付型
                    elif 'date' in value and value['date']:
                        result[key] = value['date'].get('start', '')
                    # 数値型
                    elif 'number' in value:
                        result[key] = str(value['number'])
                    # その他の場合は文字列として扱う
                    else:
                        result[key] = str(value)
                # 値が文字列の場合はそのまま使用
                elif isinstance(value, (str, int, float)):
                    result[key] = str(value)
                
                # 値が見つかったら次のキーへ
                if result[key]:
                    break
    
    # IDが空の場合は生成
    if not result['id'] or result['id'] == 'NO_ID':
        result['id'] = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    
    return result

def create_product_label(product_data: Dict[str, Any]) -> Tuple[Image.Image, str]:
    """商品ラベルを作成"""
    
    # ラベルサイズに応じた寸法を設定
    if LABEL_SIZE == '62x29':
        width_px, height_px = 696, 271
    elif LABEL_SIZE == '62x100':
        width_px, height_px = 696, 1109
    else:
        # デフォルトは62x29mm
        width_px, height_px = 696, 271
    
    # 白い背景でラベルを作成
    label = Image.new('RGB', (width_px, height_px), 'white')
    draw = ImageDraw.Draw(label)
    
    # QRコードデータを生成
    qr_data = {
        'id': product_data['id'],
        'name': product_data['name'],
        'year': product_data['year'],
        'supplier': product_data['supplier'],
        'timestamp': datetime.utcnow().isoformat(),
        'page_id': product_data['page_id'],
        'page_url': product_data['page_url']
    }
    
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
        qr_img = qr_img.resize((qr_size, qr_size), Image.Resampling.LANCZOS)
        label.paste(qr_img, (20, 20))
        
        text_x = qr_size + 40
        text_y = 20
        
        # コンパクトなフォントサイズ
        font_sizes = {'title': 20, 'details': 14}
        line_height = 22
    else:
        # 縦レイアウト（上にQR、下にテキスト）
        qr_size = min(width_px - 40, int(height_px * 0.4))
        qr_img = qr_img.resize((qr_size, qr_size), Image.Resampling.LANCZOS)
        qr_x = (width_px - qr_size) // 2
        label.paste(qr_img, (qr_x, 20))
        
        text_x = 20
        text_y = qr_size + 40
        
        font_sizes = {'title': 24, 'details': 18}
        line_height = 28
    
    # デフォルトフォントを使用
    try:
        font_title = ImageFont.load_default()
        font_details = ImageFont.load_default()
    except:
        font_title = None
        font_details = None
    
    # 商品名を描画（大きめのフォント）
    title = product_data['name'][:30]
    draw.text((text_x, text_y), title, fill='black', font=font_title)
    
    # 詳細情報を描画
    details = [
        f"ID: {product_data['id']}",
        f"年式: {product_data['year']}" if product_data['year'] else None,
        f"仕入先: {product_data['supplier']}" if product_data['supplier'] else None,
        f"分類: {product_data['category']}",
        f"日付: {product_data['date']}"
    ]
    
    detail_y = text_y + 30
    for detail in details:
        if detail and detail_y < height_px - 20:
            draw.text((text_x, detail_y), detail[:40], fill='black', font=font_details)
            detail_y += line_height
    
    return label, LABEL_SIZE

@functions_framework.http
def process_notion_webhook(request: Request):
    """
    Notion自動化Webhookを処理してラベルを印刷
    """
    try:
        # CORSヘッダーの設定
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, X-Workspace-ID'
        }
        
        # OPTIONSリクエストへの対応
        if request.method == 'OPTIONS':
            return '', 204, headers
        
        # プリンター接続テスト（GETリクエスト）
        if request.method == 'GET' and request.args.get('test_connection'):
            test_results = test_printer_connectivity(PRINTER_IP)
            return jsonify({
                "status": "test_complete",
                "printer_ip": PRINTER_IP,
                "test_results": test_results,
                "timestamp": datetime.utcnow().isoformat()
            }), 200, headers
        
        # リクエストデータの取得
        request_data = None
        content_type = request.headers.get('Content-Type', '')
        
        # デバッグ用
        logging.info(f"Request headers: {dict(request.headers)}")
        logging.info(f"Content-Type: {content_type}")
        
        try:
            # まず通常のJSONパースを試みる
            if 'application/json' in content_type:
                try:
                    request_data = request.get_json(silent=True)
                except Exception as e:
                    logging.warning(f"JSON parse error: {e}")
            
            # JSONパースが失敗した場合、生データを処理
            if request_data is None:
                raw_data = request.data
                
                if raw_data:
                    # 様々なエンコーディングを試す
                    encodings = ['utf-8', 'shift_jis', 'euc-jp', 'iso-2022-jp', 'utf-16', 'latin-1']
                    decoded_data = None
                    
                    for encoding in encodings:
                        try:
                            decoded_data = raw_data.decode(encoding)
                            logging.info(f"Successfully decoded with {encoding}")
                            break
                        except UnicodeDecodeError:
                            continue
                    
                    if decoded_data:
                        # JSONとして解析を試みる
                        try:
                            request_data = json.loads(decoded_data)
                        except json.JSONDecodeError:
                            # JSONでない場合、フォームデータとして解析
                            if 'application/x-www-form-urlencoded' in content_type:
                                # URLエンコードされたデータを解析
                                from urllib.parse import parse_qs
                                parsed = parse_qs(decoded_data)
                                request_data = {k: v[0] if len(v) == 1 else v for k, v in parsed.items()}
                            else:
                                # それでも失敗した場合は、生データを辞書に入れる
                                request_data = {"raw_data": decoded_data}
                    else:
                        # デコードできない場合は、バイナリデータとして扱う
                        logging.error(f"Failed to decode data. First 100 bytes: {raw_data[:100]}")
                        request_data = {"error": "Failed to decode request data"}
                else:
                    request_data = {}
                    
        except Exception as e:
            logging.error(f"Error processing request data: {e}", exc_info=True)
            request_data = {"error": str(e)}
        
        logging.info(f"受信データ (Content-Type: {content_type}): {request_data}")
        
        # データベースIDの検証（設定されている場合）
        if ALLOWED_DATABASE_IDS:
            # リクエストからデータベースIDを取得
            database_id = None
            
            # 様々な場所からデータベースIDを探す
            if request_data:
                # 直接含まれている場合
                database_id = request_data.get('database_id', '')
                
                # URLパラメータから
                if not database_id:
                    database_id = request.args.get('database_id', '')
                
                # ヘッダーから
                if not database_id:
                    database_id = request.headers.get('X-Database-ID', '')
            
            # データベースIDが見つからない場合
            if not database_id:
                logging.warning("データベースIDが提供されていません")
                return jsonify({
                    "status": "error",
                    "message": "データベースIDが必要です",
                    "hint": "URLパラメータ(?database_id=xxx)またはリクエストボディにdatabase_idを含めてください"
                }), 400, headers
            
            # 許可されたデータベースIDかチェック
            if database_id not in ALLOWED_DATABASE_IDS:
                logging.warning(f"許可されていないデータベースID: {database_id}")
                return jsonify({
                    "status": "error",
                    "message": "認証エラー: 許可されていないデータベース"
                }), 403, headers
        
        # テストリクエストの場合
        if request_data and request_data.get("test", False):
            return jsonify({
                "status": "success",
                "message": "テスト接続成功",
                "timestamp": datetime.utcnow().isoformat(),
                "printer_ip": PRINTER_IP,
                "label_size": LABEL_SIZE
            }), 200, headers
        
        # データがない場合
        if not request_data:
            return jsonify({
                "status": "error", 
                "message": "リクエストデータが必要です",
                "hint": "POSTリクエストのボディにJSONデータを含めてください"
            }), 400, headers
        
        # Notionデータを抽出
        product_data = extract_notion_webhook_data(request_data)
        
        # ラベルを作成
        label_image, label_size = create_product_label(product_data)
        
        # ラスターデータに変換
        raster_lines = convert_image_to_raster(label_image, 696)  # 62mm = 696px at 300dpi
        
        # プリンターに送信
        success = send_to_printer(PRINTER_IP, raster_lines, label_size)
        
        if success:
            return jsonify({
                "status": "success",
                "message": "ラベルが正常に印刷されました",
                "label_id": product_data['id'],
                "printed_data": {
                    "商品名": product_data['name'],
                    "ID": product_data['id'],
                    "年式": product_data['year'],
                    "仕入れ先": product_data['supplier'],
                    "カテゴリー": product_data['category'],
                    "日付": product_data['date']
                }
            }), 200, headers
        else:
            return jsonify({
                "status": "error",
                "message": "印刷に失敗しました",
                "printer_ip": PRINTER_IP
            }), 500, headers
            
    except Exception as e:
        logging.error(f"ウェブフック処理エラー: {str(e)}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": str(e),
            "type": type(e).__name__
        }), 500