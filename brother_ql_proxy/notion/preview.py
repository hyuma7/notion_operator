"""
ラベルプレビュー生成モジュール
"""

import io
import os
import sys
import base64
from typing import Dict, Any, List, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont
import qrcode


class LabelPreviewGenerator:
    """ラベルプレビューを生成するクラス"""
    
    def __init__(self):
        pass  # Font sizes will be calculated dynamically based on the font_size parameter
    
    def generate_preview(self, printable_fields: List[Dict[str, Any]], 
                        label_size: str = "62", 
                        include_qr: bool = True,
                        qr_data: Optional[str] = None,
                        font_size: int = 16,
                        qr_size_scale: int = 3,
                        auto_extend_height: bool = True,
                        layout_mode: str = "vertical") -> Dict[str, Any]:
        """印刷プレビューを生成"""
        try:
            # パラメータの型変換を確実に行う
            font_size = int(font_size) if font_size is not None else 16
            qr_size_scale = int(qr_size_scale) if qr_size_scale is not None else 3
            # ラベルサイズの設定
            width = 696  # 幅は固定
            if label_size in ['62x29', '62']:
                initial_height = 271  # 初期高さ
                base_qr_size = 50  # ベースサイズ
            elif label_size == '62x100':
                initial_height = 1109
                base_qr_size = 75  # ベースサイズ
            else:
                initial_height = 271
                base_qr_size = 50  # ベースサイズ
            
            # 動的高さ計算のための初期設定
            if auto_extend_height:
                height = self._calculate_required_height(printable_fields, width, font_size, base_qr_size, qr_size_scale, initial_height, include_qr, layout_mode)
            else:
                height = initial_height
            
            # QRコードサイズをスケールに基づいて計算
            qr_size = base_qr_size * qr_size_scale
            
            # 背景画像を作成
            img = Image.new('RGB', (width, height), 'white')
            draw = ImageDraw.Draw(img)
            
            # フォントの読み込み（日本語対応）
            font_loaded = False
            # フォントサイズの最小値を保証（0以下になるとエラー）
            sz_title = max(8, font_size + 4)
            sz_normal = max(8, font_size)
            sz_small = max(8, font_size - 2)

            # 日本語フォントのパスリストを OS 別に構築
            windir = os.environ.get("WINDIR", os.environ.get("SystemRoot", "C:\\Windows"))
            japanese_fonts = []

            if sys.platform == "win32":
                fonts_dir = os.path.join(windir, "Fonts")
                japanese_fonts = [
                    os.path.join(fonts_dir, "msgothic.ttc"),
                    os.path.join(fonts_dir, "meiryo.ttc"),
                    os.path.join(fonts_dir, "YuGothB.ttc"),
                    os.path.join(fonts_dir, "yugothic.ttf"),
                    os.path.join(fonts_dir, "msmincho.ttc"),
                ]
            else:
                japanese_fonts = [
                    # WSL
                    "/mnt/c/Windows/Fonts/msgothic.ttc",
                    "/mnt/c/Windows/Fonts/meiryo.ttc",
                    # macOS
                    "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
                    "/Library/Fonts/Arial Unicode.ttf",
                    # Linux
                    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                    "/usr/share/fonts/truetype/takao-gothic/TakaoGothic.ttf",
                    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
                ]

            for font_path in japanese_fonts:
                if not os.path.exists(font_path):
                    continue
                try:
                    title_font = ImageFont.truetype(font_path, sz_title)
                    normal_font = ImageFont.truetype(font_path, sz_normal)
                    small_font = ImageFont.truetype(font_path, sz_small)
                    font_loaded = True
                    break
                except Exception:
                    continue

            # 日本語フォントが見つからない場合のフォールバック
            if not font_loaded:
                try:
                    title_font = ImageFont.truetype("arial.ttf", sz_title)
                    normal_font = ImageFont.truetype("arial.ttf", sz_normal)
                    small_font = ImageFont.truetype("arial.ttf", sz_small)
                except Exception:
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
            
            # レイアウトモードに応じた描画
            if layout_mode == "vertical":
                self._draw_vertical_layout(draw, printable_fields, normal_font, small_font, 
                                         width, height, qr_width, font_size, auto_extend_height)
            elif layout_mode == "horizontal":
                self._draw_horizontal_layout(draw, printable_fields, normal_font, small_font, 
                                           width, height, qr_width, font_size, auto_extend_height, 2)
            elif layout_mode == "compact":
                self._draw_horizontal_layout(draw, printable_fields, normal_font, small_font, 
                                           width, height, qr_width, font_size, auto_extend_height, 3)
            else:
                # デフォルトは縦並び
                self._draw_vertical_layout(draw, printable_fields, normal_font, small_font, 
                                         width, height, qr_width, font_size, auto_extend_height)
            
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
    
    def wrap_text(self, text: str, font, max_width: int, font_size: int = 16) -> List[str]:
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
                text_width = len(test_line) * (font_size * 0.6)
            
            if text_width <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        
        if current_line:
            lines.append(current_line)
        
        return lines if lines else [text]
    
    def _calculate_required_height(self, printable_fields: List[Dict[str, Any]], 
                                  width: int, font_size: int, base_qr_size: int, 
                                  qr_size_scale: int, min_height: int, include_qr: bool, layout_mode: str = "vertical") -> int:
        """必要な高さを計算"""
        try:
            # QRコードのサイズ計算
            qr_size = base_qr_size * qr_size_scale if include_qr else 0
            qr_width = qr_size + 15 if include_qr else 0
            
            # テキスト描画エリアの計算
            text_width = width - qr_width - 20  # 左マージン10 + QRコードとの間隔10
            current_y = 10  # 上マージン
            
            # 仮のフォントを作成（高さ計算用）
            temp_font = None
            _windir = os.environ.get("WINDIR", os.environ.get("SystemRoot", "C:\\Windows"))
            _candidates = (
                [
                    os.path.join(_windir, "Fonts", "msgothic.ttc"),
                    os.path.join(_windir, "Fonts", "meiryo.ttc"),
                ]
                if sys.platform == "win32"
                else [
                    "/mnt/c/Windows/Fonts/msgothic.ttc",
                    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                ]
            )
            for _fp in _candidates:
                if not os.path.exists(_fp):
                    continue
                try:
                    temp_font = ImageFont.truetype(_fp, max(8, font_size))
                    break
                except Exception:
                    continue
            if temp_font is None:
                temp_font = ImageFont.load_default()
            
            # レイアウトモードに応じた高さ計算
            if layout_mode == "horizontal":
                # 横並び（2列）の場合
                columns = 2
                column_height = self._calculate_column_height(printable_fields, text_width // columns, font_size, temp_font, columns)
                current_y += column_height
            elif layout_mode == "compact":
                # コンパクト（3列）の場合
                columns = 3
                column_height = self._calculate_column_height(printable_fields, text_width // columns, font_size, temp_font, columns)
                current_y += column_height
            else:
                # 縦並び（デフォルト）の場合
                for field in printable_fields:
                    field_name = field.get('name', '')
                    field_value = field.get('value', '')
                    
                    # 短い値の場合は横並び、長い値の場合は縦並び
                    if len(field_value) <= 30:
                        # 横並び（同じ行）の場合
                        current_y += font_size + 3
                    else:
                        # 縦並び（次の行）の場合
                        current_y += (font_size - 2) + 2  # フィールド名の高さ
                        value_lines = self.wrap_text(field_value, temp_font, text_width - 10, font_size)
                        for _ in value_lines:
                            current_y += font_size + 3
                    
                    # フィールド間の間隔
                    current_y += 5
            
            # 下マージンを追加
            required_height = current_y + 30
            
            # 最小高さを保証し、QRコードの高さも考慮
            if include_qr:
                qr_required_height = qr_size + 20  # QRコード + マージン
                required_height = max(required_height, qr_required_height)
            
            final_height = max(required_height, min_height)
            
            # 高さを適切な単位に丸める（Brother QLプリンターの仕様に合わせて）
            final_height = ((final_height + 15) // 16) * 16  # 16ピクセル単位に丸める
            
            return final_height
            
        except Exception as e:
            # エラーの場合は最小高さを返す
            return min_height
    
    def _draw_vertical_layout(self, draw, printable_fields, normal_font, small_font, 
                             width, height, qr_width, font_size, auto_extend_height):
        """縦並びレイアウトで描画"""
        text_width = width - qr_width - 20  # 左マージン10 + QRコードとの間隔10
        text_x = 10
        current_y = 10
        
        for i, field in enumerate(printable_fields):
            field_name = field.get('name', '')
            field_value = field.get('value', '')
            
            # フィールド名の幅を計算
            name_text = f"{field_name}:"
            try:
                name_bbox = small_font.getbbox(name_text)
                name_width = name_bbox[2] - name_bbox[0] + 5  # 5px間隔
            except:
                name_width = len(name_text) * (font_size * 0.5) + 5  # フォールバック
            
            # フィールド名を描画
            draw.text((text_x, current_y), name_text, fill='gray', font=small_font)
            
            # フィールド値を名前の横に描画（短い場合）
            value_text_width = text_width - name_width
            
            # 値が短い場合は同じ行に、長い場合は次の行に
            if len(field_value) <= 30:  # 短いテキストの場合
                # 同じ行に描画
                draw.text((text_x + name_width, current_y), field_value, fill='black', font=normal_font)
                current_y += font_size + 3
            else:
                # 長いテキストの場合は次の行に
                current_y += (font_size - 2) + 2
                value_lines = self.wrap_text(field_value, normal_font, text_width - text_x, font_size)
                for line in value_lines:
                    if not auto_extend_height and current_y + font_size > height - 10:
                        break
                    draw.text((text_x, current_y), line, fill='black', font=normal_font)
                    current_y += font_size + 3
            
            # フィールド間の間隔
            current_y += 5
            
            # 動的高さが有効でない場合のみスペース制限
            if not auto_extend_height and current_y > height - 30:
                break  # 残りスペースが少ない場合は停止
    
    def _draw_horizontal_layout(self, draw, printable_fields, normal_font, small_font, 
                               width, height, qr_width, font_size, auto_extend_height, columns):
        """横並びレイアウトで描画"""
        available_width = width - qr_width - 20  # 利用可能幅
        column_width = available_width // columns  # 各カラムの幅
        column_spacing = 10  # カラム間の間隔
        
        # 各カラムの開始位置とY位置を初期化
        column_positions = []
        column_y_positions = []
        
        for col in range(columns):
            start_x = 10 + col * column_width
            column_positions.append(start_x)
            column_y_positions.append(10)  # 初期Y位置
        
        # フィールドをカラムに分散配置
        for i, field in enumerate(printable_fields):
            col_index = i % columns  # 現在のカラムインデックス
            current_x = column_positions[col_index]
            current_y = column_y_positions[col_index]
            
            field_name = field.get('name', '')
            field_value = field.get('value', '')
            
            # フィールド名の幅を計算
            name_text = f"{field_name}:"
            try:
                name_bbox = small_font.getbbox(name_text)
                name_width = name_bbox[2] - name_bbox[0] + 5  # 5px間隔
            except:
                name_width = len(name_text) * (font_size * 0.4) + 5  # フォールバック（カラム内なので小さめ）
            
            # フィールド名を描画
            draw.text((current_x, current_y), name_text, fill='gray', font=small_font)
            
            # カラム内での有効幅を計算
            effective_width = column_width - column_spacing
            value_area_width = effective_width - name_width
            
            # 値の長さに応じて配置を決定
            if len(field_value) <= 15 and name_width < effective_width * 0.4:  # 短い値 & 名前が短い場合
                # 同じ行に描画
                draw.text((current_x + name_width, current_y), field_value, fill='black', font=normal_font)
                current_y += font_size + 3
            else:
                # 次の行に描画
                current_y += (font_size - 2) + 2
                value_lines = self.wrap_text(field_value, normal_font, effective_width, font_size)
                
                for line in value_lines:
                    if not auto_extend_height and current_y + font_size > height - 10:
                        break
                    draw.text((current_x, current_y), line, fill='black', font=normal_font)
                    current_y += font_size + 3
            
            # フィールド間の間隔
            current_y += 8
            
            # カラムのY位置を更新
            column_y_positions[col_index] = current_y
            
            # 動的高さが有効でない場合のみスペース制限
            if not auto_extend_height and current_y > height - 30:
                break  # 残りスペースが少ない場合は停止
    
    def _calculate_column_height(self, printable_fields, column_width, font_size, temp_font, columns):
        """カラム配置での必要高さを計算"""
        column_heights = [0] * columns
        
        for i, field in enumerate(printable_fields):
            col_index = i % columns
            field_name = field.get('name', '')
            field_value = field.get('value', '')
            
            # 名前の幅を概算
            name_width = len(field_name) * (font_size * 0.4) + 5
            effective_width = column_width - 10
            
            # 短い値の場合は横並び、長い値の場合は縦並び
            if len(field_value) <= 15 and name_width < effective_width * 0.4:
                # 横並び（同じ行）の場合
                column_heights[col_index] += font_size + 3
            else:
                # 縦並び（次の行）の場合
                column_heights[col_index] += (font_size - 2) + 2  # フィールド名の高さ
                value_lines = self.wrap_text(field_value, temp_font, effective_width, font_size)
                for _ in value_lines:
                    column_heights[col_index] += font_size + 3
            
            # フィールド間の間隔
            column_heights[col_index] += 8
        
        # 最も高いカラムの高さを返す
        return max(column_heights) if column_heights else 0
    
    def create_print_data(self, printable_fields: List[Dict[str, Any]], 
                         label_size: str = "62",
                         include_qr: bool = True,
                         qr_data: Optional[str] = None,
                         font_size: int = 16,
                         qr_size_scale: int = 3,
                         auto_extend_height: bool = True,
                         layout_mode: str = "vertical") -> Image.Image:
        """印刷用の画像データを作成"""
        # パラメータの型変換を確実に行う
        font_size = int(font_size) if font_size is not None else 16
        qr_size_scale = int(qr_size_scale) if qr_size_scale is not None else 3
        
        # プレビューと同じロジックで実際の印刷用画像を生成
        preview_result = self.generate_preview(printable_fields, label_size, include_qr, qr_data, font_size, qr_size_scale, auto_extend_height, layout_mode)
        
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