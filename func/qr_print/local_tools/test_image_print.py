#!/usr/bin/env python3
"""
Brother QLプリンター テスト（CLIツール使用版）
brother_qlのCLIを直接使用してより確実に印刷
"""

import os
import sys
import subprocess
import tempfile
from PIL import Image, ImageDraw, ImageFont
import datetime

# プリンター設定
PRINTER_IP = os.environ.get('PRINTER_IP', '192.168.1.100')
PRINTER_MODEL = os.environ.get('PRINTER_MODEL', 'QL-820NWB')
LABEL_SIZE = os.environ.get('LABEL_SIZE', '62')

def create_test_image():
    """テスト用の画像を作成"""
    # 62mmラベル用のサイズ (300dpi)
    width = 696  # 62mm
    height = 271 # 29mm
    
    # 白背景の画像を作成
    image = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(image)
    
    # 黒い枠を描画
    draw.rectangle([10, 10, width-10, height-10], outline='black', width=3)
    
    # テキストを描画
    try:
        font = ImageFont.load_default()
        large_font = font
    except:
        font = None
        large_font = None
    
    text = "TEST PRINT"
    try:
        if font:
            bbox = draw.textbbox((0, 0), text, font=large_font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
        else:
            text_width = len(text) * 15
            text_height = 20
    except:
        text_width = len(text) * 15
        text_height = 20
    
    x = (width - text_width) // 2
    y = (height - text_height) // 2
    
    draw.text((x, y), text, fill='black', font=large_font)
    
    # 現在時刻を追加
    time_text = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    draw.text((20, height-30), time_text, fill='black', font=font)
    
    # IPアドレスを追加
    draw.text((20, 20), f"IP: {PRINTER_IP}", fill='black', font=font)
    
    return image

def print_with_cli(image_path):
    """CLIツールを使用して印刷"""
    try:
        # 正しいbrother_qlコマンド構文
        cmd = [
            'brother_ql',
            '-b', 'network',
            '-m', PRINTER_MODEL,
            '-p', f'tcp://{PRINTER_IP}:9100',
            'print',
            '-l', LABEL_SIZE,
            image_path
        ]
        
        print(f"実行コマンド: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            print("✅ 印刷成功!")
            if result.stdout:
                print(f"出力: {result.stdout}")
            return True
        else:
            print(f"❌ 印刷失敗 (終了コード: {result.returncode})")
            if result.stderr:
                print(f"エラー: {result.stderr}")
            if result.stdout:
                print(f"出力: {result.stdout}")
            
            # 代替コマンドも試す
            print("代替コマンドを試行中...")
            return try_alternative_cli(image_path)
            
    except subprocess.TimeoutExpired:
        print("❌ タイムアウト: 印刷に時間がかかりすぎています")
        return False
    except FileNotFoundError:
        print("❌ brother_qlコマンドが見つかりません")
        print("pip install brother_ql でインストールしてください")
        return False
    except Exception as e:
        print(f"❌ 印刷エラー: {e}")
        return False

def try_alternative_cli(image_path):
    """代替のCLIコマンドを試す"""
    alternatives = [
        # パターン1: --printerオプション
        [
            'brother_ql',
            '--backend', 'network',
            '--model', PRINTER_MODEL,
            '--printer', f'tcp://{PRINTER_IP}:9100',
            'print',
            '--label-size', LABEL_SIZE,
            image_path
        ],
        # パターン2: 環境変数を使用
        [
            'brother_ql',
            'print',
            '-l', LABEL_SIZE,
            image_path
        ]
    ]
    
    for i, cmd in enumerate(alternatives, 1):
        try:
            print(f"代替コマンド {i}: {' '.join(cmd)}")
            
            # パターン2の場合は環境変数を設定
            env = os.environ.copy()
            if i == 2:
                env['BROTHER_QL_PRINTER'] = f'tcp://{PRINTER_IP}:9100'
                env['BROTHER_QL_BACKEND'] = 'network'
                env['BROTHER_QL_MODEL'] = PRINTER_MODEL
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                env=env
            )
            
            if result.returncode == 0:
                print(f"✅ 代替コマンド {i} で印刷成功!")
                return True
            else:
                print(f"代替コマンド {i} 失敗: {result.stderr}")
                
        except Exception as e:
            print(f"代替コマンド {i} エラー: {e}")
    
    return False

def check_printer_connection():
    """プリンターとの接続を確認"""
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((PRINTER_IP, 9100))
        sock.close()
        
        if result == 0:
            print(f"✅ プリンター({PRINTER_IP}:9100)に接続可能")
            return True
        else:
            print(f"❌ プリンター({PRINTER_IP}:9100)に接続できません")
            return False
    except Exception as e:
        print(f"❌ 接続チェックエラー: {e}")
        return False

def main():
    print("🖨️  Brother QLプリンター テスト（CLIベース）")
    print(f"プリンターIP: {PRINTER_IP}")
    print(f"プリンターモデル: {PRINTER_MODEL}")
    print(f"ラベルサイズ: {LABEL_SIZE}")
    print("-" * 50)
    
    # プリンター接続確認
    if not check_printer_connection():
        print("プリンターの接続を確認してください")
        return False
    
    # 引数で画像パスが指定された場合
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        print(f"指定画像をテスト: {image_path}")
        if not os.path.exists(image_path):
            print(f"❌ ファイルが見つかりません: {image_path}")
            return False
        success = print_with_cli(image_path)
    else:
        # テスト画像を作成して印刷
        print("テスト画像を作成中...")
        test_image = create_test_image()
        
        # 一時ファイルに保存
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
            temp_path = tmp_file.name
            test_image.save(temp_path)
            print(f"テスト画像を保存: {temp_path}")
        
        try:
            success = print_with_cli(temp_path)
        finally:
            # 一時ファイルを削除
            try:
                os.unlink(temp_path)
            except:
                pass
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)