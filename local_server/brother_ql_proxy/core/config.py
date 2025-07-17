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
    "proxy_port": 8080,
    "ngrok_authtoken": "",
    "enable_ngrok": False,
    "label_size": "62",
    "ngrok_domain": "",
    "ngrok_reserved_domain_id": ""
}