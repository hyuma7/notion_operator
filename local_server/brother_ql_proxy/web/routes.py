"""
Flask Webサーバーのルート定義
"""

from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
from PIL import Image as PILImage, ImageDraw, ImageFont
import qrcode
import io
from functools import wraps

from ..utils import convert_to_brother_format
from ..utils.brother_format import create_simple_test_label
from ..notion import NotionPageParser, LabelPreviewGenerator


def create_flask_app(proxy):
    """Flaskアプリケーションを作成"""
    app = Flask(__name__)
    CORS(app)
    
    @app.after_request
    def hide_server_info(response):
        """外部アクセス時にサーバー情報を隠蔽"""
        client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR', ''))
        is_local = client_ip in ['127.0.0.1', '::1', 'localhost'] or client_ip.startswith('192.168.') or client_ip.startswith('10.') or client_ip.startswith('172.')
        
        if not is_local:
            # 外部アクセス時はサーバー情報を隠蔽
            response.headers.pop('Server', None)
            response.headers['Server'] = 'API Server'
        
        return response
    
    def require_secret_for_external_access(f):
        """外部アクセス時にsecret_keyを要求するデコレーター"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # ローカルアクセスかチェック
            client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR', ''))
            is_local = client_ip in ['127.0.0.1', '::1', 'localhost'] or client_ip.startswith('192.168.') or client_ip.startswith('10.') or client_ip.startswith('172.')
            
            # ローカルアクセスの場合は認証をスキップ
            if is_local:
                return f(*args, **kwargs)
            
            # 外部アクセスの場合、secret_keyが設定されているかチェック
            configured_secret = proxy.config.get('secret_key', '')
            if not configured_secret:
                proxy.log(f"外部アクセス拒否: secret_keyが設定されていません (IP: {client_ip})", "WARNING")
                return jsonify({"error": "Unauthorized"}), 401
            
            # リクエストから'secret'ヘッダーを取得
            provided_secret = request.headers.get('secret')
            
            if provided_secret != configured_secret:
                proxy.log(f"外部アクセス拒否: 無効なsecret_key (IP: {client_ip})", "WARNING")
                return jsonify({"error": "Unauthorized"}), 401
            
            proxy.log(f"外部アクセス許可: 有効なsecret_key (IP: {client_ip})", "INFO")
            return f(*args, **kwargs)
        return decorated_function
    
    @app.route('/')
    def index():
        """Webインターフェース"""
        # 外部アクセス時はWebインターフェースを隠蔽
        client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR', ''))
        is_local = client_ip in ['127.0.0.1', '::1', 'localhost'] or client_ip.startswith('192.168.') or client_ip.startswith('10.') or client_ip.startswith('172.')
        
        if not is_local:
            return jsonify({"error": "Not Found"}), 404
        
        return render_template_string(WEB_INTERFACE_HTML)
    
    @app.route('/', methods=['POST'])
    @require_secret_for_external_access
    def root_post():
        """ルートパスへのPOSTリクエストを処理してプレビューを生成"""
        try:
            proxy.log("ルートパスへのPOSTリクエストを受信。Notionデータを処理します。")
            
            # Notionデータを解析
            webhook_data = request.get_json()
            if not webhook_data:
                return jsonify({"status": "error", "message": "JSONデータが必要です"}), 400
            
            # Notionデータを解析
            parser = NotionPageParser()
            
            parsed_data = parser.parse_webhook_data(webhook_data)
            
            if not parsed_data.get('success'):
                return jsonify({
                    "status": "error", 
                    "message": parsed_data.get('error', '解析に失敗しました')
                }), 400
            
            # 印刷可能フィールドを取得
            printable_fields = parser.get_printable_fields(parsed_data)
            
            # プレビュー生成
            preview_generator = LabelPreviewGenerator()
            label_size = proxy.config.get('label_size', '62')
            include_qr = True
            qr_data = parsed_data.get('page_url', parsed_data.get('title', 'No URL'))
            
            preview_result = preview_generator.generate_preview(
                printable_fields, label_size, include_qr, qr_data
            )
            
            # 最新のプレビューデータを保存（Webインターフェースで表示するため）
            proxy.latest_preview = {
                "preview": preview_result,
                "parsed_data": parsed_data,
                "printable_fields": printable_fields,
                "timestamp": datetime.now().isoformat(),
                "original_webhook_data": webhook_data  # 元のウェブフックデータを保存
            }
            
            return jsonify({
                "status": "success",
                "message": "Notionデータを受信し、プレビューを生成しました",
                "preview": preview_result,
                "parsed_data": parsed_data,
                "printable_fields": printable_fields
            })
            
        except Exception as e:
            proxy.log(f"ルートPOSTエラー: {e}", "ERROR")
            return jsonify({"status": "error", "message": str(e)}), 500
    
    @app.route('/latest-preview', methods=['GET'])
    def get_latest_preview():
        """最新のプレビューデータを取得"""
        if hasattr(proxy, 'latest_preview'):
            return jsonify({
                "status": "success",
                "data": proxy.latest_preview
            })
        else:
            return jsonify({
                "status": "no_data",
                "message": "まだプレビューデータがありません"
            })
    
    @app.route('/status', methods=['GET'])
    def status():
        """ステータス確認"""
        # デバッグログ
        proxy.log(f"=== ステータス確認 ===")
        proxy.log(f"設定ファイル: {proxy.config}")
        proxy.log(f"プリンターIP: {proxy.config.get('printer_ip', 'なし')}")
        proxy.log(f"プリンターポート: {proxy.config.get('printer_port', 'なし')}")
        
        test_result = proxy.test_printer_connection()
        proxy.log(f"プリンター接続テスト結果: {test_result}")
        
        # ngrok URLを安全に文字列として取得
        ngrok_url = None
        if proxy.ngrok_url:
            if hasattr(proxy.ngrok_url, 'public_url'):
                # NgrokTunnelオブジェクトの場合
                ngrok_url = str(proxy.ngrok_url.public_url)
            else:
                # 既に文字列の場合
                ngrok_url = str(proxy.ngrok_url)
        
        # Secret Key設定状態を確認
        secret_key_configured = bool(proxy.config.get('secret_key', ''))

        response_data = {
            "proxy_status": "online",
            "printer_ip": proxy.config.get('printer_ip', 'なし'),
            "printer_port": proxy.config.get('printer_port', 9100),
            "printer_connected": test_result.get('connected', False),
            "ngrok_url": ngrok_url,
            "secret_key_configured": secret_key_configured,
            "timestamp": datetime.now().isoformat(),
            "test_result": test_result  # デバッグ用
        }
        
        proxy.log(f"ステータスレスポンス: {response_data}")
        return jsonify(response_data)
    
    @app.route('/print/raw', methods=['POST'])
    @require_secret_for_external_access
    def print_raw():
        """生データを印刷"""
        try:
            data = request.data
            if not data:
                return jsonify({"status": "error", "message": "データがありません"}), 400
            
            success = proxy.send_raw_data_to_printer(data)
            
            if success:
                proxy.log(f"生データ印刷成功: {len(data)} bytes")
                return jsonify({"status": "success", "message": "印刷しました", "bytes": len(data)})
            else:
                return jsonify({"status": "error", "message": "印刷に失敗しました"}), 500
                
        except Exception as e:
            proxy.log(f"印刷エラー: {e}", "ERROR")
            return jsonify({"status": "error", "message": str(e)}), 500
    
    @app.route('/print/label', methods=['POST'])
    @require_secret_for_external_access
    def print_label():
        """ラベルを作成して印刷"""
        try:
            data = request.get_json() or {}
            
            # シンプルなテキストラベルを作成
            text = data.get('text', 'テストラベル')
            label_size = data.get('label_size', proxy.config['label_size'])
            
            # ラベル画像を作成（テストスクリプトと同じサイズ）
            if label_size in ['62x29', '62']:
                width, height = 696, 271  # テストスクリプトと同じ
            else:
                width, height = 696, 1109
                
            img = PILImage.new('RGB', (width, height), 'white')
            draw = ImageDraw.Draw(img)
            
            # テキストを描画（日本語フォントを使用）
            font = None
            japanese_fonts = [
                "/mnt/c/Windows/Fonts/msgothic.ttc",
                "/mnt/c/Windows/Fonts/meiryo.ttc",
                "C:/Windows/Fonts/msgothic.ttc",
                "C:/Windows/Fonts/meiryo.ttc",
            ]
            
            for font_path in japanese_fonts:
                try:
                    font = ImageFont.truetype(font_path, 24)
                    break
                except:
                    continue
            
            if font is None:
                try:
                    font = ImageFont.load_default()
                except:
                    font = None
                
            draw.text((50, 50), text, fill='black', font=font)
            
            # QRコードを追加（オプション・コンパクト）
            if data.get('qr_data'):
                qr = qrcode.QRCode(version=1, box_size=3, border=1)  # 小さくコンパクト
                qr.add_data(data['qr_data'])
                qr.make(fit=True)
                qr_img = qr.make_image(fill_color="black", back_color="white")
                qr_img = qr_img.resize((100, 100))  # コンパクトサイズ
                img.paste(qr_img, (width - 120, 50))
            
            # Brother QLフォーマットに変換
            raster_data = convert_to_brother_format(img, label_size)
            
            # プリンターに送信
            success = proxy.send_raw_data_to_printer(raster_data)
            
            if success:
                return jsonify({"status": "success", "message": "ラベルを印刷しました"})
            else:
                return jsonify({"status": "error", "message": "印刷に失敗しました"}), 500
                
        except Exception as e:
            proxy.log(f"ラベル印刷エラー: {e}", "ERROR")
            return jsonify({"status": "error", "message": str(e)}), 500
    
    @app.route('/print/test', methods=['POST'])
    def print_test():
        """シンプルなテスト印刷"""
        try:
            # シンプルなテストデータを作成
            test_data = create_simple_test_label("TEST")
            
            # プリンターに送信
            success = proxy.send_raw_data_to_printer(test_data)
            
            if success:
                return jsonify({"status": "success", "message": "テスト印刷を実行しました"})
            else:
                return jsonify({"status": "error", "message": "テスト印刷に失敗しました"}), 500
                
        except Exception as e:
            proxy.log(f"テスト印刷エラー: {e}", "ERROR")
            return jsonify({"status": "error", "message": str(e)}), 500
    
    @app.route('/notion/webhook', methods=['POST'])
    @require_secret_for_external_access
    def notion_webhook():
        """Notionウェブフックハンドラー"""
        try:
            # 生のリクエストデータをログ出力
            raw_data = request.get_data()
            proxy.log(f"=== Notionウェブフック受信 ===")
            proxy.log(f"Content-Type: {request.content_type}")
            proxy.log(f"Headers: {dict(request.headers)}")
            proxy.log(f"Raw data length: {len(raw_data)} bytes")
            proxy.log(f"Raw data (first 500 chars): {raw_data[:500]}")
            
            webhook_data = request.get_json()
            if not webhook_data:
                proxy.log("JSONデータが取得できませんでした", "ERROR")
                return jsonify({"status": "error", "message": "JSONデータが必要です"}), 400
            
            # JSONデータの詳細ログ
            import json
            proxy.log(f"Parsed JSON keys: {list(webhook_data.keys())}")
            proxy.log(f"JSON data: {json.dumps(webhook_data, indent=2, ensure_ascii=False)[:1000]}...")
            
            # Notionデータを解析
            parser = NotionPageParser()
            
            parsed_data = parser.parse_webhook_data(webhook_data)
            
            proxy.log(f"解析結果: {parsed_data.get('event_type', 'unknown')}")
            
            if parsed_data.get('success'):
                # 印刷可能フィールドを取得
                printable_fields = parser.get_printable_fields(parsed_data)
                proxy.log(f"印刷可能フィールド数: {len(printable_fields)}")
                
                for field in printable_fields:
                    proxy.log(f"  - {field['name']} ({field['type']}): {field['value'][:100]}...")
                
                return jsonify({
                    "status": "success",
                    "message": "ウェブフックを処理しました",
                    "parsed_data": parsed_data,
                    "printable_fields": printable_fields
                })
            else:
                proxy.log(f"解析エラー: {parsed_data.get('error', '不明なエラー')}", "ERROR")
                return jsonify({
                    "status": "error", 
                    "message": parsed_data.get('error', '解析に失敗しました'),
                    "raw_data": webhook_data
                }), 400
                
        except Exception as e:
            proxy.log(f"Notionウェブフックエラー: {e}", "ERROR")
            import traceback
            proxy.log(f"スタックトレース: {traceback.format_exc()}", "ERROR")
            return jsonify({"status": "error", "message": str(e)}), 500
    
    @app.route('/notion/preview', methods=['POST'])
    @require_secret_for_external_access
    def notion_preview():
        """Notionデータのプレビュー生成"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({"status": "error", "message": "JSONデータが必要です"}), 400
            
            # データの種類を判定
            if 'printable_fields' in data:
                # 既に解析済みのデータ
                printable_fields = data['printable_fields']
            else:
                # 生のNotionウェブフックデータ
                parser = NotionPageParser()
                # リクエストデータを整形して出力
                parser.print_request_data(data)
                
                parsed_data = parser.parse_webhook_data(data)
                
                if not parsed_data.get('success'):
                    return jsonify({
                        "status": "error", 
                        "message": parsed_data.get('error', '解析に失敗しました')
                    }), 400
                
                printable_fields = parser.get_printable_fields(parsed_data)
            
            # プレビュー生成
            preview_generator = LabelPreviewGenerator()
            
            # 設定を取得
            label_size = data.get('label_size', proxy.config.get('label_size', '62'))
            include_qr = data.get('include_qr', True)
            qr_data = data.get('qr_data')
            font_size = data.get('font_size', 16)
            qr_size = data.get('qr_size', 3)
            
            # QRデータが指定されていない場合はページURLを使用
            if include_qr and not qr_data:
                if 'parsed_data' in locals() and parsed_data.get('page_url'):
                    qr_data = parsed_data['page_url']
                elif 'page_url' in data:
                    qr_data = data['page_url']
                else:
                    qr_data = data.get('title', 'No URL')
            
            preview_result = preview_generator.generate_preview(
                printable_fields, label_size, include_qr, qr_data, font_size, qr_size
            )
            
            if preview_result.get('success'):
                return jsonify({
                    "status": "success",
                    "preview": preview_result,
                    "printable_fields": printable_fields
                })
            else:
                return jsonify({
                    "status": "error", 
                    "message": preview_result.get('error', 'プレビュー生成に失敗しました')
                }), 500
                
        except Exception as e:
            proxy.log(f"プレビュー生成エラー: {e}", "ERROR")
            return jsonify({"status": "error", "message": str(e)}), 500
    
    @app.route('/notion/print', methods=['POST'])
    @require_secret_for_external_access
    def notion_print():
        """Notionデータを印刷"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({"status": "error", "message": "JSONデータが必要です"}), 400
            
            proxy.log(f"=== Notion印刷リクエスト受信 ===")
            proxy.log(f"データキー: {list(data.keys())}")
            proxy.log(f"ラベルサイズ: {data.get('label_size', 'なし')}")
            proxy.log(f"QRデータ: {data.get('qr_data', 'なし')[:50] if data.get('qr_data') else 'なし'}")
            
            # プレビューと同じロジックでデータを準備
            if 'printable_fields' in data:
                printable_fields = data['printable_fields']
            else:
                parser = NotionPageParser()
                # リクエストデータを整形して出力
                parser.print_request_data(data)
                
                parsed_data = parser.parse_webhook_data(data)
                
                if not parsed_data.get('success'):
                    return jsonify({
                        "status": "error", 
                        "message": parsed_data.get('error', '解析に失敗しました')
                    }), 400
                
                printable_fields = parser.get_printable_fields(parsed_data)
            
            # 印刷用画像を生成
            preview_generator = LabelPreviewGenerator()
            
            label_size = data.get('label_size', proxy.config.get('label_size', '62'))
            include_qr = data.get('include_qr', True)
            qr_data = data.get('qr_data')
            font_size = data.get('font_size', 16)
            qr_size = data.get('qr_size', 3)
            
            if include_qr and not qr_data:
                if 'parsed_data' in locals() and parsed_data.get('page_url'):
                    qr_data = parsed_data['page_url']
                elif 'page_url' in data:
                    qr_data = data['page_url']
                else:
                    qr_data = data.get('title', 'No URL')
            
            print_img = preview_generator.create_print_data(
                printable_fields, label_size, include_qr, qr_data, font_size, qr_size
            )
            
            proxy.log(f"印刷画像生成完了: {print_img.size}")
            proxy.log(f"印刷フィールド数: {len(printable_fields)}")
            
            # Brother QLフォーマットに変換
            raster_data = convert_to_brother_format(print_img, label_size)
            proxy.log(f"ラスターデータ生成完了: {len(raster_data)} bytes")
            
            # プリンターに送信
            success = proxy.send_raw_data_to_printer(raster_data)
            
            if success:
                return jsonify({
                    "status": "success", 
                    "message": "Notionデータを印刷しました",
                    "printed_fields": len(printable_fields)
                })
            else:
                return jsonify({"status": "error", "message": "印刷に失敗しました"}), 500
                
        except Exception as e:
            proxy.log(f"Notion印刷エラー: {e}", "ERROR")
            return jsonify({"status": "error", "message": str(e)}), 500
    
    return app


# Webインターフェースのテンプレート
WEB_INTERFACE_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Brother QL プリンタープロキシ</title>
    <meta charset="utf-8">
    <style>
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            margin-bottom: 30px;
        }
        .status {
            padding: 15px;
            margin: 20px 0;
            border-radius: 8px;
            font-weight: 500;
        }
        .online {
            background-color: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        .offline {
            background-color: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        button {
            padding: 12px 24px;
            margin: 8px;
            cursor: pointer;
            border: none;
            border-radius: 6px;
            font-size: 16px;
            font-weight: 500;
            transition: all 0.3s;
        }
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }
        .btn-primary {
            background-color: #007bff;
            color: white;
        }
        .btn-primary:hover {
            background-color: #0056b3;
        }
        .test-form {
            margin: 30px 0;
            padding: 25px;
            background: #f8f9fa;
            border-radius: 8px;
        }
        input[type="text"] {
            width: 100%;
            padding: 12px;
            margin: 10px 0;
            border: 1px solid #ddd;
            border-radius: 6px;
            font-size: 16px;
        }
        .api-section {
            margin-top: 40px;
        }
        .api-endpoint {
            background: #f1f3f4;
            padding: 10px 15px;
            margin: 8px 0;
            border-radius: 6px;
            font-family: monospace;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🖨️ Brother QL プリンタープロキシサーバー</h1>
        <div id="status" class="status">接続状態を確認中...</div>
        
        
        <div class="test-form">
            <h3>🗒️ Notion データプレビュー</h3>
            <div id="webhook-status" style="padding: 15px; background: #f0f8ff; border-radius: 8px; margin: 10px 0;">
                <p style="margin: 0;">Notionからのデータを待機中...</p>
            </div>
            <div id="notion-result" style="margin-top: 20px;"></div>
            <div id="notion-preview" style="margin-top: 20px;"></div>
            <div id="print-controls" style="display: none; margin-top: 20px;">
                <div style="margin-bottom: 20px; padding: 15px; background: #f8f9fa; border-radius: 8px;">
                    <div style="margin-bottom: 15px;">
                        <label for="font-size-slider" style="display: block; margin-bottom: 5px; font-weight: 500;">文字サイズ: <span id="font-size-value">16</span>px</label>
                        <input type="range" id="font-size-slider" min="8" max="36" value="16" style="width: 100%;" oninput="updateFontSize(this.value)">
                    </div>
                    <div style="margin-bottom: 15px;">
                        <label for="qr-size-slider" style="display: block; margin-bottom: 5px; font-weight: 500;">QRコードサイズ: <span id="qr-size-value">3</span></label>
                        <input type="range" id="qr-size-slider" min="1" max="8" value="3" style="width: 100%;" oninput="updateQRSize(this.value)">
                    </div>
                    <div style="margin-bottom: 15px;">
                        <label for="layout-mode" style="display: block; margin-bottom: 5px; font-weight: 500;">レイアウトモード:</label>
                        <select id="layout-mode" style="width: 100%; padding: 5px;" onchange="updateLayoutMode(this.value)">
                            <option value="vertical">縦並び（標準）</option>
                            <option value="horizontal">横並び（2列）</option>
                            <option value="compact">コンパクト（3列）</option>
                        </select>
                    </div>
                    <button class="btn-primary" onclick="updatePreview()" style="background-color: #28a745; margin-bottom: 10px;">プレビュー更新</button>
                </div>
                <button class="btn-primary" onclick="printLatestNotion()">🖨️ このラベルを印刷</button>
                <button class="btn-primary" onclick="clearPreview()" style="background-color: #6c757d;">クリア</button>
            </div>
        </div>
        
        <div id="secret-warning" style="display: none; margin-top: 20px; padding: 15px; background: #f8d7da; border: 1px solid #f5c6cb; border-radius: 8px;">
            <h4 style="margin-top: 0; color: #721c24;">⚠️ セキュリティ警告</h4>
            <p style="margin-bottom: 10px; color: #721c24; font-size: 14px;">
                Secret Keyが設定されていません。外部からのアクセスは拒否されます。
            </p>
            <p style="margin-bottom: 0; color: #721c24; font-size: 12px;">
                設定タブでSecret Keyを設定してください。
            </p>
        </div>

        <div style="margin-top: 20px; text-align: right;">
            <button onclick="simpleTest()" style="font-size: 11px; padding: 4px 12px; background-color: #f8f9fa; color: #6c757d; border: 1px solid #dee2e6; border-radius: 3px; cursor: pointer;">接続テスト</button>
        </div>
    </div>
    
    <script>
        async function checkStatus() {
            try {
                const response = await fetch('/status');
                const data = await response.json();
                const statusDiv = document.getElementById('status');
                if (data.printer_connected) {
                    statusDiv.className = 'status online';
                    statusDiv.innerHTML = `✅ プリンター接続中<br>
                        <small>${data.printer_ip}:${data.printer_port}</small>`;
                } else {
                    statusDiv.className = 'status offline';
                    statusDiv.textContent = '❌ プリンター未接続';
                }

                // Secret Key未設定の警告を表示/非表示
                const secretWarning = document.getElementById('secret-warning');
                if (secretWarning) {
                    secretWarning.style.display = data.secret_key_configured ? 'none' : 'block';
                }
            } catch (e) {
                console.error(e);
            }
        }
        
        
        async function simpleTest() {
            try {
                const response = await fetch('/print/test', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({})
                });
                const data = await response.json();
                alert(data.message || 'シンプルテスト印刷しました');
            } catch (e) {
                alert('エラー: ' + e.message);
            }
        }
        
        let latestNotionData = null;
        let currentFontSize = parseInt(localStorage.getItem('labelFontSize')) || 16;
        let currentQRSize = parseInt(localStorage.getItem('labelQRSize')) || 3;
        let currentLayoutMode = localStorage.getItem('labelLayoutMode') || 'vertical';
        let lastDataHash = null; // データ変更検出用
        
        function updateFontSize(value) {
            currentFontSize = parseInt(value);
            document.getElementById('font-size-value').textContent = value;
            localStorage.setItem('labelFontSize', value);
            console.log('フォントサイズを保存:', value);
        }
        
        function updateQRSize(value) {
            currentQRSize = parseInt(value);
            document.getElementById('qr-size-value').textContent = value;
            localStorage.setItem('labelQRSize', value);
            console.log('QRサイズを保存:', value);
        }
        
        function updateLayoutMode(value) {
            currentLayoutMode = value;
            localStorage.setItem('labelLayoutMode', value);
            console.log('レイアウトモードを保存:', value);
        }
        
        function loadSavedSettings() {
            // 保存された設定を読み込み
            const savedFontSize = parseInt(localStorage.getItem('labelFontSize')) || 16;
            const savedQRSize = parseInt(localStorage.getItem('labelQRSize')) || 3;
            const savedLayoutMode = localStorage.getItem('labelLayoutMode') || 'vertical';
            
            currentFontSize = savedFontSize;
            currentQRSize = savedQRSize;
            currentLayoutMode = savedLayoutMode;
            
            document.getElementById('font-size-slider').value = savedFontSize;
            document.getElementById('font-size-value').textContent = savedFontSize;
            document.getElementById('qr-size-slider').value = savedQRSize;
            document.getElementById('qr-size-value').textContent = savedQRSize;
            document.getElementById('layout-mode').value = savedLayoutMode;
            
            console.log('保存された設定を読み込み:', {fontSize: savedFontSize, qrSize: savedQRSize, layoutMode: savedLayoutMode});
        }
        
        function generateDataHash(data) {
            // データのハッシュ値を生成してコンテンツ変更を検出
            if (!data || !data.printable_fields) return null;
            
            const fieldsString = data.printable_fields.map(field => 
                field.name + ':' + field.value + ':' + field.type
            ).join('|');
            
            const pageUrl = data.parsed_data?.page_url || '';
            const timestamp = data.timestamp || '';
            
            return fieldsString + '|' + pageUrl + '|' + timestamp;
        }
        
        async function updatePreview() {
            if (!latestNotionData) {
                alert('Notionデータがありません。まずNotionからデータを受信してください。');
                return;
            }
            
            try {
                const response = await fetch('/notion/preview', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        printable_fields: latestNotionData.parsed_data?.printable_fields || latestNotionData.printable_fields,
                        parsed_data: latestNotionData.parsed_data,
                        font_size: currentFontSize,
                        qr_size: currentQRSize,
                        layout_mode: currentLayoutMode,
                        label_size: latestNotionData.preview?.dimensions?.label_size || '62',
                        include_qr: true,
                        qr_data: latestNotionData.parsed_data?.parsed_data?.page_url || latestNotionData.parsed_data?.page_url || latestNotionData.parsed_data?.title || 'No URL'
                    })
                });
                
                const data = await response.json();
                if (data.status === 'success' && data.preview) {
                    displayPreview(data.preview);
                } else {
                    alert('プレビューの更新に失敗しました: ' + (data.message || 'エラー'));
                }
            } catch (e) {
                alert('エラー: ' + e.message);
            }
        }
        
        async function generatePreviewWithUserSettings() {
            // ユーザー指定の設定でプレビューを生成
            if (!latestNotionData) return;
            
            try {
                const response = await fetch('/notion/preview', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        printable_fields: latestNotionData.printable_fields,
                        parsed_data: latestNotionData.parsed_data,
                        font_size: currentFontSize,
                        qr_size: currentQRSize,
                        layout_mode: currentLayoutMode,
                        label_size: latestNotionData.preview?.dimensions?.label_size || '62',
                        include_qr: true,
                        qr_data: latestNotionData.parsed_data?.page_url || latestNotionData.parsed_data?.title || 'No URL'
                    })
                });
                
                const data = await response.json();
                if (data.status === 'success' && data.preview) {
                    displayPreview(data.preview);
                }
            } catch (e) {
                console.error('Preview generation error:', e);
            }
        }
        
        async function checkLatestPreview() {
            try {
                const response = await fetch('/latest-preview');
                const data = await response.json();
                
                if (data.status === 'success' && data.data) {
                    // データ変更検出
                    const newDataHash = generateDataHash(data.data);
                    const hasDataChanged = lastDataHash !== newDataHash;
                    
                    if (hasDataChanged) {
                        const webhookStatus = document.getElementById('webhook-status');
                        webhookStatus.style.background = '#d4edda';
                        webhookStatus.innerHTML = '<p style="margin: 0; color: #155724;">✅ Notionデータを受信しました - ' + new Date(data.data.timestamp).toLocaleString() + '</p>';
                        
                        latestNotionData = data.data;
                        lastDataHash = newDataHash;
                        
                        // プレビューを表示
                        if (data.data.printable_fields) {
                            displayNotionResult({
                                status: 'success',
                                parsed_data: data.data.parsed_data,
                                printable_fields: data.data.printable_fields
                            });
                        }
                        
                        // 印刷コントロールを表示
                        document.getElementById('print-controls').style.display = 'block';
                        
                        // ユーザー指定のフォントサイズでプレビューを自動更新
                        await generatePreviewWithUserSettings();
                    }
                }
            } catch (e) {
                console.error('Preview check error:', e);
            }
        }
        
        async function printLatestNotion() {
            if (!latestNotionData) {
                alert('印刷するデータがありません');
                return;
            }
            
            try {
                // ユーザー指定の設定で印刷
                const response = await fetch('/notion/print', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        printable_fields: latestNotionData.printable_fields,
                        parsed_data: latestNotionData.parsed_data,
                        label_size: latestNotionData.preview?.dimensions?.label_size || '62',
                        include_qr: true,
                        qr_data: latestNotionData.parsed_data?.page_url || latestNotionData.parsed_data?.title || 'No URL',
                        font_size: currentFontSize,
                        qr_size: currentQRSize,
                        layout_mode: currentLayoutMode
                    })
                });
                
                const result = await response.json();
                alert(result.message || '印刷を実行しました');
                
            } catch (e) {
                alert('印刷エラー: ' + e.message);
                console.error(e);
            }
        }
        
        function clearPreview() {
            latestNotionData = null;
            document.getElementById('webhook-status').style.background = '#f0f8ff';
            document.getElementById('webhook-status').innerHTML = '<p style="margin: 0;">Notionからのデータを待機中...</p>';
            document.getElementById('notion-result').innerHTML = '';
            document.getElementById('notion-preview').innerHTML = '';
            document.getElementById('print-controls').style.display = 'none';
        }
        
        function displayNotionResult(result) {
            const resultDiv = document.getElementById('notion-result');
            
            let html = '<h4>処理結果</h4>';
            html += '<div style="background: #f8f9fa; padding: 15px; border-radius: 6px; margin: 10px 0;">';
            html += '<strong>ステータス:</strong> ' + (result.status === 'success' ? '✅ 成功' : '❌ エラー') + '<br>';
            
            if (result.message) {
                html += '<strong>メッセージ:</strong> ' + result.message + '<br>';
            }
            
            if (result.parsed_data) {
                html += '<strong>イベントタイプ:</strong> ' + (result.parsed_data.event_type || 'unknown') + '<br>';
                html += '<strong>ページタイトル:</strong> ' + (result.parsed_data.title || 'なし') + '<br>';
            }
            
            if (result.printable_fields && result.printable_fields.length > 0) {
                html += '<br><strong>印刷可能フィールド:</strong><br>';
                html += '<ul>';
                result.printable_fields.forEach(field => {
                    html += '<li><strong>' + field.name + '</strong> (' + field.type + '): ' + field.value + '</li>';
                });
                html += '</ul>';
            }
            
            if (result.error) {
                html += '<div style="color: red;"><strong>エラー:</strong> ' + result.error + '</div>';
            }
            
            html += '</div>';
            resultDiv.innerHTML = html;
        }
        
        function displayPreview(preview) {
            const previewDiv = document.getElementById('notion-preview');
            
            if (preview.preview_image) {
                let html = '<h4>ラベルプレビュー</h4>';
                html += '<div style="background: white; padding: 20px; border: 1px solid #ddd; border-radius: 6px; text-align: center;">';
                html += '<img src="' + preview.preview_image + '" style="max-width: 100%; border: 1px solid #ccc;">';
                html += '<div style="margin-top: 10px; font-size: 12px; color: #666;">';
                html += '寸法: ' + preview.dimensions.width + 'x' + preview.dimensions.height + ' px<br>';
                html += 'フィールド数: ' + preview.fields_count;
                if (preview.has_qr) {
                    html += ' | QRコード: あり';
                }
                html += '</div>';
                html += '</div>';
                previewDiv.innerHTML = html;
            }
        }
        
        loadSavedSettings(); // 保存された設定を読み込み
        checkStatus();
        checkLatestPreview();
        setInterval(checkStatus, 30000); // 30秒間隔に変更
        setInterval(checkLatestPreview, 2000); // 2秒間隔でプレビューをチェック
    </script>
</body>
</html>
'''