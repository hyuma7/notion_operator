"""
Notion共有URLからページの全プロパティを取得するスクリプト

【設計方針】
- PropertyValue dataclass でプロパティ1件の型と値を保持
- PageData dataclass でページ全体を保持
- dump() でそのままJSON化できる辞書に変換
- _extract_rollup_item() でrollup配列内の全型に対応
- 未対応型は None を返す（str(item)で生dictを埋め込まない）
"""

import os
import re
import json
import sys
from dataclasses import dataclass, field, asdict
from typing import Any, Optional
from dotenv import load_dotenv
from notion_client import Client

try:
    from brother_ql_proxy.core.config import CONFIG_FILE, LEGACY_CONFIG_FILES
except Exception:
    CONFIG_FILE = "printer_proxy_config.json"
    LEGACY_CONFIG_FILES = ()

load_dotenv()

_NOTION_VERSION = "2022-06-28"


def _iter_config_files() -> tuple[str, ...]:
    candidates = [CONFIG_FILE, *LEGACY_CONFIG_FILES, "printer_proxy_config.json"]
    seen = set()
    result = []
    for path in candidates:
        if not path or path in seen:
            continue
        seen.add(path)
        result.append(path)
    return tuple(result)


def _get_config_value(key: str) -> str:
    for path in _iter_config_files():
        try:
            with open(path, "r", encoding="utf-8") as f:
                value = json.load(f).get(key)
            if value:
                return str(value).strip()
        except Exception:
            continue
    return ""


def _get_api_key() -> str:
    """設定ファイル → 環境変数の優先順位でAPIキーを返す"""
    return _get_config_value("notion_api_key") or os.getenv("NOTION_API_KEY", "").strip()


def _get_database_id() -> str:
    """設定ファイル → 環境変数の優先順位でDatabase IDを返す"""
    return _get_config_value("notion_database_id") or os.getenv("NOTION_DATABASE_ID", "").strip()


# ─────────────────────────────────────────────────────────────────────────────
# スキーマ定義
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PropertyValue:
    """Notionプロパティ1件の抽出結果

    Attributes:
        type:  Notionプロパティの型名（"title", "rollup", "select" など）
        value: 抽出済みの値
                - str          : title / rich_text / select / formula(string) / unique_id
                - int | float  : number / formula(number)
                - bool         : checkbox / formula(boolean)
                - list[str]    : multi_select / people / rollup(array) の文字列リスト
                - list[dict]   : files（{"name": ..., "url": ...} のリスト）
                - dict         : date（{"start": ..., "end": ...}）
                - None         : 値なし
    """
    type: str
    value: Any

    def dump(self) -> dict:
        """JSON化可能な辞書に変換"""
        return {"type": self.type, "value": self.value}


@dataclass
class PageData:
    """Notionページ全体の取得結果

    Attributes:
        page_id:         ページUUID
        url:             Notion内部URL
        created_time:    作成日時（ISO8601）
        last_edited_time: 最終更新日時（ISO8601）
        properties:      プロパティ名 → PropertyValue の辞書
    """
    page_id: str
    url: str
    created_time: str
    last_edited_time: str
    properties: dict[str, PropertyValue] = field(default_factory=dict)

    def dump(self) -> dict:
        """JSON化可能な辞書に変換。UI側から参照される形式を維持する"""
        return {
            "page_id": self.page_id,
            "url": self.url,
            "created_time": self.created_time,
            "last_edited_time": self.last_edited_time,
            "properties": {name: pv.dump() for name, pv in self.properties.items()},
        }


# ─────────────────────────────────────────────────────────────────────────────
# URLユーティリティ
# ─────────────────────────────────────────────────────────────────────────────

def extract_page_id(url: str) -> str:
    """Notion共有URLからページID（UUID形式）を抽出する"""
    match = re.search(r"([a-f0-9]{32})", url)
    if not match:
        raise ValueError(f"URLからページIDを抽出できません: {url}")
    raw = match.group(1)
    return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"


# ─────────────────────────────────────────────────────────────────────────────
# rollup 配列アイテムの個別抽出
# ─────────────────────────────────────────────────────────────────────────────

