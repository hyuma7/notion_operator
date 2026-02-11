"""
Notion共有URLからページの全プロパティを取得するスクリプト
"""

import os
import re
import json
import sys
from dotenv import load_dotenv
from notion_client import Client

# .envから環境変数を読み込み
load_dotenv()

NOTION_API_KEY = os.getenv("NOTION_API_KEY")


def extract_page_id(url: str) -> str:
    """Notion共有URLからページIDを抽出する"""
    # URLからハッシュ部分を取得（32文字の16進数）
    match = re.search(r"([a-f0-9]{32})", url)
    if not match:
        raise ValueError(f"URLからページIDを抽出できません: {url}")

    raw_id = match.group(1)
    # UUID形式に変換: 8-4-4-4-12
    page_id = f"{raw_id[:8]}-{raw_id[8:12]}-{raw_id[12:16]}-{raw_id[16:20]}-{raw_id[20:]}"
    return page_id


def fetch_all_properties(page_id: str) -> dict:
    """ページの全プロパティを取得して解析する"""
    notion = Client(auth=NOTION_API_KEY)

    # ページ情報を取得
    page = notion.pages.retrieve(page_id=page_id)

    properties = page.get("properties", {})
    result = {}

    for prop_name, prop_data in properties.items():
        prop_type = prop_data.get("type", "unknown")
        value = _extract_value(notion, prop_data, prop_type)
        result[prop_name] = {
            "type": prop_type,
            "value": value,
        }

    return {
        "page_id": page.get("id"),
        "url": page.get("url"),
        "created_time": page.get("created_time"),
        "last_edited_time": page.get("last_edited_time"),
        "properties": result,
    }


def _extract_value(notion: Client, prop_data: dict, prop_type: str):
    """プロパティタイプに応じて値を抽出"""
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
                results = []
                for item in rollup.get("array", []):
                    itype = item.get("type")
                    if itype == "title":
                        results.append("".join(t.get("plain_text", "") for t in item.get("title", [])))
                    elif itype == "rich_text":
                        results.append("".join(t.get("plain_text", "") for t in item.get("rich_text", [])))
                    elif itype == "number":
                        val = item.get("number")
                        if val is not None:
                            results.append(val)
                    else:
                        results.append(str(item))
                return results
            elif rtype:
                return rollup.get(rtype)
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
                                title = "".join(t.get("plain_text", "") for t in rp_data.get("title", []))
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
            return f"未対応: {prop_type}"

    except Exception as e:
        return f"エラー: {e}"


def main():
    if not NOTION_API_KEY:
        print("エラー: NOTION_API_KEY が .env に設定されていません")
        sys.exit(1)

    # コマンドライン引数またはデフォルトURL
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = "https://www.notion.so/30454e6206d880619fa7f9510bb20ede?source=copy_link"

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
        value = info["value"]
        ptype = info["type"]
        print(f"  {name} ({ptype}): {value}")

    print()
    print("--- JSON出力 ---")
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
