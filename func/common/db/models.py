from typing import List, Optional, Union, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
from notion_client import Client
from pydantic_notion import NotionModel, NotionDatabase, NotionProperty


# ステータス用Enum定義
class StockStatus(str, Enum):
    IN_STOCK = "在庫あり"
    RESERVED = "予約済"
    SOLD = "売却済"


class Phase(str, Enum):
    RECEIVED = "入荷"
    CHECKING = "状態確認中"
    READY = "販売待機中"
    ON_SALE = "販売中"
    SOLD = "売却済み"
    OTHER = "その他"


class Rank(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"


class Platform(str, Enum):
    STORE = "店舗"
    MERCARI = "メルカリ"
    RAKUMA = "ラクマ"
    YAHOO = "ヤフオク"
    OTHER = "その他"


class TransactionType(str, Enum):
    SUPPLIER = "仕入先"
    CUSTOMER = "販売先"


# カテゴリー一覧モデル
class Category(NotionModel):
    name: str = NotionProperty(title=True)
    main_category: Optional[str] = NotionProperty(rich_text=True)
    mercari_1: Optional[str] = NotionProperty(rich_text=True)
    mercari_2: Optional[str] = NotionProperty(rich_text=True)
    mercari_3: Optional[str] = NotionProperty(rich_text=True)
    rakuma_1: Optional[str] = NotionProperty(rich_text=True)
    rakuma_2: Optional[str] = NotionProperty(rich_text=True)
    paypay_1: Optional[str] = NotionProperty(rich_text=True)
    paypay_2: Optional[str] = NotionProperty(rich_text=True)
    yahoo_1: Optional[str] = NotionProperty(rich_text=True)
    ebay_1: Optional[str] = NotionProperty(rich_text=True)
    memo: Optional[str] = NotionProperty(rich_text=True)


# 製品番号一覧モデル
class ProductType(NotionModel):
    type_number: str = NotionProperty(title=True)
    category_id: Optional[str] = NotionProperty(relation=True)
    description: Optional[str] = NotionProperty(rich_text=True)
    description_html: Optional[str] = NotionProperty(rich_text=True)
    images: Optional[List[str]] = NotionProperty(files=True)


# 取引先一覧モデル
class Partner(NotionModel):
    name: str = NotionProperty(title=True)
    transaction_types: List[TransactionType] = NotionProperty(multi_select=True)
    contact_person: Optional[str] = NotionProperty(rich_text=True)
    phone: Optional[str] = NotionProperty(phone_number=True)
    email: Optional[str] = NotionProperty(email=True)
    address: Optional[str] = NotionProperty(rich_text=True)
    memo: Optional[str] = NotionProperty(rich_text=True)


# 商品一覧モデル
class Product(NotionModel):
    name: str = NotionProperty(title=True)
    supplier_id: Optional[str] = NotionProperty(relation=True)
    purchase_price: Optional[float] = NotionProperty(number=True)
    purchase_date: Optional[datetime] = NotionProperty(date=True)
    selling_price: Optional[float] = NotionProperty(number=True)
    selling_platforms: Optional[List[Platform]] = NotionProperty(multi_select=True)
    stock_status: Optional[StockStatus] = NotionProperty(select=True)
    phase: Optional[Phase] = NotionProperty(select=True)
    sold_date: Optional[datetime] = NotionProperty(date=True)
    rank: Optional[Rank] = NotionProperty(select=True)
    category_id: Optional[str] = NotionProperty(relation=True)
    manufacturer: Optional[str] = NotionProperty(rich_text=True)
    model_number: Optional[str] = NotionProperty(rich_text=True)
    serial_number: Optional[str] = NotionProperty(rich_text=True)
    manufacturing_year: Optional[str] = NotionProperty(rich_text=True)
    dimension_inch: Optional[float] = NotionProperty(number=True)
    images: Optional[List[str]] = NotionProperty(files=True)
    description: Optional[str] = NotionProperty(rich_text=True)
    notes: Optional[str] = NotionProperty(rich_text=True)
    platform_url: Optional[str] = NotionProperty(url=True)
    mercari_url: Optional[str] = NotionProperty(url=True)
    ebay_url: Optional[str] = NotionProperty(url=True)
    paypay_url: Optional[str] = NotionProperty(url=True)


# データベース設定
class NotionDB:
    def __init__(self, token: str):
        self.client = Client(auth=token)
        
    def create_databases(self):
        # カテゴリーデータベースの作成
        category_db = NotionDatabase(
            title="カテゴリー一覧",
            properties=Category.get_properties()
        )
        
        # 製品番号データベースの作成
        product_type_db = NotionDatabase(
            title="製品番号一覧",
            properties=ProductType.get_properties()
        )
        
        # 取引先データベースの作成
        partner_db = NotionDatabase(
            title="取引先一覧",
            properties=Partner.get_properties()
        )
        
        # 商品データベースの作成
        product_db = NotionDatabase(
            title="商品一覧",
            properties=Product.get_properties()
        )
        
        return {
            "categories": category_db,
            "product_types": product_type_db,
            "partners": partner_db,
            "products": product_db
        } 