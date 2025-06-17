import os
import json
import io
import time
import datetime as dt
from urllib.parse import urlencode

import functions_framework
from flask import jsonify, Request
from notion_client import Client
from PIL import Image, ImageDraw, ImageFont
from google.cloud import storage
import qrcode

# ── 環境変数 ───────────────────────────────────
NOTION_API_KEY = os.environ.get("NOTION_API_KEY")
GCS_BUCKET     = os.environ.get("GCS_BUCKET")      # 必須

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

# ── ラベル生成 ──────────────────────────────────
def create_product_label_with_qr(
    product_info: dict,
    page_url: str,
    width: int = 800,
    height: int = 400,
) -> io.BytesIO:
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    # フォント
    try:
        title_font  = load_font(36, bold=True)
        normal_font = load_font(24)
    except Exception as e:
        print("FONT WARNING:", e)
        title_font = normal_font = ImageFont.load_default()

    # タイトル
    draw.text((20, 20), "【商品情報】", font=title_font, fill="black")

    # 表示対象プロパティのみ
    y = 80
    for key in DISPLAY_PROPERTIES:
        if key in product_info:
            draw.text((40, y), f"{key}: {product_info[key]}", font=normal_font, fill="black")
            y += 40

    # QR
    qr_img = create_qr_code(page_url)
    qr_pos = (width - qr_img.width - 40, 80)
    img.paste(qr_img, qr_pos)

    # キャプション
    draw.text((qr_pos[0], qr_pos[1] + qr_img.height + 10),
              "製品ページへアクセス", font=normal_font, fill="black")

    # 枠
    draw.rectangle([(10, 10), (width - 10, height - 10)], outline="black", width=2)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

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

        # ラベル生成
        img_data = create_product_label_with_qr(product, page_url)

        # アップロード
        file_name = f"qr_codes/{page_id}_{int(time.time())}.png"
        image_url = upload_image_to_cloud_storage(img_data, file_name)

        # Notion に追加
        caption = "商品情報ラベル（QR＋自動生成）"
        notion_res = add_image_to_notion(page_id, image_url, caption)

        return jsonify({
            "success": True,
            "image_url": image_url,
            "page_id": page_id,
            "notion_response": notion_res
        })

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(tb)
        return jsonify({"error": str(e), "trace": tb}), 500


# ── Cloud Run 単体テスト用 ──────────────────────
#   Cloud Functions では不要だが、ローカル or Cloud Run デバッグで
#   `PORT=8080 python main.py` とすれば起動確認できる。
if __name__ == "__main__":
    # Cloud Functions では不要だが、ローカル実行のために target 名を指定
    app = functions_framework.create_app(target="handle_create_product_label")
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)))

