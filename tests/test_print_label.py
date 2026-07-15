"""
print_label（ライブラリ優先 → CLI フォールバック）の単体テスト

- ライブラリ経路成功時: used_fallback=False、CLI は呼ばれない
- ライブラリ経路で例外時: print_with_cli が呼ばれ used_fallback=True になる

proxy と print_with_cli をモックする。brother_ql は実インストールに依存しないよう
sys.modules に偽モジュールを注入して差し替える。
"""

import sys
import os
import types
from contextlib import contextmanager
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image as PILImage

from brother_ql_proxy.utils import brother_format
from brother_ql_proxy.utils.brother_format import print_label


def _make_proxy(send_ok=True):
    proxy = Mock()
    proxy.config = {"printer_model": "QL-820NWB"}
    proxy.send_raw_data_to_printer.return_value = send_ok
    proxy.log = Mock()
    return proxy


def _dummy_image():
    return PILImage.new("RGB", (10, 10), "white")


@contextmanager
def fake_brother_ql(convert_return=b"RASTER", convert_side_effect=None):
    """brother_ql / brother_ql.raster / brother_ql.conversion を偽モジュールで差し替える。

    convert のモックを yield する。
    """
    convert_mock = Mock(name="convert")
    if convert_side_effect is not None:
        convert_mock.side_effect = convert_side_effect
    else:
        convert_mock.return_value = convert_return
    raster_cls = Mock(name="BrotherQLRaster")

    pkg = types.ModuleType("brother_ql")
    raster_mod = types.ModuleType("brother_ql.raster")
    raster_mod.BrotherQLRaster = raster_cls
    conversion_mod = types.ModuleType("brother_ql.conversion")
    conversion_mod.convert = convert_mock

    modules = {
        "brother_ql": pkg,
        "brother_ql.raster": raster_mod,
        "brother_ql.conversion": conversion_mod,
    }
    with patch.dict(sys.modules, modules):
        yield convert_mock


class TestLibraryPath:
    def test_ライブラリ経路成功_フォールバックしない(self):
        proxy = _make_proxy(send_ok=True)
        img = _dummy_image()

        with fake_brother_ql(convert_return=b"RASTER_BYTES") as convert_mock, \
             patch.object(brother_format, "print_with_cli") as mock_cli:
            result = print_label(img, "62x29", proxy)

        assert result == {"success": True, "used_fallback": False, "error": None}
        # ラベルサイズは '62x29' → '62' に正規化される
        assert convert_mock.call_args.kwargs["label"] == "62"
        # ライブラリで生成したバイト列をそのまま送信
        proxy.send_raw_data_to_printer.assert_called_once_with(b"RASTER_BYTES")
        # CLI は呼ばれない
        mock_cli.assert_not_called()


class TestFallbackPath:
    def test_ライブラリ経路で例外_CLIにフォールバック(self):
        proxy = _make_proxy(send_ok=True)
        img = _dummy_image()

        with fake_brother_ql(convert_side_effect=RuntimeError("boom")), \
             patch.object(brother_format, "print_with_cli", return_value=True) as mock_cli:
            result = print_label(img, "62", proxy)

        assert result["success"] is True
        assert result["used_fallback"] is True
        assert result["error"] is None
        # CLI 経路（convert_to_brother_format → print_with_cli）が呼ばれる
        mock_cli.assert_called_once()
        # フォールバックの旨が WARNING ログに出る
        assert any(
            call.args and call.args[-1] == "WARNING"
            for call in proxy.log.call_args_list
        )

    def test_import失敗でもCLIにフォールバック(self):
        """brother_ql が未インストール（import 失敗）でもフォールバックする"""
        proxy = _make_proxy(send_ok=True)
        img = _dummy_image()

        # brother_ql を sys.modules から消して import を失敗させる
        with patch.dict(sys.modules, {"brother_ql": None,
                                      "brother_ql.raster": None,
                                      "brother_ql.conversion": None}), \
             patch.object(brother_format, "print_with_cli", return_value=True) as mock_cli:
            result = print_label(img, "62", proxy)

        assert result["success"] is True
        assert result["used_fallback"] is True
        mock_cli.assert_called_once()

    def test_ライブラリ送信失敗_CLIにフォールバック(self):
        # ライブラリ経路は成功するが送信で失敗 → フォールバック（CLI 経路は成功）
        proxy = Mock()
        proxy.config = {"printer_model": "QL-820NWB"}
        proxy.log = Mock()
        # 1回目（ライブラリ経路）は False、2回目（CLI 経路）は True
        proxy.send_raw_data_to_printer.side_effect = [False, True]
        img = _dummy_image()

        with fake_brother_ql(convert_return=b"R"), \
             patch.object(brother_format, "print_with_cli", return_value=True) as mock_cli:
            result = print_label(img, "62", proxy)

        assert result == {"success": True, "used_fallback": True, "error": None}
        mock_cli.assert_called_once()

    def test_両経路失敗(self):
        proxy = _make_proxy(send_ok=False)
        img = _dummy_image()

        with fake_brother_ql(convert_side_effect=RuntimeError("boom")), \
             patch.object(brother_format, "print_with_cli", return_value=False):
            result = print_label(img, "62", proxy)

        assert result["success"] is False
        assert result["used_fallback"] is True
