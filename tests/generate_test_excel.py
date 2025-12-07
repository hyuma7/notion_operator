"""
テストデータからExcelファイルを生成するスクリプト
"""

import sys
import os
import pandas as pd
from datetime import datetime
import re
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment


def load_test_data():
    """テストCSVデータを読み込む"""
    csv_path = os.path.join(os.path.dirname(__file__), 'data', 'sample_notion_data.csv')
    df = pd.read_csv(csv_path)
    return df


def export_to_excel(sections, output_path):
    """ピボットセクションをExcelファイルに出力"""
    wb = Workbook()
    ws = wb.active
    ws.title = "財務集計"

    current_row = 1

    # 各セクションを順番に書き込み
    for section_name, pivot_df in sections.items():
        # セクションタイトル
        ws.cell(row=current_row, column=1, value=section_name)
        ws.cell(row=current_row, column=1).font = Font(bold=True, size=14)
        current_row += 1

        # ヘッダー行（月の列）
        ws.cell(row=current_row, column=1, value="")  # 左上は空欄
        for col_idx, month in enumerate(pivot_df.columns, start=2):
            ws.cell(row=current_row, column=col_idx, value=month)
            ws.cell(row=current_row, column=col_idx).font = Font(bold=True)
            ws.cell(row=current_row, column=col_idx).alignment = Alignment(horizontal='center')

        # 「計」列
        ws.cell(row=current_row, column=len(pivot_df.columns) + 2, value="計")
        ws.cell(row=current_row, column=len(pivot_df.columns) + 2).font = Font(bold=True)
        ws.cell(row=current_row, column=len(pivot_df.columns) + 2).alignment = Alignment(horizontal='center')
        current_row += 1

        # データ行
        for company in pivot_df.index:
            ws.cell(row=current_row, column=1, value=company)
            row_total = 0
            for col_idx, month in enumerate(pivot_df.columns, start=2):
                value = pivot_df.loc[company, month]
                ws.cell(row=current_row, column=col_idx, value=value)
                ws.cell(row=current_row, column=col_idx).number_format = '#,##0'
                row_total += value

            # 計列
            ws.cell(row=current_row, column=len(pivot_df.columns) + 2, value=row_total)
            ws.cell(row=current_row, column=len(pivot_df.columns) + 2).number_format = '#,##0'
            current_row += 1

        # 合計行
        ws.cell(row=current_row, column=1, value="合計")
        ws.cell(row=current_row, column=1).font = Font(bold=True)
        for col_idx, month in enumerate(pivot_df.columns, start=2):
            col_total = pivot_df[month].sum()
            ws.cell(row=current_row, column=col_idx, value=col_total)
            ws.cell(row=current_row, column=col_idx).number_format = '#,##0'
            ws.cell(row=current_row, column=col_idx).font = Font(bold=True)

        # 合計の計列
        grand_total = pivot_df.values.sum()
        ws.cell(row=current_row, column=len(pivot_df.columns) + 2, value=grand_total)
        ws.cell(row=current_row, column=len(pivot_df.columns) + 2).number_format = '#,##0'
        ws.cell(row=current_row, column=len(pivot_df.columns) + 2).font = Font(bold=True)
        current_row += 2  # セクション間に空行

    # 列幅調整
    ws.column_dimensions['A'].width = 20
    num_cols = len(sections[list(sections.keys())[0]].columns) + 2
    for col_idx in range(2, num_cols + 1):
        if col_idx <= 26:
            col_letter = chr(64 + col_idx)
        else:
            first_letter = chr(64 + (col_idx - 1) // 26)
            second_letter = chr(65 + (col_idx - 1) % 26)
            col_letter = first_letter + second_letter
        ws.column_dimensions[col_letter].width = 12

    # ファイルを保存
    wb.save(output_path)


def create_test_excel():
    """テストデータからExcelファイルを生成"""
    print("テストデータを読み込んでいます...")
    df = load_test_data()

    print(f"データ件数: {len(df)}件")

    # テストデータをDataFrameに変換
    print("データをパースしています...")

    # データクリーニング関数
    def clean_currency(value):
        if pd.isna(value) or value == "":
            return 0
        if isinstance(value, (int, float)):
            return float(value)
        value = str(value).replace('￥', '').replace(',', '').strip()
        try:
            return float(value)
        except:
            return 0

    def clean_company_name(value):
        if pd.isna(value) or value == "":
            return "不明"
        if isinstance(value, str) and '(https://' in value:
            value = re.sub(r'\s*\(https://.*?\)', '', value)
        return value.strip()

    # データ変換
    df_clean = df.copy()
    df_clean['仕入れ先'] = df_clean['仕入れ先'].apply(clean_company_name)
    df_clean['販売媒体'] = df_clean['販売媒体'].apply(clean_company_name)
    df_clean['売上金'] = df_clean['売上金'].apply(clean_currency)
    df_clean['仕入れ原価'] = df_clean['仕入れ原価'].apply(clean_currency)
    df_clean['販売手数料'] = df_clean['販売手数料'].apply(clean_currency)
    df_clean['送料'] = df_clean['送料'].apply(clean_currency)
    df_clean['純利益'] = df_clean['純利益'].apply(clean_currency)

    # 売却年月を抽出
    df_clean['売却年月'] = pd.to_datetime(df_clean['売却日']).apply(
        lambda x: f"{x.year}年{x.month}月" if pd.notna(x) else None
    )

    print("ピボットテーブルを作成しています...")

    # 開始年月（2025年6月）
    start_year = 2025
    start_month = 6

    # 12ヶ月分の月リストを生成
    months = []
    current_year = start_year
    current_month = start_month

    for i in range(12):
        months.append(f"{current_year}年{current_month}月")
        current_month += 1
        if current_month > 12:
            current_month = 1
            current_year += 1

    # ピボットテーブルを作成（5つ）
    pivot_list = []

    # 1. 企業別売上（業販）- 仕入先 × 売上金
    pivot1 = df_clean.pivot_table(
        values='売上金',
        index='仕入れ先',
        columns='売却年月',
        aggfunc='sum',
        fill_value=0
    )

    # 2. 企業別販売利益（業販）- 仕入先 × 純利益
    pivot2 = df_clean.pivot_table(
        values='純利益',
        index='仕入れ先',
        columns='売却年月',
        aggfunc='sum',
        fill_value=0
    )

    # 3. 企業別売上（小売）- 販売媒体 × 売上金
    pivot3 = df_clean.pivot_table(
        values='売上金',
        index='販売媒体',
        columns='売却年月',
        aggfunc='sum',
        fill_value=0
    )

    # 4. 企業別販売利益（小売）- 販売媒体 × 純利益
    pivot4 = df_clean.pivot_table(
        values='純利益',
        index='販売媒体',
        columns='売却年月',
        aggfunc='sum',
        fill_value=0
    )

    # 5. 企業別仕入高 - 仕入先 × 仕入れ原価
    pivot5 = df_clean.pivot_table(
        values='仕入れ原価',
        index='仕入れ先',
        columns='売却年月',
        aggfunc='sum',
        fill_value=0
    )

    pivot_list = [pivot1, pivot2, pivot3, pivot4, pivot5]

    # 存在しない月も0で表示
    for i, pivot in enumerate(pivot_list):
        for month in months:
            if month not in pivot.columns:
                pivot[month] = 0
        pivot_list[i] = pivot[months]

    # 全体合算の作成
    summary_data = {
        '指標': ['売上', '原価', '粗利', '販売手数料', '送料', '販売利益']
    }

    for month in months:
        month_data = df_clean[df_clean['売却年月'] == month]
        if len(month_data) > 0:
            売上 = month_data['売上金'].sum()
            原価 = month_data['仕入れ原価'].sum()
            粗利 = 売上 - 原価
            手数料 = month_data['販売手数料'].sum()
            送料 = month_data['送料'].sum()
            販売利益 = 粗利 - 手数料 - 送料
            summary_data[month] = [売上, 原価, 粗利, 手数料, 送料, 販売利益]
        else:
            summary_data[month] = [0, 0, 0, 0, 0, 0]

    # 計列を追加
    summary_data['計'] = [
        df_clean['売上金'].sum(),
        df_clean['仕入れ原価'].sum(),
        df_clean['売上金'].sum() - df_clean['仕入れ原価'].sum(),
        df_clean['販売手数料'].sum(),
        df_clean['送料'].sum(),
        df_clean['純利益'].sum()
    ]

    summary_df = pd.DataFrame(summary_data)
    summary_df.set_index('指標', inplace=True)

    # 仕入先・売上先別の統合リスト作成
    all_companies = set()
    all_companies.update(pivot_list[0].index)
    all_companies.update(pivot_list[2].index)
    all_companies.discard('不明')
    all_companies = sorted(list(all_companies))

    combined_sales_data = {}
    for month in months + ['計']:
        combined_sales_data[month] = []

    for company in all_companies:
        for month in months + ['計']:
            # 仕入先として売上があるか
            supplier_sales = 0
            if company in pivot_list[0].index and month in pivot_list[0].columns:
                supplier_sales = pivot_list[0].loc[company, month]

            # 販売媒体として売上があるか
            retailer_sales = 0
            if company in pivot_list[2].index and month in pivot_list[2].columns:
                retailer_sales = pivot_list[2].loc[company, month]

            combined_sales_data[month].append(supplier_sales + retailer_sales)

    combined_sales_df = pd.DataFrame(combined_sales_data, index=all_companies)

    # Excelに出力
    print("Excelファイルを作成しています...")

    sections = {
        '全体合算': summary_df,
        '仕入先・売上先別': combined_sales_df,
        '企業別仕入高': pivot_list[4]
    }

    # ファイル名を生成
    end_month = start_month + 11
    end_year = start_year
    if end_month > 12:
        end_year = start_year + 1
        end_month = end_month - 12
    filename = f"財務集計_{start_year}年{start_month}月-{end_year}年{end_month}月_テスト.xlsx"

    output_path = os.path.join(os.path.dirname(__file__), 'data', filename)

    # Excelファイルを出力
    export_to_excel(sections, output_path)

    print(f"[OK] Excelファイルを作成しました: {output_path}")
    print(f"\n統計情報:")
    print(f"  総売上: {df_clean['売上金'].sum():,.0f}円")
    print(f"  総原価: {df_clean['仕入れ原価'].sum():,.0f}円")
    print(f"  総利益: {df_clean['純利益'].sum():,.0f}円")
    print(f"  企業数: {len(all_companies)}社")
    print(f"  期間: {start_year}年{start_month}月-{end_year}年{end_month}月")


if __name__ == '__main__':
    create_test_excel()
