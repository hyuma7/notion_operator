"""
ヤフオク出品ツールの設定・マッピング定義
"""

# ============================================================
# 出品用スキーマ: 表示するプロパティ（表示順）
# ============================================================
LISTING_DISPLAY_PROPERTIES = [
    # 基本情報
    "商品名",
    "ID",
    "型番",
    "型番名",           # rollup
    "メーカー",         # rollup
    "カテゴリー",       # rollup
    "ランク",
    "サイズ",           # rollup
    "年式",             # rollup
    "接続方法",         # rollup
    "寸法/インチ",
    # 説明文系
    "説明文",           # rollup
    "説明文HTML",       # rollup
    "追加説明文",
    "備考",
    # 画像
    "画像",             # rollup
    "個別画像",
    # 金額（出品価格の参考）
    "仕入れ金",
]

# 除外するプロパティ（計算系・利益系・配送料・内部管理系）
EXCLUDE_PROPERTIES = {
    # 計算系 (formula)
    "仕入れ手数料",
    "販売手数料",
    "利益率",
    "純利益",
    "仕入れ原価",
    # 配送・手数料関連
    "送料",
    "仕入手数料",
    "販売手数料率",
    "送料計算方法",
    # 内部管理系
    "作成日時",
    "仕入れ日",
    "売却日",
    "在庫状況",
    "売上金",
    "仕入れ先",
    "仕入れ先名",
    "仕入先カテゴリ",
    "販売先カテゴリ",
    "販売担当者",
    "販売媒体",
    "販売媒体名",
    "作業担当",
    "購入者名",
    "伝票番号",
    "商品ID",
    "画像URL",
}

# Notionプロパティ名 → ヤフオクフォーム項目のマッピング
PROPERTY_MAPPING = {
    # Notionプロパティ名: ヤフオクフィールド名
    "商品名": "title",           # タイトル（65文字以内）
    "説明文": "description",      # 商品説明（rollup）
    "追加説明文": "description",  # 商品説明（rich_text、説明文がなければこちら）
    "画像": "images",            # 画像（rollup）
    "個別画像": "images",        # 個別画像（files）
    "カテゴリー": "category",     # カテゴリ（rollup）
    "ランク": "condition",        # 商品の状態（select: A,B,C...）
    "仕入れ金": "start_price",   # 開始価格の参考値（number）
    "サイズ": "size",            # 商品サイズ（rollup）
    "メーカー": "brand",         # ブランド/メーカー（rollup）
    "備考": "notes",             # 備考（rich_text）
    "説明文HTML": "description_html",  # HTML説明文（rollup）
}

# ランク → ヤフオク商品状態のマッピング
CONDITION_MAPPING = {
    "S": "新品、未使用",
    "A": "未使用に近い",
    "B": "目立った傷や汚れなし",
    "C": "やや傷や汚れあり",
    "D": "傷や汚れあり",
    "E": "全体的に状態が悪い",
}

# デフォルト設定
DEFAULTS = {
    "auction_duration_days": 7,        # オークション期間（日）
    "shipping_payer": "seller",        # 送料負担: "seller"=出品者, "buyer"=落札者
    "shipping_region": "愛知県",       # 発送元の地域
    "shipping_method": "ゆうパック",    # 配送方法
    "returns_accepted": False,         # 返品可否
    "auto_extension": True,            # 自動延長
    "condition_default": "やや傷や汚れあり",  # デフォルト商品状態
}

# ヤフオクURL
YAHOO_AUCTION_URL = "https://auctions.yahoo.co.jp"
YAHOO_LOGIN_URL = "https://login.yahoo.co.jp/"
YAHOO_SELL_URL = "https://auctions.yahoo.co.jp/sell/jp/show/submit"

# Chrome設定
CHROME_PROFILE_DIR = "./chrome_profile"
COOKIE_FILE = "yahoo_cookies.pkl"

# 操作間の待機時間（秒）
WAIT_SHORT = 1
WAIT_MEDIUM = 2
WAIT_LONG = 3
