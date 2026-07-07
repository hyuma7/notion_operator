from typing import Optional, List, Any
from pydantic import BaseModel, ConfigDict, Field, field_validator
from datetime import date, datetime
import re

class NotionRecord(BaseModel):
    """Base class for Notion records"""
    id: Optional[str] = None
    created_time: Optional[datetime] = None

class SoldRecord(NotionRecord):
    """Represents a sold item record"""
    product_name: str = Field(alias="商品名", default="")
    sales_amount: float = Field(alias="売上金", default=0)
    profit: float = Field(alias="純利益", default=0)
    cost_price: float = Field(alias="仕入れ原価", default=0)
    commission: float = Field(alias="販売手数料", default=0)
    shipping_cost: float = Field(alias="送料", default=0)
    
    sold_date: Optional[date] = Field(alias="売却日", default=None)
    sold_year_month: Optional[str] = None # Calculated field
    
    supplier: str = Field(alias="仕入れ先名", default="不明")
    sales_channel: str = Field(alias="販売媒体名", default="不明")
    
    supplier_category: str = Field(alias="仕入先カテゴリ", default="その他")
    sales_channel_category: str = Field(alias="販売先カテゴリ", default="その他")

    assignee: Optional[str] = Field(alias="作業担当", default=None)
    sales_assignee: Optional[str] = Field(alias="販売担当者", default=None)  # ロールアップ

    @field_validator('sales_amount', 'profit', 'cost_price', 'commission', 'shipping_cost', mode='before')
    @classmethod
    def clean_currency(cls, v: Any) -> float:
        if v is None or v == "":
            return 0.0
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            # Remove currency symbols and commas
            v = v.replace('￥', '').replace(',', '').strip()
            try:
                return float(v)
            except ValueError:
                return 0.0
        return 0.0

    @field_validator('supplier', 'sales_channel', mode='before')
    @classmethod
    def clean_company_name(cls, v: Any) -> str:
        if v is None or v == "":
            return "不明"
        if isinstance(v, str):
             # Remove URL part if exists: "Name (https://...)"
            value = re.sub(r'\s*\(https://.*?\)', '', v)
            return value.strip()
        return str(v).strip()

    @field_validator('supplier_category', 'sales_channel_category', mode='before')
    @classmethod
    def clean_category(cls, v: Any) -> str:
        if v is None or v == "" or v == "不明":
            return "その他"
        # Notionから取得できた値をそのまま使用
        v_str = str(v).strip()
        return v_str if v_str else "その他"

class PurchaseRecord(NotionRecord):
    """Represents a purchase record (regardless of sold status)"""
    cost_price: float = Field(alias="仕入れ原価", default=0)
    supplier: str = Field(alias="仕入れ先名", default="不明") # Fallback to "仕入れ先" if "仕入れ先名" not found
    supplier_category: str = Field(alias="仕入先カテゴリ", default="その他")
    assignee: Optional[str] = Field(alias="作業担当", default=None)
    
    purchase_date: Optional[date] = Field(alias="仕入れ日", default=None) # 仕入れ日ベースで帰属月を計算
    purchase_year_month: Optional[str] = None # Calculated

    @field_validator('cost_price', mode='before')
    @classmethod
    def clean_currency(cls, v: Any) -> float:
        if v is None or v == "":
            return 0.0
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            v = v.replace('￥', '').replace(',', '').strip()
            try:
                return float(v)
            except ValueError:
                return 0.0
        return 0.0

    @field_validator('supplier', mode='before')
    @classmethod
    def clean_company_name(cls, v: Any) -> str:
        if v is None or v == "":
            return "不明"
        if isinstance(v, str):
            value = re.sub(r'\s*\(https://.*?\)', '', v)
            return value.strip()
        return str(v).strip()

    @field_validator('supplier_category', mode='before')
    @classmethod
    def clean_category(cls, v: Any) -> str:
        if v is None or v == "" or v == "不明":
            return "その他"
        # Notionから取得できた値をそのまま使用
        v_str = str(v).strip()
        return v_str if v_str else "その他"


