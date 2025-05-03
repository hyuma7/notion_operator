import os
import jwt
from typing import Dict, Optional, List
from notion_client import Client
from functools import wraps
from flask import jsonify, Request

class NotionAuth:
    def __init__(self, allowed_workspaces: Optional[List[str]] = None):
        """
        NotionAuthクラスの初期化
        
        Args:
            allowed_workspaces: 許可されたワークスペースIDのリスト。Noneの場合は環境変数から取得
        """
        self.api_key = os.environ.get("NOTION_API_KEY")
        if not self.api_key:
            raise ValueError("NOTION_API_KEY environment variable is not set")
        
        self.client = Client(auth=self.api_key)
        
        # 許可されたワークスペースの設定
        if allowed_workspaces is None:
            workspaces_env = os.environ.get("ALLOWED_NOTION_WORKSPACES", "")
            self.allowed_workspaces = [ws.strip() for ws in workspaces_env.split(",")] if workspaces_env else []
        else:
            self.allowed_workspaces = allowed_workspaces
    
    def get_workspace_info(self) -> Dict:
        """
        Notion APIトークンからワークスペース情報を取得する
        
        Returns:
            Dict: ワークスペース情報を含む辞書
        """
        try:
            # トークンの検証と情報取得
            response = self.client.users.me()
            # Notion APIレスポンスの構造に合わせて修正
            # ワークスペースIDは実際のレスポンス構造で確認する必要あり
            bot_info = response.get("bot", {})
            workspace_id = bot_info.get("workspace_id")
            
            return {
                "workspace_id": workspace_id,
                "bot_id": response.get("id"),
                "bot_name": response.get("name")
            }
        except Exception as e:
            raise Exception(f"ワークスペース情報の取得に失敗しました: {str(e)}")
    
    def verify_token(self) -> bool:
        """
        Notion APIトークンの有効性を検証する
        
        Returns:
            bool: トークンが有効な場合はTrue
        """
        try:
            # トークンの検証（APIリクエストを実行）
            self.client.users.me()
            return True
        except Exception:
            return False
    
    def verify_workspace(self) -> bool:
        """
        リクエスト元のワークスペースが許可されたワークスペースかどうかを検証する
        
        Returns:
            bool: 許可されたワークスペースの場合はTrue
        """
        # 許可リストが空の場合は常に許可
        if not self.allowed_workspaces:
            return True
            
        try:
            # ワークスペース情報を取得
            workspace_info = self.get_workspace_info()
            workspace_id = workspace_info.get("workspace_id")
            
            # 許可されたワークスペースかどうかを確認
            return workspace_id in self.allowed_workspaces
        except Exception as e:
            print(f"ワークスペース検証エラー: {str(e)}")
            return False
    
    def get_client(self) -> Client:
        """
        Notionクライアントのインスタンスを取得する
        
        Returns:
            Client: Notionクライアントのインスタンス
        """
        return self.client

def require_notion_auth(f):
    """
    Notion認証を要求するデコレータ
    
    Args:
        f: デコレートする関数
        
    Returns:
        デコレートされた関数
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # リクエストオブジェクトを取得
        request = next((arg for arg in args if isinstance(arg, Request)), None)
        if not request:
            return jsonify({"error": "リクエストオブジェクトが見つかりません"}), 500
        
        # NotionAuthインスタンスを作成
        notion_auth = NotionAuth()
        
        # トークンの検証
        if not notion_auth.verify_token():
            return jsonify({"error": "無効なNotion APIトークンです"}), 401
        
        # ワークスペースの検証
        if not notion_auth.verify_workspace():
            workspace_info = notion_auth.get_workspace_info()
            return jsonify({
                "error": "許可されていないワークスペースからのリクエストです",
                "workspace_id": workspace_info.get("workspace_id")
            }), 403
        
        # 元の関数を実行
        return f(*args, **kwargs)
    
    return decorated_function