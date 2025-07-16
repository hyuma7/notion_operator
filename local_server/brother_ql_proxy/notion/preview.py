"""
ラベルプレビュー生成モジュール
"""

import io
import base64
from typing import Dict, Any, List, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont
import qrcode


class LabelPreviewGenerator:
    """ラベルプレビューを生成するクラス"""
    
    def __init__(self):
        self.default_font_size = 16
        self.title_font_size = 20
        self.small_font_size = 12
    
    def generate_preview(self, printable_fields: List[Dict[str, Any]], 
                        label_size: str = "62", 
                        include_qr: bool = True,
                        qr_data: Optional[str] = None) -> Dict[str, Any]:
        """印刷プレビューを生成"""
        try:
            # ラベルサイズの設定（テストスクリプトと同じサイズ）
            if label_size in ['62x29', '62']:
                width, height = 696, 271  # テストスクリプトと同じ
                qr_size = 100  # QRコードは小さく
            elif label_size == '62x100':
                width, height = 696, 1109
                qr_size = 150
            else:
                width, height = 696, 271
                qr_size = 100
            
            # 背景画像を作成
            img = Image.new('RGB', (width, height), 'white')
            draw = ImageDraw.Draw(img)
            
            # フォントの読み込み（日本語対応）
            font_loaded = False
            
            # 日本語フォントのパスリスト
            japanese_fonts = [
                # WSL からアクセス可能な Windows フォント
                "/mnt/c/Windows/Fonts/msgothic.ttc",  # MS ゴシック
                "/mnt/c/Windows/Fonts/meiryo.ttc",    # メイリオ
                "/mnt/c/Windows/Fonts/YuGothic.ttc",  # 游ゴシック
                "/mnt/c/Windows/Fonts/msmincho.ttc",  # MS 明朝
                # Windows
                "C:/Windows/Fonts/msgothic.ttc",  # MS ゴシック
                "C:/Windows/Fonts/meiryo.ttc",    # メイリオ
                "C:/Windows/Fonts/YuGothic.ttc",  # 游ゴシック
                "C:/Windows/Fonts/msmincho.ttc",  # MS 明朝
                # macOS
                "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
                "/System/Library/Fonts/Hiragino Sans GB.ttc",
                "/Library/Fonts/Arial Unicode.ttf",
                # Linux
                "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/truetype/takao-gothic/TakaoGothic.ttf",
            ]
            
            for font_path in japanese_fonts:
                try:
                    title_font = ImageFont.truetype(font_path, self.title_font_size)
                    normal_font = ImageFont.truetype(font_path, self.default_font_size)
                    small_font = ImageFont.truetype(font_path, self.small_font_size)
                    font_loaded = True
                    break
                except:
                    continue
            
            # 日本語フォントが見つからない場合は英語フォントを試す
            if not font_loaded:
                try:
                    # Windowsフォントを試す
                    title_font = ImageFont.truetype("arial.ttf", self.title_font_size)
                    normal_font = ImageFont.truetype("arial.ttf", self.default_font_size)
                    small_font = ImageFont.truetype("arial.ttf", self.small_font_size)
                except:
                    # デフォルトフォント
                    title_font = ImageFont.load_default()
                    normal_font = ImageFont.load_default()
                    small_font = ImageFont.load_default()
            
            # QRコードの生成と配置（サイズを小さく）
            qr_img = None
            qr_width = 0
            if include_qr and qr_data:
                qr_img = self.generate_qr_code(qr_data, qr_size)
                qr_width = qr_size + 15  # マージン込み（縮小）
                # QRコードを右側に配置
                qr_x = width - qr_size - 8
                qr_y = (height - qr_size) // 2
                img.paste(qr_img, (qr_x, qr_y))
            
            # テキスト描画エリアの計算
            text_width = width - qr_width - 20  # 左マージン10 + QRコードとの間隔10
            text_x = 10
            current_y = 10
            
            # フィールドの描画
            for i, field in enumerate(printable_fields):
                field_name = field.get('name', '')
                field_value = field.get('value', '')
                field_type = field.get('type', '')
                
                # すべてのフィールドは通常フォントで表示（タイトルは除外済み）
                font = normal_font
                color = 'black'
                
                # フィールド名の描画
                name_text = f"{field_name}:"
                draw.text((text_x, current_y), name_text, fill='gray', font=small_font)
                current_y += self.small_font_size + 2
                
                # フィールド値の描画（長い場合は折り返し）
                value_lines = self.wrap_text(field_value, font, text_width - text_x)
                for line in value_lines:
                    if current_y + self.default_font_size > height - 10:
                        break  # ラベルからはみ出る場合は停止
                    draw.text((text_x, current_y), line, fill=color, font=font)
                    current_y += self.default_font_size + 3
                
                # フィールド間の間隔
                current_y += 5
                
                if current_y > height - 30:
                    break  # 残りスペースが少ない場合は停止
            
            # プレビュー画像をBase64エンコード
            img_buffer = io.BytesIO()
            img.save(img_buffer, format='PNG')
            img_base64 = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
            
            return {
                'success': True,
                'preview_image': f"data:image/png;base64,{img_base64}",
                'dimensions': {'width': width, 'height': height, 'label_size': label_size},
                'fields_count': len(printable_fields),
                'has_qr': include_qr and qr_data is not None
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'プレビュー生成エラー: {str(e)}'
            }
    
    def generate_qr_code(self, data: str, size: int) -> Image.Image:
        """QRコードを生成（データサイズを小さく）"""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,  # エラー訂正レベルを低く
            box_size=6,  # ボックスサイズを小さく
            border=1,    # ボーダーを小さく
        )
        qr.add_data(data)
        qr.make(fit=True)
        
        qr_img = qr.make_image(fill_color="black", back_color="white")
        return qr_img.resize((size, size), Image.Resampling.LANCZOS)
    
    def wrap_text(self, text: str, font, max_width: int) -> List[str]:
        """テキストを指定幅で折り返し"""
        lines = []
        words = text.split(' ')
        current_line = ""
        
        for word in words:
            test_line = current_line + (" " if current_line else "") + word
            # テキスト幅を概算（正確なgetsize()が使えない場合の代替）
            try:
                bbox = font.getbbox(test_line)
                text_width = bbox[2] - bbox[0]
            except:
                # フォールバック: 文字数ベースの概算
                text_width = len(test_line) * (self.default_font_size * 0.6)
            
            if text_width <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        
        if current_line:
            lines.append(current_line)
        
        return lines if lines else [text]
    
    def create_print_data(self, printable_fields: List[Dict[str, Any]], 
                         label_size: str = "62",
                         include_qr: bool = True,
                         qr_data: Optional[str] = None) -> Image.Image:
        """印刷用の画像データを作成"""
        # プレビューと同じロジックで実際の印刷用画像を生成
        preview_result = self.generate_preview(printable_fields, label_size, include_qr, qr_data)
        
        if preview_result.get('success'):
            # Base64データから画像を復元
            img_data = preview_result['preview_image'].split(',')[1]
            img_bytes = base64.b64decode(img_data)
            img = Image.open(io.BytesIO(img_bytes))
            return img
        else:
            # エラーの場合はダミー画像を返す
            img = Image.new('RGB', (696, 271), 'white')
            draw = ImageDraw.Draw(img)
            draw.text((50, 50), "エラー: 画像生成に失敗", fill='black')
            return img