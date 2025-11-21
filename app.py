import streamlit as st
import pandas as pd
from datetime import datetime
from notion_client import Client
import os
from dotenv import load_dotenv
from io import BytesIO

# 環境変数を読み込み
load_dotenv()

# Notionクライアントの初期化
notion = Client(auth=os.getenv("NOTION_API_KEY"))
database_id = os.getenv("NOTION_DATABASE_ID")

st.set_page_config(
    page_title="Flat在庫管理システム",
    page_icon="🏢",
    layout="wide"
)

st.title("🏢 Flat在庫管理システム - Excel出力")

# サイドバーに説明を表示
with st.sidebar:
    st.header("📝 使い方")
    st.write("1. 対象年月を選択してください")
    st.write("2. 「データを取得」ボタンをクリック")
    st.write("3. 「Excel出力」ボタンでダウンロード")
    st.write("")
    st.info("在庫状況が「売却済み」のデータのみを取得します")
    st.write("")
    st.success("✅ データベース構造対応済み")
    st.write("- プロパティ名: **在庫状況** (status型)")
    st.write("- 日付フィルタ: **売却日**")

# 日付選択UI
st.header("📅 期間選択")
col1, col2 = st.columns(2)

with col1:
    year = st.selectbox(
        "年を選択",
        options=list(range(2020, 2031)),
        index=list(range(2020, 2031)).index(datetime.now().year)
    )

with col2:
    month = st.selectbox(
        "月を選択",
        options=list(range(1, 13)),
        index=datetime.now().month - 1,
        format_func=lambda x: f"{x}月"
    )


def fetch_notion_data(year: int, month: int):
    """
    Notionデータベースから指定された月の「売却済み」データを取得
    
    データベース情報:
    - データベース名: 商品一覧
    - データベースID: 1d254e6206d881bb9e88d2e7ffb90444
    - 在庫状況プロパティID: qFjR (status型)
    - 売却日プロパティID: \ep:H (date型)
    """
    try:
        # 指定月の開始日と終了日を計算
        start_date = f"{year}-{month:02d}-01"
        if month == 12:
            end_date = f"{year + 1}-01-01"
        else:
            end_date = f"{year}-{month + 1:02d}-01"

        # Notionデータベースをクエリ
        results = notion.databases.query(
            database_id=database_id,
            filter={
                "and": [
                    {
                        "property": "在庫状況",  # 正しいプロパティ名: status型
                        "status": {              # select型ではなくstatus型
                            "equals": "売却済み"
                        }
                    },
                    {
                        "property": "売却日",
                        "date": {
                            "on_or_after": start_date
                        }
                    },
                    {
                        "property": "売却日",
                        "date": {
                            "before": end_date
                        }
                    }
                ]
            }
        )

        return results
    except Exception as e:
        st.error(f"データ取得中にエラーが発生しました: {str(e)}")
        return None


def parse_notion_results(results):
    """
    Notion APIの結果をPandas DataFrameに変換
    
    対応プロパティ型:
    - title: タイトルプロパティ
    - rich_text: リッチテキスト
    - number: 数値
    - select: 単一選択
    - status: ステータス (⭐️ 在庫状況で使用)
    - multi_select: 複数選択
    - date: 日付
    - checkbox: チェックボックス
    - url: URL
    - email: メールアドレス
    - phone_number: 電話番号
    - formula: 数式
    - rollup: ロールアップ
    - relation: リレーション
    - people: ユーザー
    - files: ファイル
    - unique_id: ユニークID
    - created_time: 作成日時
    """
    if not results or "results" not in results:
        return pd.DataFrame()

    data = []
    for page in results["results"]:
        properties = page["properties"]
        row = {}

        # 各プロパティを解析
        for prop_name, prop_value in properties.items():
            prop_type = prop_value["type"]

            if prop_type == "title":
                row[prop_name] = prop_value["title"][0]["plain_text"] if prop_value["title"] else ""
            elif prop_type == "rich_text":
                row[prop_name] = prop_value["rich_text"][0]["plain_text"] if prop_value["rich_text"] else ""
            elif prop_type == "number":
                row[prop_name] = prop_value["number"]
            elif prop_type == "select":
                row[prop_name] = prop_value["select"]["name"] if prop_value["select"] else ""
            elif prop_type == "status":  # ⭐️ status型の処理を追加
                row[prop_name] = prop_value["status"]["name"] if prop_value["status"] else ""
            elif prop_type == "multi_select":
                row[prop_name] = ", ".join([item["name"] for item in prop_value["multi_select"]])
            elif prop_type == "date":
                if prop_value["date"]:
                    row[prop_name] = prop_value["date"]["start"]
                else:
                    row[prop_name] = ""
            elif prop_type == "checkbox":
                row[prop_name] = prop_value["checkbox"]
            elif prop_type == "url":
                row[prop_name] = prop_value["url"] or ""
            elif prop_type == "email":
                row[prop_name] = prop_value["email"] or ""
            elif prop_type == "phone_number":
                row[prop_name] = prop_value["phone_number"] or ""
            elif prop_type == "formula":
                # 数式の結果型に応じて処理
                formula = prop_value.get("formula", {})
                if formula.get("type") == "string":
                    row[prop_name] = formula.get("string", "")
                elif formula.get("type") == "number":
                    row[prop_name] = formula.get("number", 0)
                else:
                    row[prop_name] = str(formula)
            elif prop_type == "rollup":
                # ロールアップの結果を処理
                rollup = prop_value.get("rollup", {})
                if rollup.get("type") == "array":
                    array_data = rollup.get("array", [])
                    if array_data:
                        row[prop_name] = ", ".join([str(item) for item in array_data])
                    else:
                        row[prop_name] = ""
                elif rollup.get("type") == "number":
                    row[prop_name] = rollup.get("number", 0)
                else:
                    row[prop_name] = str(rollup)
            elif prop_type == "relation":
                # リレーションのIDを取得
                relations = prop_value.get("relation", [])
                row[prop_name] = ", ".join([rel["id"] for rel in relations])
            elif prop_type == "people":
                # ユーザー名を取得
                people = prop_value.get("people", [])
                row[prop_name] = ", ".join([person.get("name", "") for person in people])
            elif prop_type == "files":
                # ファイル名を取得
                files = prop_value.get("files", [])
                row[prop_name] = ", ".join([file.get("name", "") for file in files])
            elif prop_type == "unique_id":
                # ユニークIDを取得
                unique_id = prop_value.get("unique_id", {})
                prefix = unique_id.get("prefix", "")
                number = unique_id.get("number", 0)
                row[prop_name] = f"{prefix}{number}" if prefix else str(number)
            elif prop_type == "created_time":
                row[prop_name] = prop_value.get("created_time", "")
            else:
                row[prop_name] = str(prop_value.get(prop_type, ""))

        data.append(row)

    return pd.DataFrame(data)


