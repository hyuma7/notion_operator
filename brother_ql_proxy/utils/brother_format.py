"""
Brother QLプリンターフォーマット変換ユーティリティ
"""

import struct
import tempfile
import os
import subprocess
from PIL import Image as PILImage


def create_simple_test_label(text: str = "TEST") -> bytes:
    """シンプルなテストラベルを作成（brother_qlライブラリ使用）"""
    
    # シンプルなテスト画像を作成
    width, height = 696, 271
    image = PILImage.new('RGB', (width, height), 'white')
    
    from PIL import ImageDraw, ImageFont
    draw = ImageDraw.Draw(image)
    
    # 黒い枠を描画
    draw.rectangle([10, 10, width-10, height-10], outline='black', width=3)
    
    # テキストを描画
    try:
        font = ImageFont.load_default()
    except:
        font = None
    
    # テキストを中央に配置
    if font:
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
    else:
        text_width = len(text) * 15
        text_height = 20
    
    x = (width - text_width) // 2
    y = (height - text_height) // 2
    
    draw.text((x, y), text, fill='black', font=font)
    
    # brother_qlライブラリを使用して変換
    return convert_to_brother_format(image, '62x29')


def print_label(image: PILImage.Image, label_size: str, proxy) -> dict:
    """ラベルを印刷する。

    ライブラリ経路（brother_ql を直接利用）を優先し、失敗時は従来の CLI 方式へ
    フォールバックする。

    Args:
        image: 印刷する PIL 画像
        label_size: ラベルサイズ（'62' や '62x29' 形式。幅の数値のみ使用）
        proxy: PrinterProxy インスタンス（config / log / send_raw_data_to_printer を持つ）

    Returns:
        {"success": bool, "used_fallback": bool, "error": str | None}
    """
    # ── ライブラリ経路（優先） ─────────────────────────────────────
    try:
        # import も含めて失敗はフォールバック対象にする
        from brother_ql.raster import BrotherQLRaster
        from brother_ql.conversion import convert

        # CLI と同じ正規化: '62x29' → '62'
        label_size_num = label_size.split('x')[0] if 'x' in label_size else label_size
        printer_model = proxy.config.get('printer_model', 'QL-820NWB')

        proxy.log(
            f"ライブラリ経路で印刷開始: model={printer_model}, label={label_size_num}"
        )

        qlr = BrotherQLRaster(printer_model)
        raster = convert(
            qlr=qlr,
            images=[image],
            label=label_size_num,
            rotate='auto',
            threshold=70.0,
            dither=False,
            compress=False,
            red=False,
            dpi_600=False,
            hq=True,
            cut=True,
        )

        if proxy.send_raw_data_to_printer(raster):
            proxy.log("✅ ライブラリ経路で印刷成功")
            return {"success": True, "used_fallback": False, "error": None}

        # 送信失敗はフォールバックへ
        raise Exception("ライブラリ経路でのプリンター送信に失敗しました")

    except Exception as lib_err:
        proxy.log(
            f"ライブラリ経路が失敗したため CLI 方式にフォールバックします: {lib_err}",
            "WARNING",
        )

    # ── フォールバック経路（従来の CLI 方式） ──────────────────────
    try:
        raster = convert_to_brother_format(image, label_size)
        success = proxy.send_raw_data_to_printer(raster)
        if success:
            return {"success": True, "used_fallback": True, "error": None}
        return {"success": False, "used_fallback": True, "error": "CLI 方式の印刷に失敗しました"}
    except Exception as cli_err:
        return {"success": False, "used_fallback": True, "error": str(cli_err)}


