"""
プリンタープロキシのコアクラス
"""

import os
import json
import socket
import logging
from contextlib import contextmanager
from typing import Dict, Any

from .config import CONFIG_FILE, DEFAULT_CONFIG, LOG_FILE

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)


class PrinterProxy:
    def __init__(self):
        self.config = self.load_config()
        self.log_callbacks = []
        
    def load_config(self):
        """設定ファイルを読み込む"""
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return {**DEFAULT_CONFIG, **config}
        return DEFAULT_CONFIG.copy()
    
    def save_config(self):
        """設定ファイルを保存"""
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
    
    def add_log_callback(self, callback):
        """ログコールバックを追加"""
        self.log_callbacks.append(callback)
    
    def log(self, message, level="INFO"):
        """ログ出力"""
        logging.log(getattr(logging, level), message)
        for callback in self.log_callbacks:
            callback(f"[{level}] {message}")
    
    def test_printer_connection(self) -> Dict[str, Any]:
        """プリンター接続テスト"""
        try:
            printer_ip = self.config.get('printer_ip')
            printer_port = self.config.get('printer_port', 9100)
            
            self.log(f"プリンター接続テスト開始: IP={printer_ip}, Port={printer_port}")
            
            if not printer_ip:
                self.log("プリンターIPが設定されていません", "ERROR")
                return {"status": "error", "connected": False, "error": "プリンターIPが未設定"}
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex((printer_ip, printer_port))
            sock.close()
            
            if result == 0:
                self.log(f"プリンター {printer_ip}:{printer_port} に接続成功")
                return {"status": "success", "connected": True}
            else:
                self.log(f"プリンター接続失敗: エラーコード {result}", "ERROR")
                return {"status": "error", "connected": False, "error_code": result}
        except Exception as e:
            self.log(f"プリンター接続エラー: {e}", "ERROR")
            return {"status": "error", "connected": False, "error": str(e)}
    
    @contextmanager
    def printer_connection(self):
        """プリンター接続コンテキストマネージャー"""
        sock = None
        try:
            self.log(f"プリンターに接続中: {self.config['printer_ip']}:{self.config['printer_port']}")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect((self.config['printer_ip'], self.config['printer_port']))
            self.log("プリンター接続成功")
            yield sock
        finally:
            if sock:
                self.log("プリンター接続を閉じています")
                sock.close()
                self.log("プリンター接続を閉じました")
    
    def send_raw_data_to_printer(self, data: bytes) -> bool:
        """生データをプリンターに送信（CLIで印刷済みの場合は成功を返す）"""
        try:
            # CLI経由で既に印刷済みの場合
            if data == b'CLI_SUCCESS':
                self.log("CLI経由で印刷が完了しました")
                return True
            
            # 従来の生データ送信（レガシー対応）
            self.log(f"プリンターへの送信開始: {len(data)} bytes")
            
            with self.printer_connection() as sock:
                self.log("プリンターに接続しました")
                
                # データを分割して送信（大きなデータの場合）
                chunk_size = 1024
                total_sent = 0
                
                while total_sent < len(data):
                    chunk = data[total_sent:total_sent + chunk_size]
                    # 進捗を10%刻みでログ出力（詳細ログを減らす）
                    progress = (total_sent * 100) // len(data)
                    if progress % 10 == 0 and total_sent == (progress * len(data)) // 100:
                        self.log(f"送信進捗: {progress}% ({total_sent}/{len(data)} bytes)")
                    sent = sock.send(chunk)
                    if sent == 0:
                        raise RuntimeError("プリンターへの接続が失われました")
                    total_sent += sent
                
                self.log("データ送信完了、応答を待機中...")
                
                # 送信完了を待つ
                import time
                time.sleep(0.1)  # 短い待機時間
                
                self.log(f"プリンターにデータを送信しました ({len(data)} bytes)")
                return True
        except Exception as e:
            self.log(f"印刷エラー: {e}", "ERROR")
            return False
    
