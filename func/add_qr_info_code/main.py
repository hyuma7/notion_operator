import os
import json
import io
import time
import datetime as dt
from urllib.parse import urlencode
import base64
import struct
import requests

import functions_framework
from flask import jsonify, Request
from notion_client import Client
from PIL import Image, ImageDraw, ImageFont
from google.cloud import storage
import qrcode

# ── 環境変数 ───────────────────────────────────
NOTION_API_KEY = os.environ.get("NOTION_API_KEY")
GCS_BUCKET     = os.environ.get("GCS_BUCKET")
PRINTER_PROXY_URL = os.environ.get("PRINTER_PROXY_URL")  # プリンタープロキシのURL

# ── Notion クライアント ────────────────────────
notion = Client(auth=NOTION_API_KEY)

# Notion 側でラベルに載せたいプロパティ
DISPLAY_PROPERTIES = ["商品名", "型番", "ID"]

# ── フォント設定 ───────────────────────────────
FONT_DIR      = os.path.join(os.path.dirname(__file__), "fonts")
JP_FONT_PATH  = os.path.join(FONT_DIR, "NotoSansJP-Regular.otf")

def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """
    日本語対応フォントを優先してロード。
    フォントが見つからない場合はデフォルトフォントを使用。
    """
    try:
        path = JP_FONT_PATH
        if bold:
            bold_path = JP_FONT_PATH.replace("Regular", "Bold")
            if os.path.exists(bold_path):
                path = bold_path
        
        if os.path.exists(path):
            return ImageFont.truetype(path, size, encoding="unic")
    except Exception as e:
        print(f"フォント読み込みエラー: {e}")
    
    # フォントが見つからない場合はデフォルトフォントを使用
    return ImageFont.load_default()

# ── QR 生成 ────────────────────────────────────
def create_qr_code(data: str, size: int = 200) -> Image.Image:
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    return qr_img.resize((size, size))

# ── ラベル生成（Brother QL対応） ──────────────────
def create_product_label_for_brother(
    product_info: dict,
    page_url: str,
    label_size: str = "62x29"
) -> Image.Image:
    """
    Brother QLプリンター用のラベル画像を生成
    label_size: "62x29" or "62x100"
    """
    # Brother QLの解像度に合わせたサイズ設定
    if label_size == "62x29":
        width, height = 696, 271  # 62mm x 29mm at 300dpi
    else:
        width, height = 696, 1109  # 62mm x 100mm at 300dpi
    
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    # フォントサイズを調整
    try:
        if label_size == "62x29":
            title_font  = load_font(24, bold=True)
            normal_font = load_font(16)
            qr_size = 150
        else:
            title_font  = load_font(36, bold=True)
            normal_font = load_font(24)
            qr_size = 200
    except Exception as e:
        print("FONT WARNING:", e)
        title_font = normal_font = ImageFont.load_default()
        qr_size = 150

    # レイアウト調整
    margin = 10
    y_start = margin
    
    # タイトル
    draw.text((margin, y_start), "【商品情報】", font=title_font, fill="black")
    y = y_start + 40

    # QRコードを右側に配置
    qr_img = create_qr_code(page_url, qr_size)
    qr_x = width - qr_img.width - margin
    qr_y = y
    img.paste(qr_img, (qr_x, qr_y))

    # テキスト情報を左側に配置
    text_width = qr_x - margin * 2
    for key in DISPLAY_PROPERTIES:
        if key in product_info:
            text = f"{key}: {product_info[key]}"
            # テキストが長い場合は折り返す
            if draw.textlength(text, font=normal_font) > text_width:
                # 簡易的な折り返し処理
                value = str(product_info[key])
                draw.text((margin, y), f"{key}:", font=normal_font, fill="black")
                y += 25
                draw.text((margin + 20, y), value[:20], font=normal_font, fill="black")
                if len(value) > 20:
                    y += 25
                    draw.text((margin + 20, y), value[20:40], font=normal_font, fill="black")
            else:
                draw.text((margin, y), text, font=normal_font, fill="black")
            y += 30

    # 日時を追加
    now = dt.datetime.now().strftime("%Y/%m/%d %H:%M")
    draw.text((margin, height - 30), f"印刷日時: {now}", font=normal_font, fill="gray")

    return img