def _extract_rollup_item(item: dict) -> Optional[Any]:
    """rollup の array 内アイテム1件から値を取り出す

    対応型:
        title        → plain_text を結合した文字列
        rich_text    → plain_text を結合した文字列
        number       → 数値 (int | float | None)
        select       → name 文字列
        multi_select → name のリスト
        formula      → string / number / boolean のいずれか
        date         → {"start": ..., "end": ...}
        people       → name のリスト
        files        → {"name": ..., "url": ...} のリスト
        checkbox     → bool
        url          → 文字列
        未対応型     → None（生dictを文字列化しない）
    """
    itype = item.get("type")

    if itype == "title":
        return "".join(t.get("plain_text", "") for t in item.get("title", [])) or None

    elif itype == "rich_text":
        return "".join(t.get("plain_text", "") for t in item.get("rich_text", [])) or None

    elif itype == "number":
        return item.get("number")  # None のままでOK

    elif itype == "select":
        sel = item.get("select")
        return sel.get("name") if sel else None

    elif itype == "multi_select":
        return [s.get("name") for s in item.get("multi_select", [])] or None

    elif itype == "formula":
        formula = item.get("formula", {})
        ftype = formula.get("type")  # "string" | "number" | "boolean" | "date"
        return formula.get(ftype) if ftype else None

    elif itype == "date":
        date_data = item.get("date")
        if date_data:
            return {"start": date_data.get("start"), "end": date_data.get("end")}
        return None

    elif itype == "people":
        names = [p.get("name", p.get("id")) for p in item.get("people", [])]
        return names or None

    elif itype == "files":
        files = []
        for f in item.get("files", []):
            if f.get("type") == "file":
                files.append({"name": f.get("name"), "url": f["file"].get("url")})
            elif f.get("type") == "external":
                files.append({"name": f.get("name"), "url": f["external"].get("url")})
        return files or None

    elif itype == "checkbox":
        return item.get("checkbox")

    elif itype == "url":
        return item.get("url")

    else:
        # 未対応型は None を返す（以前は str(item) で汚いデータを返していた）
        return None


# ─────────────────────────────────────────────────────────────────────────────
# プロパティ値の抽出（メインロジック）
# ─────────────────────────────────────────────────────────────────────────────

def _extract_value(notion: Client, prop_data: dict, prop_type: str) -> Any:
    """プロパティタイプに応じて値を抽出し、Python ネイティブ型で返す"""
    try:
        if prop_type == "title":
            return "".join(t.get("plain_text", "") for t in prop_data.get("title", []))

        elif prop_type == "rich_text":
            return "".join(t.get("plain_text", "") for t in prop_data.get("rich_text", []))

        elif prop_type == "number":
            return prop_data.get("number")

        elif prop_type == "select":
            sel = prop_data.get("select")
            return sel.get("name") if sel else None

        elif prop_type == "multi_select":
            return [item.get("name") for item in prop_data.get("multi_select", [])]

        elif prop_type == "status":
            status = prop_data.get("status")
            return status.get("name") if status else None

        elif prop_type == "date":
            date_data = prop_data.get("date")
            if date_data:
                return {"start": date_data.get("start"), "end": date_data.get("end")}
            return None

        elif prop_type == "checkbox":
            return prop_data.get("checkbox", False)

        elif prop_type == "url":
            return prop_data.get("url")

        elif prop_type == "email":
            return prop_data.get("email")

        elif prop_type == "phone_number":
            return prop_data.get("phone_number")

        elif prop_type == "people":
            return [p.get("name", p.get("id")) for p in prop_data.get("people", [])]

        elif prop_type == "files":
            files = []
            for f in prop_data.get("files", []):
                if f.get("type") == "file":
                    files.append({"name": f.get("name"), "url": f["file"].get("url")})
                elif f.get("type") == "external":
                    files.append({"name": f.get("name"), "url": f["external"].get("url")})
            return files

        elif prop_type in ("created_time", "last_edited_time"):
            return prop_data.get(prop_type)

        elif prop_type in ("created_by", "last_edited_by"):
            user = prop_data.get(prop_type, {})
            return user.get("name", user.get("id"))

        elif prop_type == "formula":
            formula = prop_data.get("formula", {})
            ftype = formula.get("type")
            return formula.get(ftype) if ftype else None

        elif prop_type == "rollup":
            rollup = prop_data.get("rollup", {})
            rtype = rollup.get("type")

            if rtype == "array":
                # 各アイテムを _extract_rollup_item で変換し、None は除外
                results = []
                for item in rollup.get("array", []):
                    extracted = _extract_rollup_item(item)
                    if extracted is not None:
                        # list が返ってきた場合（multi_select / people / files）は展開
                        if isinstance(extracted, list):
                            results.extend(extracted)
                        else:
                            results.append(extracted)
                return results

            elif rtype == "number":
                return rollup.get("number")

            elif rtype == "date":
                date_data = rollup.get("date")
                if date_data:
                    return {"start": date_data.get("start"), "end": date_data.get("end")}
                return None

            else:
                return None

        elif prop_type == "relation":
            relations = prop_data.get("relation", [])
            titles = []
            for rel in relations:
                rel_id = rel.get("id")
                if rel_id:
                    try:
                        rel_page = notion.pages.retrieve(page_id=rel_id)
                        for rp_name, rp_data in rel_page.get("properties", {}).items():
                            if rp_data.get("type") == "title":
                                title = "".join(
                                    t.get("plain_text", "")
                                    for t in rp_data.get("title", [])
                                )
                                titles.append(title)
                                break
                        else:
                            titles.append(rel_id)
                    except Exception:
                        titles.append(rel_id)
            return titles

        elif prop_type == "unique_id":
            uid = prop_data.get("unique_id", {})
            prefix = uid.get("prefix", "")
            number = uid.get("number", "")
            return f"{prefix}-{number}" if prefix else str(number)

        else:
            return None  # 未対応型は None（表示フィルターで除外される）

    except Exception as e:
        return f"エラー: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# パブリックAPI
