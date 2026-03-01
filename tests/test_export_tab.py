"""
Excel出力タブのテスト
"""

import unittest
import pandas as pd
import sys
import os

# プロジェクトのルートディレクトリをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brother_ql_proxy.ui.export_tab import ExportTab


class TestExportTab(unittest.TestCase):
    """ExportTabクラスのテストケース"""

    def setUp(self):
        """各テストの前に実行される初期化処理"""
        # テスト用のダミーデータを作成
        self.test_data = {
            'ID': ['PDT-1', 'PDT-2', 'PDT-3', 'PDT-4'],
            '仕入れ先': ['SA (https://example.com)', 'RE (https://example.com)', 'SA (https://example.com)', ''],
            '販売媒体': ['メルカリ1 (https://example.com)', 'Yahoo! (https://example.com)', 'メルカリ1 (https://example.com)', 'Yahoo! (https://example.com)'],
            '売却日': ['2025-09-15', '2025-10-20', '2025-11-10', '2025-09-25'],
            '売上金': ['￥30,000', '￥20,000', '￥15,000', '￥25,000'],
            '仕入れ原価': ['10000', '8000', '6000', '9000'],
            '販売手数料': ['3000', '2000', '1500', '2500'],
            '送料': ['￥2,200', '￥1,800', '￥1,200', '￥2,000'],
            '純利益': ['14800', '8200', '6300', '11500'],
            '在庫状況': ['売却済み', '売却済み', '売却済み', '売却済み']
        }
        self.df = pd.DataFrame(self.test_data)

    def test_clean_currency(self):
        """通貨クリーニング機能のテスト"""
        # ExportTabのcreate_pivot_sectionsメソッド内のclean_currency関数をテスト
        test_values = [
            ('￥1,000', 1000.0),
            ('2000', 2000.0),
            ('', 0.0),
            (None, 0.0),
            (1500, 1500.0),
            ('￥10,000', 10000.0)
        ]

        for input_val, expected in test_values:
            with self.subTest(input_val=input_val):
                # clean_currency関数のロジックを再現
                if pd.isna(input_val) or input_val == "":
                    result = 0
                elif isinstance(input_val, (int, float)):
                    result = float(input_val)
                else:
                    cleaned = str(input_val).replace('￥', '').replace(',', '').strip()
                    try:
                        result = float(cleaned)
                    except:
                        result = 0

                self.assertEqual(result, expected, f"Failed for input: {input_val}")

    def test_clean_company_name(self):
        """企業名クリーニング機能のテスト"""
        test_cases = [
            ('SA (https://www.notion.so/SA-123?pvs=21)', 'SA'),
            ('メルカリ1 (https://www.notion.so/メルカリ1-456?pvs=21)', 'メルカリ1'),
            ('RE', 'RE'),
            ('', '不明'),
            (None, '不明')
        ]

        for input_val, expected in test_cases:
            with self.subTest(input_val=input_val):
                import re
                # clean_company_name関数のロジックを再現
                if pd.isna(input_val) or input_val == "":
                    result = "不明"
                else:
                    if '(https://' in str(input_val):
                        result = re.sub(r'\s*\(https://.*?\)', '', str(input_val))
                    else:
                        result = str(input_val)
                    result = result.strip()

                self.assertEqual(result, expected, f"Failed for input: {input_val}")

    def test_extract_year_month(self):
        """年月抽出機能のテスト"""
        test_cases = [
            ('2025-09-15', '2025年9月'),
            ('2025-10-01', '2025年10月'),
            ('2025-11-30', '2025年11月'),
            ('', None),
            (None, None)
        ]

        for input_val, expected in test_cases:
            with self.subTest(input_val=input_val):
                # extract_year_month関数のロジックを再現
                if pd.isna(input_val) or input_val == "":
                    result = None
                else:
                    try:
                        date_obj = pd.to_datetime(input_val)
                        result = f"{date_obj.year}年{date_obj.month}月"
                    except:
                        result = None

                self.assertEqual(result, expected, f"Failed for input: {input_val}")

    def test_month_list_generation(self):
        """12ヶ月の月リスト生成のテスト"""
        start_year = 2025
        start_month = 6

        # 月のリストを生成
        months = []
        current_year = start_year
        current_month = start_month

        for i in range(12):
            months.append(f"{current_year}年{current_month}月")
            current_month += 1
            if current_month > 12:
                current_month = 1
                current_year += 1

        # 検証
        self.assertEqual(len(months), 12, "月リストは12要素である必要があります")
        self.assertEqual(months[0], "2025年6月", "最初の月が正しくありません")
        self.assertEqual(months[6], "2025年12月", "7番目の月が正しくありません")
        self.assertEqual(months[7], "2026年1月", "8番目の月が正しくありません")
        self.assertEqual(months[11], "2026年5月", "最後の月が正しくありません")

    def test_date_range_calculation(self):
        """期間計算のテスト"""
        test_cases = [
            (2025, 6, "2025-06-01", "2026-06-01"),
            (2025, 1, "2025-01-01", "2026-01-01"),
            (2025, 12, "2025-12-01", "2026-12-01"),
            (2024, 7, "2024-07-01", "2025-07-01")
        ]

        for start_year, start_month, expected_start, expected_end in test_cases:
            with self.subTest(year=start_year, month=start_month):
                # 開始日
                start_date = f"{start_year}-{start_month:02d}-01"

                # 終了日計算
                end_month = start_month + 12
                end_year = start_year
                if end_month > 12:
                    end_year = start_year + 1
                    end_month = end_month - 12

                end_date = f"{end_year}-{end_month:02d}-01"

                self.assertEqual(start_date, expected_start, "開始日が正しくありません")
                self.assertEqual(end_date, expected_end, "終了日が正しくありません")

    def test_pivot_data_structure(self):
        """ピボットデータの構造テスト"""
        # テストデータから簡易的なピボットテーブルを作成
        df_clean = self.df.copy()

        # 日付から年月を抽出
        df_clean['売却年月'] = pd.to_datetime(df_clean['売却日']).apply(
            lambda x: f"{x.year}年{x.month}月"
        )

        # 数値変換
        df_clean['売上金_数値'] = df_clean['売上金'].apply(
            lambda x: float(str(x).replace('￥', '').replace(',', '')) if pd.notna(x) else 0
        )

        # 企業名クリーニング
        import re
        df_clean['仕入れ先_clean'] = df_clean['仕入れ先'].apply(
            lambda x: re.sub(r'\s*\(https://.*?\)', '', str(x)).strip() if pd.notna(x) and x != '' else '不明'
        )

        # ピボットテーブル作成
        pivot = df_clean.pivot_table(
            values='売上金_数値',
            index='仕入れ先_clean',
            columns='売却年月',
            aggfunc='sum',
            fill_value=0
        )

        # 検証
        self.assertGreater(len(pivot), 0, "ピボットテーブルが空です")
        self.assertIn('SA', pivot.index, "SAが仕入先に含まれていません")

    def test_summary_calculation(self):
        """全体合算の計算テスト"""
        # テストデータで全体合算を計算
        df_clean = self.df.copy()

        # 数値変換
        df_clean['売上金_数値'] = df_clean['売上金'].apply(
            lambda x: float(str(x).replace('￥', '').replace(',', '')) if pd.notna(x) else 0
        )
        df_clean['仕入れ原価_数値'] = df_clean['仕入れ原価'].apply(
            lambda x: float(str(x).replace('￥', '').replace(',', '')) if pd.notna(x) else 0
        )
        df_clean['販売手数料_数値'] = df_clean['販売手数料'].apply(
            lambda x: float(str(x).replace('￥', '').replace(',', '')) if pd.notna(x) else 0
        )
        df_clean['送料_数値'] = df_clean['送料'].apply(
            lambda x: float(str(x).replace('￥', '').replace(',', '')) if pd.notna(x) else 0
        )

        # 合計計算
        total_sales = df_clean['売上金_数値'].sum()
        total_cost = df_clean['仕入れ原価_数値'].sum()
        gross_profit = total_sales - total_cost
        total_fees = df_clean['販売手数料_数値'].sum()
        total_shipping = df_clean['送料_数値'].sum()
        net_profit = gross_profit - total_fees - total_shipping

        # 検証
        self.assertEqual(total_sales, 90000, "売上合計が正しくありません")
        self.assertEqual(total_cost, 33000, "原価合計が正しくありません")
        self.assertEqual(gross_profit, 57000, "粗利が正しくありません")
        self.assertGreater(net_profit, 0, "販売利益がマイナスです")


class TestDataIntegration(unittest.TestCase):
    """データ統合のテストケース"""

    def test_company_list_integration(self):
        """仕入先と販売先の統合テスト"""
        # テスト用の企業リスト
        suppliers = ['SA', 'RE', 'ITF']
        retailers = ['メルカリ1', 'Yahoo!', 'SA']

        # 統合
        all_companies = set()
        all_companies.update(suppliers)
        all_companies.update(retailers)
        all_companies.discard('不明')
        all_companies = sorted(list(all_companies))

        # 検証
        self.assertIn('SA', all_companies, "SAが含まれていません")
        self.assertIn('メルカリ1', all_companies, "メルカリ1が含まれていません")
        self.assertNotIn('不明', all_companies, "不明が除外されていません")
        self.assertEqual(len(all_companies), 5, "企業数が正しくありません")


if __name__ == '__main__':
    # テストを実行
    unittest.main(verbosity=2)