def convert_to_brother_format(image: PILImage.Image, label_size: str) -> bytes:
    """画像をbrother_ql CLIで印刷し、成功したかを返す（バイト数は参考値）"""
    
    # 一時ファイルに画像を保存
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        tmp_path = tmp.name
        image.save(tmp_path, 'PNG')
    
    try:
        # brother_ql CLIコマンドを実行
        success = print_with_cli(tmp_path, label_size)
        
        # 成功した場合は参考値として画像サイズ相当のバイト数を返す
        if success:
            # 画像サイズに基づく参考バイト数（実際のラスターデータサイズの概算）
            return b'CLI_SUCCESS'  # 成功フラグとして使用
        else:
            raise Exception("brother_ql CLI印刷に失敗しました")
    
    finally:
        # 一時ファイルを削除
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def print_with_cli(image_path: str, label_size: str = '62') -> bool:
    """CLIツールを使用して印刷"""
    
    # ログ出力用のプロキシインスタンスを取得
    try:
        from ..core.printer_proxy import PrinterProxy
        proxy = PrinterProxy()
        log_func = proxy.log
        PRINTER_IP = proxy.config.get('printer_ip')
        PRINTER_PORT = proxy.config.get('printer_port', 9100)
        PRINTER_MODEL = proxy.config.get('printer_model', 'QL-820NWB')
    except:
        # フォールバック
        def log_func(msg, level="INFO"):
            print(f"[{level}] {msg}")
        PRINTER_IP = '192.168.11.36'
        PRINTER_PORT = 9100
        PRINTER_MODEL = 'QL-820NWB'
    
    LABEL_SIZE = label_size
    
    log_func(f"CLI印刷開始: {image_path}, サイズ: {LABEL_SIZE}, プリンターIP: {PRINTER_IP}")
    
    # プリンター接続確認
    if not check_printer_connection(PRINTER_IP, PRINTER_PORT, log_func):
        log_func("プリンターとの接続が確認できません", "ERROR")
        return False
    
    try:
        # 正しいbrother_qlコマンド構文
        # LABEL_SIZEが'62x29'形式の場合、幅の数値のみを抽出
        label_size_num = LABEL_SIZE.split('x')[0] if 'x' in LABEL_SIZE else LABEL_SIZE
        cmd = [
            'brother_ql',
            '-b', 'network',
            '-m', PRINTER_MODEL,
            '-p', f'tcp://{PRINTER_IP}:{PRINTER_PORT}',
            'print',
            '-l', label_size_num,
            image_path
        ]
        
        log_func(f"実行コマンド: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        log_func(f"コマンド終了コード: {result.returncode}")
        
        if result.stdout:
            log_func(f"stdout: {result.stdout}")
        if result.stderr:
            log_func(f"stderr: {result.stderr}")
        
        if result.returncode == 0:
            log_func("✅ CLI印刷成功!")
            return True
        else:
            log_func(f"❌ CLI印刷失敗 (終了コード: {result.returncode})", "ERROR")
            # 代替コマンドを試す
            log_func("代替コマンドを試行中...")
            return try_alternative_cli(image_path, label_size, PRINTER_IP, PRINTER_PORT, PRINTER_MODEL, log_func)
            
    except subprocess.TimeoutExpired:
        log_func("❌ タイムアウト: 印刷に時間がかかりすぎています", "ERROR")
        return False
    except FileNotFoundError:
        log_func("❌ brother_qlコマンドが見つかりません", "ERROR")
        log_func("pip install brother_ql でインストールしてください", "ERROR")
        return False
    except Exception as e:
        log_func(f"❌ CLI印刷エラー: {e}", "ERROR")
        return False


def check_printer_connection(printer_ip: str, printer_port: int, log_func) -> bool:
    """プリンターとの接続を確認"""
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)  # 3秒タイムアウト
        result = sock.connect_ex((printer_ip, printer_port))
        sock.close()
        
        if result == 0:
            log_func(f"✅ プリンター({printer_ip}:{printer_port})に接続可能")
            return True
        else:
            log_func(f"❌ プリンター({printer_ip}:{printer_port})に接続できません (エラーコード: {result})", "ERROR")
            return False
    except Exception as e:
        log_func(f"❌ 接続チェックエラー: {e}", "ERROR")
        return False


def try_alternative_cli(image_path: str, label_size: str, printer_ip: str, printer_port: int, printer_model: str, log_func) -> bool:
    """代替のCLIコマンドを試す"""
    alternatives = [
        # パターン1: --printerオプション
        [
            'brother_ql',
            '--backend', 'network',
            '--model', printer_model,
            '--printer', f'tcp://{printer_ip}:{printer_port}',
            'print',
            '--label-size', label_size,
            image_path
        ],
        # パターン2: 環境変数を使用
        [
            'brother_ql',
            'print',
            '-l', label_size,
            image_path
        ]
    ]
    
    for i, cmd in enumerate(alternatives, 1):
        try:
            log_func(f"代替コマンド {i}: {' '.join(cmd)}")
            
            # パターン2の場合は環境変数を設定
            env = os.environ.copy()
            if i == 2:
                env['BROTHER_QL_PRINTER'] = f'tcp://{printer_ip}:{printer_port}'
                env['BROTHER_QL_BACKEND'] = 'network'
                env['BROTHER_QL_MODEL'] = printer_model
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                env=env
            )
            
            log_func(f"代替コマンド {i} 終了コード: {result.returncode}")
            if result.stdout:
                log_func(f"代替コマンド {i} stdout: {result.stdout}")
            if result.stderr:
                log_func(f"代替コマンド {i} stderr: {result.stderr}")
            
            if result.returncode == 0:
                log_func(f"✅ 代替コマンド {i} で印刷成功!")
                return True
            else:
                log_func(f"代替コマンド {i} 失敗", "ERROR")
                
        except Exception as e:
            log_func(f"代替コマンド {i} エラー: {e}", "ERROR")
    
    return False