# ─────────────────────────────────────────────────────────────────────────────

def fetch_recent_items(database_id: str, limit: int = 10) -> list[dict]:
    """データベースから更新日時の新しい順にN件を取得する

    Returns:
        [{"page_id": str, "title": str, "last_edited_time": str, "url": str}, ...]
    """
    notion = Client(auth=_get_api_key(), notion_version=_NOTION_VERSION)
    response = notion.request(
        path=f"databases/{database_id}/query",
        method="POST",
        body={
            "sorts": [{"timestamp": "last_edited_time", "direction": "descending"}],
            "page_size": limit,
        },
    )

    items = []
    for page in response.get("results", []):
        page_id = page.get("id", "")
        last_edited = page.get("last_edited_time", "")
        url = page.get("url", "")

        title = ""
        for prop_data in page.get("properties", {}).values():
            if prop_data.get("type") == "title":
                title = "".join(t.get("plain_text", "") for t in prop_data.get("title", []))
                break

        items.append({
            "page_id": page_id,
            "title": title or "(無題)",
            "last_edited_time": last_edited,
            "url": url,
        })

    return items


def search_items(database_id: str, query: str, limit: int = 20) -> list[dict]:
    """商品名またはIDでデータベースを検索する

    Args:
        query: 商品名（部分一致）または数値ID
    Returns:
        fetch_recent_items と同じ形式のリスト
    """
    notion = Client(auth=_get_api_key(), notion_version=_NOTION_VERSION)

    # 数値だけなら unique_id（ID プロパティ）でも絞り込む
    filters = []
    filters.append({"property": "商品名", "title": {"contains": query}})
    if query.isdigit():
        filters.append({"property": "ID", "unique_id": {"equals": int(query)}})

    filter_body = {"or": filters} if len(filters) > 1 else filters[0]

    response = notion.request(
        path=f"databases/{database_id}/query",
        method="POST",
        body={
            "filter": filter_body,
            "sorts": [{"timestamp": "last_edited_time", "direction": "descending"}],
            "page_size": limit,
        },
    )

    items = []
    for page in response.get("results", []):
        page_id = page.get("id", "")
        last_edited = page.get("last_edited_time", "")
        url = page.get("url", "")

        title = ""
        for prop_data in page.get("properties", {}).values():
            if prop_data.get("type") == "title":
                title = "".join(t.get("plain_text", "") for t in prop_data.get("title", []))
                break

        items.append({
            "page_id": page_id,
            "title": title or "(無題)",
            "last_edited_time": last_edited,
            "url": url,
        })

    return items


def fetch_all_properties(page_id: str) -> dict:
    """ページの全プロパティを取得して辞書で返す（後方互換インターフェース）

    Returns:
        PageData.dump() と同じ形式の辞書
        {
            "page_id": str,
            "url": str,
            "created_time": str,
            "last_edited_time": str,
            "properties": {
                "<プロパティ名>": {"type": str, "value": Any},
                ...
            }
        }
    """
    notion = Client(auth=_get_api_key(), notion_version=_NOTION_VERSION)
    page = notion.pages.retrieve(page_id=page_id)

    props: dict[str, PropertyValue] = {}
    for prop_name, prop_data in page.get("properties", {}).items():
        prop_type = prop_data.get("type", "unknown")
        value = _extract_value(notion, prop_data, prop_type)
        props[prop_name] = PropertyValue(type=prop_type, value=value)

    data = PageData(
        page_id=page.get("id", ""),
        url=page.get("url", ""),
        created_time=page.get("created_time", ""),
        last_edited_time=page.get("last_edited_time", ""),
        properties=props,
    )
    return data.dump()


# ─────────────────────────────────────────────────────────────────────────────
# CLI エントリポイント
# ─────────────────────────────────────────────────────────────────────────────

def main():
    if not _get_api_key():
        print("エラー: NOTION_API_KEY が設定されていません（設定タブまたは .env）")
        sys.exit(1)

    url = sys.argv[1] if len(sys.argv) > 1 else \
        "https://www.notion.so/30454e6206d880619fa7f9510bb20ede?source=copy_link"

    print(f"URL: {url}")
    page_id = extract_page_id(url)
    print(f"ページID: {page_id}")
    print("-" * 60)

    data = fetch_all_properties(page_id)

    print(f"作成日時: {data['created_time']}")
    print(f"更新日時: {data['last_edited_time']}")
    print(f"Notion URL: {data['url']}")
    print("=" * 60)
    print("【全プロパティ】")
    print("=" * 60)

    for name, info in data["properties"].items():
        print(f"  {name} ({info['type']}): {info['value']}")

    print()
    print("--- JSON出力 ---")
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