def convert_df_to_excel(df):
    """
    DataFrameをExcelファイルに変換
    """
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='売却済み物件')

        # ワークシートの取得と列幅の自動調整
        worksheet = writer.sheets['売却済み物件']
        for idx, col in enumerate(df.columns):
            max_length = max(
                df[col].astype(str).apply(len).max(),
                len(str(col))
            )
            # 列のアルファベット取得(A, B, C, ... AA, AB, ...)
            if idx < 26:
                col_letter = chr(65 + idx)
            else:
                col_letter = chr(65 + idx // 26 - 1) + chr(65 + idx % 26)
            worksheet.column_dimensions[col_letter].width = min(max_length + 2, 50)

    output.seek(0)
    return output


# データ取得ボタン
if st.button("📥 データを取得", type="primary"):
    with st.spinner("Notionからデータを取得中..."):
        results = fetch_notion_data(year, month)

        if results:
            df = parse_notion_results(results)

            if not df.empty:
                st.success(f"✅ {len(df)}件のデータを取得しました")
                st.session_state.df = df
                
                # データ取得成功の詳細情報
                with st.expander("📋 取得データの詳細", expanded=False):
                    st.write(f"**対象期間**: {year}年{month}月")
                    st.write(f"**取得件数**: {len(df)}件")
                    st.write(f"**列数**: {len(df.columns)}列")
                    st.write("**取得したプロパティ**:")
                    for col in df.columns:
                        st.write(f"  - {col}")
            else:
                st.warning("指定された期間に該当するデータがありません")
                st.info(f"検索条件: {year}年{month}月に売却された商品")
                st.session_state.df = None
        else:
            st.session_state.df = None

# データ表示とExcel出力
if "df" in st.session_state and st.session_state.df is not None:
    st.header("📊 取得データプレビュー")
    st.dataframe(st.session_state.df, use_container_width=True)

    # Excel出力ボタン
    st.header("💾 Excel出力")
    excel_file = convert_df_to_excel(st.session_state.df)

    st.download_button(
        label="📥 Excelファイルをダウンロード",
        data=excel_file,
        file_name=f"flat_sold_{year}年{month:02d}月.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary"
    )
    
    # データ統計情報
    with st.expander("📈 データ統計", expanded=False):
        if "売上金" in st.session_state.df.columns:
            st.metric("合計売上", f"¥{st.session_state.df['売上金'].sum():,.0f}")
        if "純利益" in st.session_state.df.columns:
            st.metric("合計純利益", f"¥{st.session_state.df['純利益'].sum():,.0f}")
        if "仕入れ金" in st.session_state.df.columns:
            st.metric("合計仕入れ", f"¥{st.session_state.df['仕入れ金'].sum():,.0f}")

# フッター
st.divider()
st.caption("🏢 Flat在庫管理システム v2.0 - Notion連携対応版")
st.caption("📚 データベース設計書: flat_inventory_database_schema.md")