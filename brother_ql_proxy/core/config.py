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
    "notion_database_id": "1d254e6206d881bb9e88d2e7ffb90444",
    "issuer_company_name": "株式会社 アーネスト",
    "issuer_representative": "代表取締役　齊藤 淳",
    "issuer_address": "〒225-0025 神奈川県横浜市青葉区鉄町25-8",
    "issuer_tel": "TEL：045-507-6784　FAX：045-507-6804",
    "issuer_invoice_number": "",
    "issuer_stamp_lines": ["株式会社", "アーネスト", "代表取締役", "齊藤 淳"],
    "issuer_stamp_image_path": "",
}
