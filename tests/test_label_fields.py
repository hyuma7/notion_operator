"""
QRラベルフィールド取得テスト

label_tab.py の _fmt / _get_value / _build_printable_fields を検証する。

対象フィールド（修正点その2）:
  - メーカー    : rollup > array > formula(string)
  - 型番名      : rollup > array > title
  - 仕入先      : rollup > array > formula(string)
  - 仕入れ日   : date
  - 製番        : rich_text
  - 販売担当者  : rollup > array > formula(string)

統合テスト:
  pytest -v -m integration tests/test_label_fields.py
  ※ Notion API キーが設定されている必要がある
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brother_ql_proxy.ui.label_tab import LABEL_PAIR_FIELDS, LABEL_SINGLE_FIELDS


# ─────────────────────────────────────────────
# label_tab のヘルパーメソッドだけを切り出した軽量クラス
# ─────────────────────────────────────────────

class LabelHelper:
    """LabelTab の Flet 非依存メソッドだけを抜き出したテスト用クラス"""

    def _fmt(self, value, prop_type: str = "") -> str:
        if value is None:
            return ""
        if prop_type == "date" or (isinstance(value, dict) and "start" in value):
            return value.get("start", "") or ""
        if isinstance(value, list):
            parts = []
            for v in value:
                if v is None:
                    continue
                if isinstance(v, dict) and "start" in v:
                    parts.append(v.get("start", "") or "")
                elif isinstance(v, (list, dict)):
                    s = self._fmt(v)
                    if s:
                        parts.append(s)
                else:
                    parts.append(str(v))
            return ", ".join(parts)
        if isinstance(value, dict):
            return ", ".join(str(v) for v in value.values() if v is not None)
        return str(value)

    def _get_value(self, props: dict, name: str) -> str:
        info = props.get(name)
        if not info:
            return ""
        return self._fmt(info.get("value"), info.get("type", ""))

    def _build_printable_fields(self, props: dict) -> list:
        fields = []
        for (nf_l, nf_r), (dl, dr) in LABEL_PAIR_FIELDS:
            v_l = self._get_value(props, nf_l)
            v_r = self._get_value(props, nf_r)
            if v_l or v_r:
                combined = f"{v_l}  :  {v_r}" if (v_l and v_r) else (v_l or v_r)
                fields.append({"name": f"{dl} / {dr}", "value": combined, "type": "combined"})
        for nf, display in LABEL_SINGLE_FIELDS:
            v = self._get_value(props, nf)
            if v:
                fields.append({"name": display, "value": v, "type": "people"})
        return fields


@pytest.fixture
def helper():
    return LabelHelper()


# ─────────────────────────────────────────────
# モックデータ生成ヘルパー
# （fetch_all_properties が返す形式: {"type": ..., "value": ...}）
# ─────────────────────────────────────────────

def rollup_formula_str(value: str) -> dict:
    """メーカー・仕入先・販売担当者のような rollup>array>formula(string)"""
    return {"type": "rollup", "value": [value] if value else []}


def rollup_title(value: str) -> dict:
    """型番名のような rollup>array>title → fetch_page が str に変換してリスト化"""
    return {"type": "rollup", "value": [value] if value else []}


def date_val(start: str) -> dict:
    return {"type": "date", "value": {"start": start, "end": None}}


def people_val(names: list) -> dict:
    return {"type": "people", "value": names}


def rich_text_val(value: str) -> dict:
    return {"type": "rich_text", "value": value}


# ─────────────────────────────────────────────
# 1. _fmt 単体テスト
# ─────────────────────────────────────────────

class TestFmt:
    def test_rollup_文字列リスト(self, helper):
        assert helper._fmt(["SHARP"], "rollup") == "SHARP"

    def test_rollup_複数値(self, helper):
        assert helper._fmt(["SHARP", "LC-40AX3"], "rollup") == "SHARP, LC-40AX3"

    def test_rollup_空リスト(self, helper):
        assert helper._fmt([], "rollup") == ""

    def test_rollup_Noneを含むリスト(self, helper):
        assert helper._fmt([None, "SHARP", None], "rollup") == "SHARP"

    def test_date_dictから日付のみ取得(self, helper):
        assert helper._fmt({"start": "2024-03-15", "end": None}, "date") == "2024-03-15"

    def test_date_startがNone(self, helper):
        assert helper._fmt({"start": None, "end": None}, "date") == ""

    def test_None値(self, helper):
        assert helper._fmt(None) == ""

    def test_文字列そのまま(self, helper):
        assert helper._fmt("テスト", "rich_text") == "テスト"

    def test_数値(self, helper):
        assert helper._fmt(12345, "number") == "12345"

    def test_リスト内にdictのdate(self, helper):
        """rollup配列内に date dict が含まれる場合 start を取り出す"""
        v = [{"start": "2024-01-20", "end": None}]
        assert helper._fmt(v, "rollup") == "2024-01-20"


# ─────────────────────────────────────────────
# 2. _get_value 単体テスト
# ─────────────────────────────────────────────

class TestGetValue:
    def test_型番名_rollupから取得(self, helper):
        props = {"型番名": rollup_title("UN55TU8000")}
        assert helper._get_value(props, "型番名") == "UN55TU8000"

    def test_メーカー_rollupから取得(self, helper):
        props = {"メーカー": rollup_formula_str("SHARP")}
        assert helper._get_value(props, "メーカー") == "SHARP"

    def test_仕入先_rollupから取得(self, helper):
        props = {"仕入先": rollup_formula_str("RE")}
        assert helper._get_value(props, "仕入先") == "RE"

    def test_仕入れ日_dateから取得(self, helper):
        props = {"仕入れ日": date_val("2024-03-01")}
        assert helper._get_value(props, "仕入れ日") == "2024-03-01"

    def test_販売担当者_rollupから取得(self, helper):
        props = {"販売担当者": rollup_formula_str("齊藤光")}
        assert helper._get_value(props, "販売担当者") == "齊藤光"

    def test_製番_rich_textから取得(self, helper):
        props = {"製番": rich_text_val("SN-12345")}
        assert helper._get_value(props, "製番") == "SN-12345"

    def test_存在しないフィールドは空文字(self, helper):
        assert helper._get_value({}, "型番名") == ""

    def test_valueがNoneの場合は空文字(self, helper):
        props = {"型番名": {"type": "rollup", "value": None}}
        assert helper._get_value(props, "型番名") == ""


# ─────────────────────────────────────────────
# 3. _build_printable_fields テスト
# ─────────────────────────────────────────────

class TestBuildPrintableFields:
    def _full_props(self):
        return {
            "メーカー":    rollup_formula_str("SHARP"),
            "型番名 ":     rollup_title("4T-C50EJ1"),   # Notion側にスペースあり
            "仕入れ先名":  rollup_formula_str("RE"),
            "仕入れ日":   date_val("2024-03-15"),
            "ID":         {"type": "unique_id", "value": "PDT-42"},
            "製番":       rich_text_val("SN-12345"),
            "販売担当者":  rollup_formula_str("齊藤光"),
            "年式":       rich_text_val("2020"),
        }

    def test_全フィールドが揃う場合(self, helper):
        fields = helper._build_printable_fields(self._full_props())
        assert len(fields) == 4

        assert fields[0]["name"] == "メーカー / 型番"
        assert fields[0]["value"] == "SHARP  :  4T-C50EJ1"

        assert fields[1]["name"] == "仕入先 / 仕入れ日"
        assert fields[1]["value"] == "RE  :  2024-03-15"

        assert fields[2]["name"] == "ID / 製番"
        assert fields[2]["value"] == "PDT-42  :  SN-12345"

        assert fields[3]["name"] == "販売担当者 / 年式"
        assert fields[3]["value"] == "齊藤光  :  2020"

    def test_型番名が空でもメーカーだけ表示(self, helper):
        props = self._full_props()
        props["型番名 "] = {"type": "rollup", "value": []}
        fields = helper._build_printable_fields(props)
        メーカー行 = next(f for f in fields if "メーカー" in f["name"])
        assert メーカー行["value"] == "SHARP"

    def test_販売担当者が空でも年式だけ表示(self, helper):
        props = self._full_props()
        props["販売担当者"] = {"type": "rollup", "value": []}  # noqa: E501
        fields = helper._build_printable_fields(props)
        販売行 = next(f for f in fields if "販売担当者" in f["name"])
        assert 販売行["value"] == "2020"

    def test_販売担当者と年式が両方空の場合は行なし(self, helper):
        props = self._full_props()
        props["販売担当者"] = {"type": "rollup", "value": []}  # noqa: E501
        props["年式"] = {"type": "rich_text", "value": ""}
        fields = helper._build_printable_fields(props)
        names = [f["name"] for f in fields]
        assert "販売担当者 / 年式" not in names

    def test_全フィールド空の場合は空リスト(self, helper):
        props = {
            "メーカー":   {"type": "rollup", "value": []},
            "型番名 ":    {"type": "rollup", "value": []},
            "仕入れ先名": {"type": "rollup", "value": []},
            "仕入れ日":  {"type": "date", "value": None},
            "製番":      {"type": "rich_text", "value": ""},
            "販売担当者": {"type": "rollup", "value": []},
        }
        fields = helper._build_printable_fields(props)
        assert fields == []


# ─────────────────────────────────────────────
# 4. 統合テスト: 実際の Notion ページから取得
# ─────────────────────────────────────────────

@pytest.mark.integration
class TestLabelFieldsIntegration:
    """
    実際の Notion API を呼んで 4K VIERA ページのフィールドを検証する。
    実行: pytest -v -m integration tests/test_label_fields.py
    """
    PAGE_URL = "https://www.notion.so/4K-VIERA-36054e6206d881ffa92bf7af5123c15f"
    EXPECTED_FIELDS = ["メーカー", "型番名 ", "仕入れ先名", "仕入れ日", "ID", "製番", "販売担当者", "年式"]

    @pytest.fixture(autouse=True)
    def fetch_page(self):
        from notion.fetch_page import fetch_all_properties, extract_page_id
        page_id = extract_page_id(self.PAGE_URL)
        self.data = fetch_all_properties(page_id)
        self.props = self.data["properties"]
        self.helper = LabelHelper()

    def test_ページ取得成功(self):
        assert self.data.get("page_id"), "page_id が取得できていない"
        assert self.props, "properties が空"

    def test_型番名フィールドが存在する(self):
        assert "型番名 " in self.props, \
            f"型番名(スペースあり) が見つからない。利用可能なフィールド: {list(self.props.keys())}"

    def test_型番名が非空(self):
        v = self.helper._get_value(self.props, "型番名 ")
        assert v, f"型番名  の値が空。raw={self.props.get('型番名 ')}"

    def test_メーカーが非空(self):
        v = self.helper._get_value(self.props, "メーカー")
        assert v, f"メーカー の値が空。raw={self.props.get('メーカー')}"

    def test_仕入れ先名フィールドが存在する(self):
        assert "仕入れ先名" in self.props, \
            f"仕入れ先名 が見つからない。利用可能なフィールド: {list(self.props.keys())}"

    def test_販売担当者フィールドが存在する(self):
        assert "販売担当者" in self.props, \
            f"販売担当者 が見つからない。利用可能なフィールド: {list(self.props.keys())}"

    def test_製番フィールドが存在する(self):
        assert "製番" in self.props, \
            f"製番 が見つからない。利用可能なフィールド: {list(self.props.keys())}"

    def test_販売担当者がrollupで取得できる(self):
        info = self.props.get("販売担当者")
        assert info is not None
        assert info.get("type") == "rollup", \
            f"販売担当者 は rollup のはずだが type={info.get('type')}"
        v = self.helper._get_value(self.props, "販売担当者")
        print(f"\n[販売担当者] = '{v}'")

    def test_仕入れ日が日付形式(self):
        v = self.helper._get_value(self.props, "仕入れ日")
        if v:
            import re
            assert re.match(r"\d{4}-\d{2}-\d{2}", v), f"日付形式でない: {v}"
        print(f"\n[仕入れ日] = '{v}'")

    def test_build_printable_fieldsで全行生成(self):
        fields = self.helper._build_printable_fields(self.props)
        print("\n[printable_fields]")
        for f in fields:
            print(f"  {f['name']}: {f['value']}")
        assert len(fields) >= 1, "フィールドが1行も生成されなかった"

    def test_全フィールドのraw値をダンプ(self):
        """デバッグ用: 全フィールドの取得結果を出力する（常にパス）"""
        print(f"\n{'='*60}")
        for name in self.EXPECTED_FIELDS:
            info = self.props.get(name)
            if info:
                v = self.helper._get_value(self.props, name)
                print(f"  {name:10s} (type={info['type']:10s}) => '{v}'")
            else:
                print(f"  {name:10s} => [フィールドなし]")
        print('='*60)
        assert True


if __name__ == "__main__":
    import subprocess
    result = subprocess.run(
        ["python", "-m", "pytest", __file__, "-v", "-m", "integration", "--tb=short", "-s"],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )
    sys.exit(result.returncode)
