import os
import json
import functions_framework
from notion_client import Client
from flask import jsonify, Request
import urllib.parse
from common.notion_auth import NotionAuth

# 環境変数の設定
NOTION_API_KEY = os.environ.get("NOTION_API_KEY")

# Notion認証の初期化
notion_auth = NotionAuth()
notion = notion_auth.get_client()

def generate_quickchart_qr_url(data: str, size: int = 300) -> str:
    """
    QuickChart APIを使用してQRコードのURLを生成する
    
    Args:
        data: QRコードに埋め込むデータ（URL等）
        size: QRコードの大きさ（ピクセル）
        
    Returns:
        QuickChart QR APIのURL
    """
    # URLエンコードしてQuickChart APIのURLを生成
    encoded_data = urllib.parse.quote(data)
    qr_url = f"https://quickchart.io/qr?text={encoded_data}&size={size}"
    
    return qr_url

def get_page_id_from_url(url: str) -> str:
    """
    NotionページのURLからページIDを抽出する
    
    Args:
        url: NotionページのURL
        
    Returns:
        ページID
    """
    # URLの最後の部分を取得（クエリパラメータを除く）
    if '?' in url:
        url = url.split('?')[0]
    
    # 最後のスラッシュ以降を取得
    page_id = url.split('/')[-1]
    
    # ハイフンが含まれていない場合はそのまま返す
    if '-' not in page_id:
        return page_id
    
    # ハイフンを含む場合は、正しいフォーマットに変換
    page_id = page_id.replace('-', '')
    
    return page_id

def add_image_to_notion(page_id: str, image_url: str, caption: str = "") -> dict:
    """
    Notionページに画像ブロックを追加する
    """
    response = notion.blocks.children.append(
        block_id=page_id,
        children=[
            {
                "object": "block",
                "type": "image",
                "image": {
                    "type": "external",
                    "external": {
                        "url": image_url
                    },
                    "caption": [
                        {
                            "type": "text", 
                            "text": {"content": caption}
                        }
                    ]
                }
            }
        ]
    )
    
    return response

def add_embed_to_notion(page_id: str, embed_url: str, after_block_id: str = None) -> dict:
    """
    Notionページに埋め込みブロックを追加する
    
    Args:
        page_id: NotionページのID
        embed_url: 埋め込むコンテンツのURL
        after_block_id: 指定された場合、このブロックの後に埋め込む。Noneの場合はページの先頭に追加
        
    Returns:
        Notion APIのレスポンス
    """
    append_params = {
        "block_id": page_id,
        "children": [
            {
                "object": "block",
                "type": "embed",
                "embed": {
                    "url": embed_url
                }
            }
        ]
    }
    
    # 特定のブロックの後に追加する場合
    if after_block_id:
        append_params["after"] = after_block_id
    
    response = notion.blocks.children.append(**append_params)
    
    return response