# ── Brother QLフォーマット変換 ─────────────────
def convert_to_brother_format(image: Image.Image, label_size: str = "62x29") -> bytes:
    """
    画像をBrother QLプリンター形式に変換
    """
    ESC = b'\x1b'
    data = b''
    
    # 初期化
    data += ESC + b'@'
    
    # ラスターモード
    data += ESC + b'ia\x01'
    
    # 印刷情報（62mmラベル用）
    if label_size == "62x29":
        # 29mmラベル
        data += ESC + b'iz' + bytes([0x80, 0x00, 0x1d, 0x0a, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
    else:
        # 100mmラベル
        data += ESC + b'iz' + bytes([0x80, 0x00, 0x64, 0x0a, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
    
    # メディア情報
    data += ESC + b'iS' + bytes([0x0e, 0x0b, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
    
    # マージン
    data += ESC + b'id\x00\x00'
    
    # 圧縮モード
    data += b'M\x02'
    
    # 画像を1ビットに変換
    if image.mode != '1':
        image = image.convert('1')
    
    # ラスターデータ（パックビット圧縮）
    for y in range(image.height):
        line_data = bytearray()
        for x in range(0, image.width, 8):
            byte = 0
            for bit in range(8):
                if x + bit < image.width:
                    if image.getpixel((x + bit, y)) == 0:
                        byte |= (1 << (7 - bit))
            line_data.append(byte)
        
        # ラスターグラフィックス転送
        data += b'g\x00' + struct.pack('<H', len(line_data)) + bytes(line_data)
    
    # 印刷コマンド
    data += b'\x1a'
    
    # フィード（カット位置まで）
    if '29' in label_size:
        data += b'\x0c'
    
    return data

# ── GCS アップロード ───────────────────────────
def upload_image_to_cloud_storage(image_data: io.BytesIO, destination_path: str | None = None) -> str:
    """
    image_data  : BytesIO
    destination_path: バケット内パス。未指定なら自動生成。
    return      : 公開 URL
    """
    if destination_path is None:
        ts = dt.datetime.utcnow().strftime("%Y%m%d%H%M%S")
        destination_path = f"qr_codes/{ts}.png"

    client = storage.Client()
    bucket = client.bucket(GCS_BUCKET)
    blob   = bucket.blob(destination_path)

    image_data.seek(0)
    blob.upload_from_file(image_data, content_type="image/png")
    blob.make_public()

    return blob.public_url

# ── プリンターへの送信 ──────────────────────────
def send_to_printer(raster_data: bytes, printer_url: str) -> dict:
    """
    Brother QLプリンタープロキシサーバーにデータを送信
    """
    try:
        response = requests.post(
            f"{printer_url}/print/raw",
            data=raster_data,
            headers={"Content-Type": "application/octet-stream"},
            timeout=30
        )
        return response.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ── Notion 画像追加 ────────────────────────────
def add_image_to_notion(page_id: str, image_url: str, caption: str = "") -> dict:
    return notion.blocks.children.append(
        block_id=page_id,
        children=[{
            "object": "block",
            "type": "image",
            "image": {
                "type": "external",
                "external": {"url": image_url},
                "caption": [{"type": "text", "text": {"content": caption}}]
            }
        }]
    )

# ── Webhook から商品情報抽出 ───────────────────
def extract_product_info_from_notion_webhook(webhook_data) -> dict:
    product_info = {}
    props = webhook_data.get("data", {}).get("properties", {})
    for key, prop in props.items():
        tp = prop.get("type")
        if tp in ("rich_text", "title"):
            texts = prop[tp]
            if texts:
                product_info[key] = texts[0]["text"]["content"]
        elif tp == "unique_id":
            pfx = prop["unique_id"].get("prefix", "")
            num = prop["unique_id"].get("number", "")
            product_info[key] = f"{pfx}-{num}"
        elif tp == "relation" and prop["relation"]:
            rel_id = prop["relation"][0]["id"]
            try:
                rel_page = notion.pages.retrieve(page_id=rel_id)
                rel_props = rel_page.get("properties", {})
                if "型番" in rel_props and rel_props["型番"]["type"] == "rich_text":
                    rel_text = rel_props["型番"]["rich_text"]
                    if rel_text:
                        product_info[key] = rel_text[0]["text"]["content"]
            except Exception:
                product_info[key] = f"関連ID: {rel_id}"
    return product_info

# ── Cloud Functions Entrypoint ──────────────────
@functions_framework.http
def handle_create_product_label(request: Request):
    try:
        req_json = request.get_json(silent=True) or {}
        if not req_json:
            # フォーム / 文字列で来た場合のフォールバック
            raw = request.data.decode("utf-8")
            try:
                req_json = json.loads(raw.replace("'", '"'))
            except Exception:
                import ast
                req_json = ast.literal_eval(raw)

        print("RAW:", req_json)

        # オプションパラメータ
        label_size = req_json.get("label_size", "62x29")
        print_directly = req_json.get("print_directly", False)
        save_to_notion = req_json.get("save_to_notion", True)

        # ----- パターン 1: Notion Webhook -----
        if isinstance(req_json, dict) and "source" in req_json and "data" in req_json:
            page_id  = req_json["data"].get("id")
            page_url = req_json["data"].get("url", "")
            product  = extract_product_info_from_notion_webhook(req_json)

        # ----- パターン 2: 任意 JSON -----
        elif "page_url" in req_json and "product_info" in req_json:
            page_url = req_json["page_url"]
            page_id  = page_url.split("/")[-1].replace("-", "")
            product  = req_json["product_info"]

        else:
            return jsonify({"error": "サポート外のデータ形式"}), 400

        # 必須チェック
        if not all([page_id, page_url, product]):
            return jsonify({"error": "page_id / page_url / product_info が不足"}), 400

        # Brother QL用ラベル生成
        label_img = create_product_label_for_brother(product, page_url, label_size)

        response_data = {
            "success": True,
            "page_id": page_id,
            "label_size": label_size
        }

        # GCSに保存（Notion表示用）
        if save_to_notion:
            img_buf = io.BytesIO()
            label_img.save(img_buf, format="PNG")
            img_buf.seek(0)
            
            file_name = f"qr_codes/{page_id}_{int(time.time())}.png"
            image_url = upload_image_to_cloud_storage(img_buf, file_name)
            response_data["image_url"] = image_url

            # Notion に追加
            caption = f"商品情報ラベル（{label_size}mm）"
            notion_res = add_image_to_notion(page_id, image_url, caption)
            response_data["notion_response"] = notion_res

        # プリンターに直接送信
        if print_directly and PRINTER_PROXY_URL:
            # Brother QLフォーマットに変換
            raster_data = convert_to_brother_format(label_img, label_size)
            
            # プリンタープロキシに送信
            print_result = send_to_printer(raster_data, PRINTER_PROXY_URL)
            response_data["print_result"] = print_result
            
            if print_result.get("status") == "error":
                response_data["warning"] = f"印刷エラー: {print_result.get('message')}"

        return jsonify(response_data)

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(tb)
        return jsonify({"error": str(e), "trace": tb}), 500

# ── テスト用エンドポイント ──────────────────────
@functions_framework.http
def test_print_label(request: Request):
    """
    テスト印刷用エンドポイント
    """
    try:
        req_json = request.get_json(silent=True) or {}
        
        # テストデータ
        test_product = {
            "商品名": req_json.get("product_name", "テスト商品"),
            "型番": req_json.get("model_number", "TEST-001"),
            "ID": req_json.get("id", "12345")
        }
        
        test_url = req_json.get("url", "https://example.com/test")
        label_size = req_json.get("label_size", "62x29")
        
        # ラベル生成
        label_img = create_product_label_for_brother(test_product, test_url, label_size)
        
        # Brother QLフォーマットに変換
        raster_data = convert_to_brother_format(label_img, label_size)
        
        # Base64エンコードして返す（デバッグ用）
        if req_json.get("return_base64", False):
            return jsonify({
                "success": True,
                "raster_data_base64": base64.b64encode(raster_data).decode('utf-8'),
                "data_size": len(raster_data)
            })
        
        # プリンターに送信
        if PRINTER_PROXY_URL:
            print_result = send_to_printer(raster_data, PRINTER_PROXY_URL)
            return jsonify({
                "success": True,
                "print_result": print_result
            })
        else:
            return jsonify({
                "error": "PRINTER_PROXY_URL が設定されていません"
            }), 400
            
    except Exception as e:
        import traceback
        return jsonify({
            "error": str(e),
            "trace": traceback.format_exc()
        }), 500