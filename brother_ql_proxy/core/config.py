"""
設定管理モジュール
"""

# 設定ファイル
CONFIG_FILE = "printer_proxy_config.json"
LOG_FILE = "printer_proxy.log"

# デフォルト設定
DEFAULT_CONFIG = {
    "printer_ip": "192.168.1.100",
    "printer_port": 9100,
    "label_size": "62",
    "font_size": 16,
    "qr_size_scale": 3,
    "notion_api_key": "",
    "notion_database_id": "1d254e6206d881bb9e88d2e7ffb90444"
}