@functions_framework.http
def add_qr_code(request: Request):
    """
    HTTP関数のエントリポイント
    Notionからのデータを受け取り、QRコードを生成してNotionに追加する
    
    Notionの自動化からのリクエスト形式（例）:
    "{'source': {'type': 'automation', 'automation_id': '1db54e62-06d8-8041-822e-004d9b756239', 'action_id': '1db54e62-06d8-8074-9ae0-005a86ede7b8', 'event_id': '2d2145c9-2250-4444-be4f-f5fd642bca87', 'user_id': '5159ce3b-3cda-483d-a478-3c2761b798eb', 'attempt': 1}, 'data': {'object': 'page', 'id': '1d454e62-06d8-81db-b701-e93ee8c9f847', 'created_time': '2025-04-13T15:09:00.000Z', 'last_edited_time': '2025-04-20T09:19:00.000Z', 'created_by': {'object': 'user', 'id': '88bff1e4-f3db-403e-8090-30961a19301e'}, 'last_edited_by': {'object': 'user', 'id': '5159ce3b-3cda-483d-a478-3c2761b798eb'}, 'cover': {'type': 'file', 'file': {'url': 'https://prod-files-secure.s3.us-west-2.amazonaws.com/43beaec1-d675-4f67-a0b4-026dcf71b4e5/564cc933-14bc-48be-8778-252cd34fb2ef/%E3%82%B9%E3%82%AF%E3%83%AA%E3%83%BC%E3%83%B3%E3%82%B7%E3%83%A7%E3%83%83%E3%83%88_2025-04-18_000907.png?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&X-Amz-Credential=ASIAZI2LB466RMZRLOKI%2F20250420%2Fus-west-2%2Fs3%2Faws4_request&X-Amz-Date=20250420T093848Z&X-Amz-Expires=3600&X-Amz-Security-Token=IQoJb3JpZ2luX2VjEBYaCXVzLXdlc3QtMiJGMEQCIH1B%2BedmtDVPUwJswsuuvxHfxejD5Z%2Fp8Wnp87hlEhOMAiB2wMcJcui63%2B%2F5gOO3JHF9UUcKlJd%2BSkjKP27q8ThOsyqGBAif%2F%2F%2F%2F%2F%2F%2F%2F%2F%2F8BEAAaDDYzNzQyMzE4MzgwNSIM1figxhwlVbKa5H0eKtoD7QFK%2F9DXfQS7dmW2%2FCv1Oct0Gz6IJ426sowNEJgVgclRQRzMSg%2FZsauzCMwji%2FcgOaV8BYRVaFJSAqUe1C1dVK8lmCAkn7Dzu%2BguzYtR6yOlAnDkXCY0gxTGZWAdOw05oauXwYl24JrdRFoDhZBUGLHI0%2BmSnicEgIkrf0FUtWjSqD3ZKOSj3JnQw08UOjupGmylhQ80sVQgOv1a90Sos9I1G2krMegLxKTCXj9wZw01OxT8XRFVmzmL0f0jKwa7ZoFzJKCSd2RJKlPtE5bx1hrq926rgNpcmqN4gtwSGzjettdWwDWD0kJFpAEn4vislfmNTu6Nq5X%2FreGp9M8r7%2FliWUeMVlzHLo%2Fxf8DH7Ha%2BZH4zkEjENyW%2BtuDDbGP6fxiiYG5VqZ3h97i6otnEqCJ2vzLY4JhB8UMNTOAUp36BDVLQ9WjXEr8JDJxMo4spfgkcbjrE2gitBJbgGAjmneQyyhmbbfiN0kzCtN3pKwHL%2FfuS65KsaXA9LveQNDskGqGG%2BxZdInZ0juR4MfCci4P74Xr%2BA2%2BrYeWG6aWu%2B9cZi8yCtRdQ%2F5IOAciyMBOJEkWte3DvSLKwODb5WNGuKwYU0i1OvMLmf9MGXci31oAmzt6A9thvPf3YMLugksAGOqYBbSFNhGvMYbgOB6Wg8BkxeNsXL1W1H0ix9jA0jHulWZbbwJd9Ws4GM0LR53cRcaxJwX7BLS6syovt0De0xnCEPbuCjBfyqHVCQ%2F9CbxjscadnHl3R0pEpI97iy5Iu8j%2Fky%2BeHGcxHpPuyoL7Ocon75zZp9hQuO9XxjNCfXz1vLyIHnuRauoWGIHtXBfeDmvThX2FnniM%2FjYQOLrjbDsSfioadeIzNpg%3D%3D&X-Amz-Signature=58d90e3cd6859725d3e7a71cb2356873c32848bc8f502b95a5c78b625f4da839&X-Amz-SignedHeaders=host&x-id=GetObject', 'expiry_time': '2025-04-20T10:38:48.709Z'}}, 'icon': {'type': 'emoji', 'emoji': '🪦'}, 'parent': {'type': 'database_id', 'database_id': '1d254e62-06d8-81bb-9e88-d2e7ffb90444'}, 'archived': False, 'in_trash': False, 'properties': {}, 'url': 'https://www.notion.so/Nintendo-Switch-1d454e6206d881dbb701e93ee8c9f847', 'public_url': None, 'request_id': '84e27705-7664-4fe0-9d76-010b37c2b298'}}"
    
    または従来の形式:
    {
        "page_id": "Notionページのユニークな識別子（オプション）", 
        "page_url": "NotionページのURL（オプション、page_idが指定されていない場合に使用）",
        "data": "QRコードに埋め込むデータ",
        "size": "QRコードのサイズ（ピクセル、オプション）"
    }
    """
    try:
        # トークンの検証
        if not notion_auth.verify_token():
            return jsonify({"error": "無効なNotion APIトークンです"}), 401
        
        # ワークスペース情報の取得（ログ用）
        workspace_info = notion_auth.get_workspace_info()
        print(f"ワークスペース情報: {workspace_info}")
        
        # リクエストデータの取得
        request_data = request.get_json(silent=True)
        if not request_data:
            # JSONとして解析できない場合は、文字列として受け取る
            request_data = request.data.decode('utf-8')
        
        print(f"受信データ: {request_data}")
        
        # リクエストデータの検証
        if not request_data:
            return jsonify({"error": "リクエストデータが必要です"}), 400
        
        # 文字列の場合はJSONに変換
        if isinstance(request_data, str):
            try:
                # シングルクォートをダブルクォートに置換してJSON解析
                # 単純な置換では解析できない場合があるため、astモジュールを使用する方法も試みる
                try:
                    # まず通常の方法で試す
                    cleaned_data = request_data.replace("'", '"')
                    request_data = json.loads(cleaned_data)
                except json.JSONDecodeError:
                    # ast.literal_evalを試す
                    import ast
                    request_data = ast.literal_eval(request_data)
            except Exception as e:
                print(f"JSON解析エラー: {e}")
                return jsonify({"error": f"JSONの解析に失敗しました: {e}"}), 400
        
        print(f"解析後のデータ: {request_data}")
        
        # Notionの自動化からのリクエスト形式かどうかを確認
        if isinstance(request_data, dict) and "data" in request_data and isinstance(request_data["data"], dict):
            # Notionの自動化からのリクエスト
            notion_data = request_data["data"]
            page_id = notion_data.get("id")
            
            if not page_id:
                return jsonify({"error": "ページIDが見つかりません"}), 400
            
            # URLの取得
            page_url = notion_data.get("url") or notion_data.get("public_url") or ""
            
            # 送信元ブロックの情報（あれば）
            # 注意: 提供されたサンプルJSONには送信元ブロックIDのフィールドはない
            source_block_id = None
            # sourceオブジェクト内にblock_idがあれば取得
            if isinstance(request_data.get("source"), dict):
                source_block_id = request_data["source"].get("block_id")
            
            # QRコードに埋め込むデータ（ページURL）
            # URLがあればそれを使用、なければページIDをそのまま使用
            qr_data = page_url if page_url else f"https://www.notion.so/{page_id}"
            
            # QRコードのURL生成
            qr_url = generate_quickchart_qr_url(qr_data, 300)
            
            print(f"ページID: {page_id}, QRデータ: {qr_data}")
            print(f"生成したQR URL: {qr_url}")
            
            # Notionページに埋め込みブロックとして追加
            response = add_embed_to_notion(page_id, qr_url, source_block_id)
        else:
            # 従来の形式
            page_id = request_data.get("page_id")
            page_url = request_data.get("page_url")
            
            if not page_id and not page_url:
                return jsonify({"error": "page_idまたはpage_urlのいずれかを指定してください"}), 400
            
            # URLからページIDを抽出
            if not page_id and page_url:
                page_id = get_page_id_from_url(page_url)
            
            data = request_data.get("data")
            size = request_data.get("size", 300)
            
            if not data:
                return jsonify({"error": "dataは必須フィールドです"}), 400
            
            # QuickChart APIでQRコードURLを生成
            qr_url = generate_quickchart_qr_url(data, size)
            
            # Notionページに追加
            response = add_embed_to_notion(page_id, qr_url)
        
        return jsonify({
            "success": True,
            "message": "QRコードが正常に追加されました",
            "qr_url": qr_url,
            "page_id": page_id,
            "notion_response": response
        })
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"エラー: {error_details}")
        return jsonify({
            "error": str(e),
            "details": error_details
        }), 500