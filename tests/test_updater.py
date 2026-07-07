"""updater モジュールのテスト"""

import hashlib
import zipfile
from unittest.mock import MagicMock, patch

import pytest

from updater import checker, downloader, _install_win
from updater.checker import parse_version, select_asset, find_checksum_url


class TestParseVersion:
    def test_tag_with_prefix(self):
        assert parse_version("v0.4.0") == (0, 4, 0)

    def test_plain_version(self):
        assert parse_version("1.12.3") == (1, 12, 3)

    def test_invalid(self):
        # 旧形式の日付タグ（v* 形式でない）は更新対象として扱わない
        assert parse_version("release-2026-05-28") is None
        assert parse_version("") is None
        assert parse_version(None) is None
        assert parse_version("v1.2") is None

    def test_comparison(self):
        assert parse_version("v0.10.0") > parse_version("v0.9.9")
        assert parse_version("v1.0.0") > parse_version("v0.99.99")


class TestSelectAsset:
    ASSETS = [
        {"name": "NotionOperator-0.5.0-macos-arm64.zip", "browser_download_url": "u1"},
        {"name": "NotionOperator-0.5.0-macos-arm64.zip.sha256", "browser_download_url": "u2"},
        {"name": "NotionOperator-0.5.0-windows-x64.zip", "browser_download_url": "u3"},
        {"name": "NotionOperator-0.5.0-windows-x64.zip.sha256", "browser_download_url": "u4"},
    ]

    def test_select_mac(self):
        asset = select_asset(self.ASSETS, "macos-arm64")
        assert asset["name"] == "NotionOperator-0.5.0-macos-arm64.zip"

    def test_select_windows(self):
        asset = select_asset(self.ASSETS, "windows-x64")
        assert asset["name"] == "NotionOperator-0.5.0-windows-x64.zip"

    def test_not_found(self):
        assert select_asset(self.ASSETS, "linux-x64") is None

    def test_checksum_url(self):
        url = find_checksum_url(self.ASSETS, "NotionOperator-0.5.0-macos-arm64.zip")
        assert url == "u2"

    def test_checksum_missing(self):
        assert find_checksum_url(self.ASSETS, "unknown.zip") is None


class TestCheckForUpdate:
    def _release(self, tag):
        return {
            "tag_name": tag,
            "html_url": f"https://github.com/x/releases/{tag}",
            "assets": TestSelectAsset.ASSETS,
        }

    @patch("updater.checker.platform_key", return_value="macos-arm64")
    @patch("updater.checker.fetch_latest_release")
    def test_newer_version(self, mock_fetch, _key):
        mock_fetch.return_value = self._release("v0.5.0")
        release = checker.check_for_update("0.4.0")
        assert release is not None
        assert release.version == (0, 5, 0)
        assert release.asset_name == "NotionOperator-0.5.0-macos-arm64.zip"
        assert release.checksum_url == "u2"

    @patch("updater.checker.platform_key", return_value="macos-arm64")
    @patch("updater.checker.fetch_latest_release")
    def test_same_version(self, mock_fetch, _key):
        mock_fetch.return_value = self._release("v0.4.0")
        assert checker.check_for_update("0.4.0") is None

    @patch("updater.checker.platform_key", return_value="macos-arm64")
    @patch("updater.checker.fetch_latest_release")
    def test_older_version(self, mock_fetch, _key):
        mock_fetch.return_value = self._release("v0.3.0")
        assert checker.check_for_update("0.4.0") is None

    @patch("updater.checker.platform_key", return_value=None)
    @patch("updater.checker.fetch_latest_release")
    def test_unsupported_platform(self, mock_fetch, _key):
        mock_fetch.return_value = self._release("v0.5.0")
        assert checker.check_for_update("0.4.0") is None


class TestInstallWin:
    def _make_zip(self, tmp_path):
        zip_path = tmp_path / "NotionOperator-0.5.0-windows-x64.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("Notion Operator.exe", b"new exe")
        return zip_path

    def test_helper_env_excludes_pyinstaller_vars(self, tmp_path, monkeypatch):
        # _PYI_* が新exeまで相続されると、削除済み _MEI フォルダを参照して
        # 起動に失敗する（Failed to load Python DLL）ため、除去されること
        monkeypatch.setenv("_PYI_APPLICATION_HOME_DIR", r"C:\Temp\_MEI404122")
        monkeypatch.setenv("_PYI_PARENT_PROCESS_LEVEL", "1")
        monkeypatch.setenv("_MEIPASS2", r"C:\Temp\_MEI404122")
        monkeypatch.setenv("NORMAL_VAR", "keep me")

        with patch("updater._install_win.subprocess.Popen") as mock_popen:
            _install_win.install_and_restart(
                self._make_zip(tmp_path), tmp_path / "old.exe"
            )

        env = mock_popen.call_args.kwargs["env"]
        assert "_PYI_APPLICATION_HOME_DIR" not in env
        assert "_PYI_PARENT_PROCESS_LEVEL" not in env
        assert "_MEIPASS2" not in env
        assert env["NORMAL_VAR"] == "keep me"

    def test_helper_script_replaces_and_restarts(self, tmp_path):
        old_exe = tmp_path / "Notion Operator.exe"
        with patch("updater._install_win.subprocess.Popen") as mock_popen:
            _install_win.install_and_restart(self._make_zip(tmp_path), old_exe)

        cmd = mock_popen.call_args.args[0]
        assert cmd[:2] == ["cmd", "/c"]
        script = cmd[2]
        content = open(script, encoding="cp932").read()
        assert "Wait-Process" in content
        assert str(old_exe) in content
        assert "Notion Operator.exe" in content

    def test_helper_waits_for_parent_process_too(self, tmp_path):
        # onefile ではブートローダー（親）が exe のロックを握ったまま
        # _MEI の削除を行うため、親子両方の PID を待つ必要がある
        import os

        with patch("updater._install_win.subprocess.Popen") as mock_popen:
            _install_win.install_and_restart(
                self._make_zip(tmp_path), tmp_path / "old.exe"
            )

        script = mock_popen.call_args.args[0][2]
        content = open(script, encoding="cp932").read()
        assert f"Wait-Process -Id {os.getpid()},{os.getppid()}" in content
        assert "-lt 60" in content

    def test_zip_without_exe(self, tmp_path):
        zip_path = tmp_path / "bad.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("readme.txt", b"no exe here")
        with pytest.raises(RuntimeError, match=".exe が見つかりません"):
            _install_win.install_and_restart(zip_path, tmp_path / "old.exe")


class TestVerifySha256:
    def _mock_response(self, text):
        response = MagicMock()
        response.text = text
        response.raise_for_status = MagicMock()
        return response

    def test_ok(self, tmp_path):
        path = tmp_path / "asset.zip"
        path.write_bytes(b"hello")
        digest = hashlib.sha256(b"hello").hexdigest()
        with patch("updater.downloader.requests.get",
                   return_value=self._mock_response(f"{digest}  asset.zip\n")):
            downloader.verify_sha256(path, "http://example/asset.zip.sha256")

    def test_mismatch(self, tmp_path):
        path = tmp_path / "asset.zip"
        path.write_bytes(b"hello")
        with patch("updater.downloader.requests.get",
                   return_value=self._mock_response("0" * 64)):
            with pytest.raises(RuntimeError, match="チェックサム"):
                downloader.verify_sha256(path, "http://example/asset.zip.sha256")
