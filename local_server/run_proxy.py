#!/usr/bin/env python3
"""
Brother QL プリンタープロキシ起動スクリプト
"""

import sys
import os

def main():
    try:
        # パッケージのパスを追加
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        
        # 必要なモジュールの確認
        print("インポート確認中...")
        
        try:
            import flet as ft
            print("[OK] Flet インポート成功")
        except ImportError as e:
            print(f"[ERROR] Flet インポートエラー: {e}")
            print("pip install flet でインストールしてください")
            return
        
        try:
            from brother_ql_proxy.main import main as app_main
            print("[OK] アプリケーション インポート成功")
        except ImportError as e:
            print(f"[ERROR] アプリケーション インポートエラー: {e}")
            return
        
        print("アプリケーション起動中...")
        ft.app(target=app_main)
        
    except Exception as e:
        print(f"エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()