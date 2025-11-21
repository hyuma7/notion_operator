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
    st.info("在庫状態が「売却済み」のデータのみを取得します")

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
    """
    try:
        # 指定月の開始日と終了日を計算
        start_date = f"{year}-{month:02d}-01"
        if month == 12:
            end_date = f"{year + 1}-01-01"
        else:
            end_date = f"{year}-{month + 1:02d}-01"

        # Notionデータベースをクエリ
        # 注: 在庫状態プロパティ名は実際のデータベースに合わせて調整してください
        results = notion.databases.query(
            database_id=database_id,
            filter={
                "and": [
                    {
                        "property": "在庫状態",
                        "select": {
                            "equals": "売却済み"
                        }
                    },
                    {
                        "property": "売却日",  # 日付プロパティ名は調整が必要な場合があります
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
            worksheet.column_dimensions[chr(65 + idx)].width = min(max_length + 2, 50)

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
            else:
                st.warning("指定された期間に該当するデータがありません")
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
