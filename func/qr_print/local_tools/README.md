# Local Tools - Notion QR Label Generator

## 📋 概要

ローカル環境でQRラベルの生成・プレビュー・印刷を行うツール群です。

## 🛠️ ツール一覧

### **notion_qr_html.py** - HTMLプレビュー版
- ライブラリ不要でブラウザでプレビュー可能
- 大きなフォント対応済み
- QRコードデータをツールチップで確認

```bash
python3 notion_qr_html.py
```

### **notion_qr_image_large.py** - 高品質画像生成版
- 大きなフォント・QRコード対応
- 実際の印刷用画像を生成
- PIL・qrcodeライブラリが必要

```bash
# ライブラリインストール
pip install pillow qrcode[pil]

# 画像生成
python3 notion_qr_image_large.py
```

### **test_image_print.py** - Brother QL印刷テスト
- Brother QLプリンターでの印刷テスト
- 実際の印刷確認済み

```bash
python3 test_image_print.py path/to/image.png
```

## 🎯 使用フロー

1. **HTMLプレビュー**で確認 → `notion_qr_html.py`
2. **画像生成**で印刷用ファイル作成 → `notion_qr_image_large.py`
3. **Brother QLで印刷** → `test_image_print.py`

## 📝 特徴

### フォントサイズ（画像版）
- **タイトル**: 32px（大きく読みやすい）
- **フィールド**: 28px（しっかり見える）
- **QRコード**: 250px（スキャンしやすい）

### 対応ラベルサイズ
- **62x29mm** - 小さなラベル
- **62x100mm** - 大きなラベル

## 🔧 カスタマイズ

### 表示フィールドの変更

```python
display_fields = ["title", "category", "Location", "SerialNumber", "date"]
```

### プリンター設定

```python
# test_image_print.py 内で設定
PRINTER_IP = "192.168.1.100"
PRINTER_MODEL = "QL-820NWB"
```

## 📦 依存関係

```bash
# HTMLプレビュー版（ライブラリ不要）
# → そのまま実行可能

# 画像生成版
pip install pillow qrcode[pil]

# 印刷版
# → Brother QLプリンターとbrother_qlコマンド
```