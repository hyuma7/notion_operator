from typing import Optional, List, Any
from pydantic import BaseModel, Field, field_validator
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
    
    purchase_date: Optional[datetime] = Field(alias="Created time", default=None) # Using Created time as purchase date
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