class DailySoldRecord(NotionRecord):
    """日別出力用 売上レコード"""
    model_config = ConfigDict(protected_namespaces=())

    product_name: str = Field(alias="商品名", default="")
    model_number: str = Field(alias="型番名", default="")
    serial_number: str = Field(alias="製番", default="")
    maker: str = Field(alias="メーカー", default="")
    year: str = Field(alias="年式", default="")
    sold_date: Optional[date] = Field(alias="売却日", default=None)
    sales_amount: float = Field(alias="売上金", default=0)
    purchase_cost: float = Field(alias="仕入れ金", default=0)
    purchase_fee: Optional[float] = Field(alias="仕入れ手数料", default=None)
    cost_price: Optional[float] = Field(alias="仕入れ原価", default=None)
    trunk_line_fee: Optional[float] = Field(alias="幹線便料金", default=None)
    promotion: Optional[float] = Field(alias="プロモーション", default=None)
    shipping_cost: float = Field(alias="送料", default=0)
    shipping_method: str = Field(alias="送料計算方法", default="")
    commission: Optional[float] = Field(alias="販売手数料", default=None)
    profit: Optional[float] = Field(alias="純利益", default=None)
    profit_rate: Optional[float] = Field(alias="利益率", default=None)
    supplier: str = Field(alias="仕入れ先名", default="")
    purchase_date: Optional[date] = Field(alias="仕入れ日", default=None)
    sales_channel: str = Field(alias="販売媒体名", default="")
    assignee: str = Field(alias="作業担当", default="")
    slip_number: Optional[str] = Field(alias="伝票番号", default=None)
    shipping_slip_number: Optional[float] = Field(alias="発送伝票番号", default=None)
    buyer_name: Optional[str] = Field(alias="購入者名", default=None)

    @field_validator('sales_amount', 'purchase_cost', 'shipping_cost', mode='before')
    @classmethod
    def clean_currency(cls, v: Any) -> float:
        if v is None or v == "":
            return 0.0
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            v = v.replace('￥', '').replace(',', '').strip()
            try:
                return float(v)
            except ValueError:
                return 0.0
        return 0.0

    @field_validator('purchase_fee', 'cost_price', 'commission', 'profit', 'profit_rate', 'shipping_slip_number', 'trunk_line_fee', 'promotion', mode='before')
    @classmethod
    def clean_optional_number(cls, v: Any) -> Optional[float]:
        if v is None or v == "":
            return None
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            v = v.replace('￥', '').replace(',', '').replace('%', '').strip()
            try:
                return float(v)
            except ValueError:
                return None
        return None


class DailyPurchaseRecord(NotionRecord):
    """日別出力用 仕入れレコード"""
    model_config = ConfigDict(protected_namespaces=())

    product_name: str = Field(alias="商品名", default="")
    model_number: str = Field(alias="型番名", default="")
    serial_number: str = Field(alias="製番", default="")
    maker: str = Field(alias="メーカー", default="")
    category: str = Field(alias="カテゴリー", default="")
    size: str = Field(alias="サイズ", default="")
    year: str = Field(alias="年式", default="")
    rank: str = Field(alias="ランク", default="")
    purchase_date: Optional[date] = Field(alias="仕入れ日", default=None)
    purchase_cost: float = Field(alias="仕入れ金", default=0)
    purchase_fee: Optional[float] = Field(alias="仕入れ手数料", default=None)
    cost_price: Optional[float] = Field(alias="仕入れ原価", default=None)
    supplier: str = Field(alias="仕入れ先名", default="")
    supplier_category: str = Field(alias="仕入先カテゴリ", default="")
    stock_status: str = Field(alias="在庫状況", default="")
    assignee: str = Field(alias="作業担当", default="")
    estimated_sales: Optional[float] = Field(alias="売上金", default=None)

    @field_validator('purchase_cost', mode='before')
    @classmethod
    def clean_currency(cls, v: Any) -> float:
        if v is None or v == "":
            return 0.0
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            v = v.replace('￥', '').replace(',', '').strip()
            try:
                return float(v)
            except ValueError:
                return 0.0
        return 0.0

    @field_validator('purchase_fee', 'cost_price', 'estimated_sales', mode='before')
    @classmethod
    def clean_optional_number(cls, v: Any) -> Optional[float]:
        if v is None or v == "":
            return None
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            v = v.replace('￥', '').replace(',', '').strip()
            try:
                return float(v)
            except ValueError:
                return None
        return None
