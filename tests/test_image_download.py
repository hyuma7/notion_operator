"""
画像ダウンロード機能の単体テスト
notion_tab.py の _download_images ロジックを Flet なしで直接テスト
"""

import re
import shutil
import sys
import os
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).parent


# ===== テスト対象のコアロジック（Flet依存なし） =====

def download_images_to_dir(files: list, save_dir: Path) -> tuple[int, int]:
    """ファイルリストから画像をダウンロードして保存。Returns: (成功数, 失敗数)"""
    save_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    errors = 0
    for i, f in enumerate(files):
        url = f.get("url")
        name = f.get("name", f"image_{i:02d}.jpg")
        if not url:
            continue
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            (save_dir / name).write_bytes(resp.content)
            count += 1
            print(f"  OK {name} ({len(resp.content):,} bytes)")
        except Exception as e:
            errors += 1
            print(f"  NG {name}: {e}")
    return count, errors


def make_safe_name(product_name: str) -> str:
    """商品名から安全なフォルダ名を生成（notion_tab.py と同じロジック）"""
    return re.sub(r'[\\/*?:"<>|]', "_", product_name)[:30] if product_name else "images"


# ===== テスト関数 =====

def test_files_type_detection():
    """files型（画像リスト）の検出ロジックのテスト"""
    print("\n=== テスト1: files型検出 ===")
    pass_count = 0

    cases = [
        # (value, 期待するis_files, 説明)
        ([{"name": "img.jpg", "url": "https://example.com/img.jpg"}], True, "画像リスト"),
        (["option1", "option2"], False, "通常リスト"),
        ([{"name": "item"}], False, "URLなしdict"),
        ([], False, "空リスト"),
        ("テキスト", False, "文字列"),
    ]

    for value, expected, desc in cases:
        is_files = isinstance(value, list) and bool(value) and isinstance(value[0], dict) and "url" in value[0]
        ok = (is_files == expected)
        print(f"  {'OK' if ok else 'NG'} {desc}: is_files={is_files} (期待={expected})")
        if ok:
            pass_count += 1

    print(f"  結果: {pass_count}/{len(cases)} 合格")
    return pass_count == len(cases)


def test_safe_name_generation():
    """商品名からの安全なフォルダ名生成テスト"""
    print("\n=== テスト2: フォルダ名生成 ===")
    pass_count = 0

    cases = [
        ("Sony VAIO type T", "Sony VAIO type T"),
        ("商品/テスト:2024", "商品_テスト_2024"),
        ('A*B?C"D<E>F|G', "A_B_C_D_E_F_G"),
        ("", "images"),  # 空文字 → "images"
    ]

    for product_name, expected in cases:
        result = make_safe_name(product_name) if product_name else "images"
        ok = result == expected
        print(f"  {'OK' if ok else 'NG'} '{product_name}' → '{result}' (期待='{expected}')")
        if ok:
            pass_count += 1

    # 長い名前は30文字でカット
    long_name = "非常に長い商品名" * 10
    result = make_safe_name(long_name)
    ok = len(result) <= 30
    print(f"  {'OK' if ok else 'NG'} 長い商品名 → {len(result)}文字 (30文字以下)")
    if ok:
        pass_count += 1

    total = len(cases) + 1
    print(f"  結果: {pass_count}/{total} 合格")
    return pass_count == total


def test_download_public_images():
    """公開URLで画像ダウンロードができるかテスト"""
    print("\n=== テスト3: 公開URL画像ダウンロード ===")

    test_files = [
        {"name": "test_jpeg.jpg", "url": "https://httpbin.org/image/jpeg"},
        {"name": "test_png.png",  "url": "https://httpbin.org/image/png"},
    ]

    save_dir = PROJECT_ROOT / "downloads" / "_test_download"
    if save_dir.exists():
        shutil.rmtree(save_dir)

    count, errors = download_images_to_dir(test_files, save_dir)
    print(f"  ダウンロード結果: {count}枚成功, {errors}件失敗")

    # ファイル存在確認
    saved = []
    for f in test_files:
        fp = save_dir / f["name"]
        if fp.exists() and fp.stat().st_size > 0:
            saved.append(fp.name)
            print(f"  OK {fp.name} 保存確認 ({fp.stat().st_size:,} bytes)")
        else:
            print(f"  NG {fp.name} 保存されていない")

    # クリーンアップ
    if save_dir.exists():
        shutil.rmtree(save_dir)
        print(f"  テスト用フォルダを削除しました")

    ok = count == len(test_files) and errors == 0
    print(f"  結果: {'合格' if ok else '不合格'}")
    return ok


def test_absolute_path():
    """save_dir が絶対パスになっているかテスト"""
    print("\n=== テスト4: 保存先の絶対パス確認 ===")

    project_root = Path(os.path.dirname(os.path.dirname(os.path.abspath(
        # listing_gui/notion_tab.py の __file__ に相当する仮パス
        str(PROJECT_ROOT / "listing_gui" / "notion_tab.py")
    ))))
    save_dir = project_root / "downloads" / "test_product"

    ok = save_dir.is_absolute()
    print(f"  {'OK' if ok else 'NG'} save_dir は絶対パス: {save_dir}")
    print(f"  期待するプロジェクトルート: {PROJECT_ROOT}")
    same_root = project_root.resolve() == PROJECT_ROOT.resolve()
    print(f"  {'OK' if same_root else 'NG'} プロジェクトルートが一致: {same_root}")

    return ok and same_root


# ===== エントリーポイント =====

if __name__ == "__main__":
    print("=" * 55)
    print("画像ダウンロード機能 テストスイート")
    print("=" * 55)

    results = [
        ("files型検出",         test_files_type_detection()),
        ("フォルダ名生成",       test_safe_name_generation()),
        ("絶対パス確認",         test_absolute_path()),
        ("公開URL画像DL",        test_download_public_images()),
    ]

    print("\n" + "=" * 55)
    print("テスト結果サマリー")
    print("=" * 55)
    all_ok = True
    for name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"  {status}  {name}")
        if not result:
            all_ok = False
    print("=" * 55)
    print("全テスト合格" if all_ok else "失敗あり - 上記ログを確認してください")

    sys.exit(0 if all_ok else 1)
