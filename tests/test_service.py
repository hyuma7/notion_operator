"""ExportServiceのレート制限対応テスト"""
import sys
import os

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from notion_client.errors import APIResponseError

from brother_ql_proxy.ui.export.service import ExportService, FetchCancelled


class TestRateLimitRetry:
    """レート制限リトライのテスト"""

    def setup_method(self):
        """各テスト前にサービスを初期化"""
        self.service = ExportService("fake_api_key", "fake_database_id")

    def test_successful_query_no_retry(self):
        """正常なクエリはリトライなしで成功"""
        mock_result = {"results": [{"id": "1"}], "has_more": False}
        self.service.notion = Mock()
        self.service.notion.databases.query.return_value = mock_result

        result = self.service._query_with_retry({"database_id": "test"})

        assert result == mock_result
        assert self.service.notion.databases.query.call_count == 1

    def test_retry_on_429_error(self):
        """429エラー時にリトライする"""
        # 最初は429、2回目は成功
        error_429 = APIResponseError(
            response=Mock(status_code=429),
            message="Rate limited",
            code="rate_limited"
        )
        error_429.status = 429

        mock_result = {"results": [], "has_more": False}

        self.service.notion = Mock()
        self.service.notion.databases.query.side_effect = [error_429, mock_result]

        # 待機時間を短縮
        self.service.INITIAL_RETRY_DELAY = 0.1
        self.service.REQUEST_DELAY = 0.01

        result = self.service._query_with_retry({"database_id": "test"})

        assert result == mock_result
        assert self.service.notion.databases.query.call_count == 2

    def test_cancel_during_retry_wait(self):
        """リトライ待機中にキャンセル可能"""
        error_429 = APIResponseError(
            response=Mock(status_code=429),
            message="Rate limited",
            code="rate_limited"
        )
        error_429.status = 429

        self.service.notion = Mock()
        self.service.notion.databases.query.side_effect = error_429

        self.service.INITIAL_RETRY_DELAY = 0.1
        self.service.REQUEST_DELAY = 0.01

        # 別スレッドでキャンセル
        import threading
        def cancel_after_delay():
            time.sleep(0.05)
            self.service.cancel()

        cancel_thread = threading.Thread(target=cancel_after_delay)
        cancel_thread.start()

        with pytest.raises(FetchCancelled):
            self.service._query_with_retry({"database_id": "test"})

        cancel_thread.join()

    def test_progress_callback_called(self):
        """進捗コールバックが呼ばれる"""
        mock_callback = Mock()
        self.service.set_progress_callback(mock_callback)

        mock_result = {"results": [{"id": "1"}], "has_more": False}
        self.service.notion = Mock()
        self.service.notion.databases.query.return_value = mock_result
        self.service.REQUEST_DELAY = 0.01

        # fetch_sales_dataを実行（モックで簡略化）
        self.service._report_progress(10, -1, "テストメッセージ")

        mock_callback.assert_called_with(10, -1, "テストメッセージ")

    def test_max_retries_exceeded(self):
        """最大リトライ回数を超えると例外"""
        error_429 = APIResponseError(
            response=Mock(status_code=429),
            message="Rate limited",
            code="rate_limited"
        )
        error_429.status = 429

        self.service.notion = Mock()
        self.service.notion.databases.query.side_effect = error_429

        self.service.MAX_RETRIES = 2
        self.service.INITIAL_RETRY_DELAY = 0.01
        self.service.REQUEST_DELAY = 0.01

        with pytest.raises(APIResponseError):
            self.service._query_with_retry({"database_id": "test"})

        assert self.service.notion.databases.query.call_count == 2

    def test_non_429_error_not_retried(self):
        """429以外のエラーはリトライしない"""
        error_500 = APIResponseError(
            response=Mock(status_code=500),
            message="Internal error",
            code="internal_error"
        )
        error_500.status = 500

        self.service.notion = Mock()
        self.service.notion.databases.query.side_effect = error_500

        with pytest.raises(APIResponseError):
            self.service._query_with_retry({"database_id": "test"})

        # 1回だけ呼ばれる（リトライなし）
        assert self.service.notion.databases.query.call_count == 1


class TestCancelFunctionality:
    """キャンセル機能のテスト"""

    def setup_method(self):
        self.service = ExportService("fake_api_key", "fake_database_id")

    def test_cancel_flag_initially_false(self):
        """初期状態ではキャンセルフラグはFalse"""
        assert self.service._cancelled is False

    def test_cancel_sets_flag(self):
        """cancel()でフラグがTrueになる"""
        self.service.cancel()
        assert self.service._cancelled is True

    def test_reset_cancel_clears_flag(self):
        """reset_cancel()でフラグがクリアされる"""
        self.service.cancel()
        self.service.reset_cancel()
        assert self.service._cancelled is False

    def test_check_cancelled_raises_when_cancelled(self):
        """キャンセル時に_check_cancelled()が例外を発生"""
        self.service.cancel()
        with pytest.raises(FetchCancelled):
            self.service._check_cancelled()


if __name__ == "__main__":
    # 簡易テスト実行
    print("=== レート制限リトライテスト ===")

    test = TestRateLimitRetry()

    test.setup_method()
    test.test_successful_query_no_retry()
    print("✓ test_successful_query_no_retry")

    test.setup_method()
    test.test_retry_on_429_error()
    print("✓ test_retry_on_429_error")

    test.setup_method()
    test.test_progress_callback_called()
    print("✓ test_progress_callback_called")

    test.setup_method()
    test.test_non_429_error_not_retried()
    print("✓ test_non_429_error_not_retried")

    print("\n=== キャンセル機能テスト ===")

    test2 = TestCancelFunctionality()

    test2.setup_method()
    test2.test_cancel_flag_initially_false()
    print("✓ test_cancel_flag_initially_false")

    test2.setup_method()
    test2.test_cancel_sets_flag()
    print("✓ test_cancel_sets_flag")

    test2.setup_method()
    test2.test_reset_cancel_clears_flag()
    print("✓ test_reset_cancel_clears_flag")

    test2.setup_method()
    test2.test_check_cancelled_raises_when_cancelled()
    print("✓ test_check_cancelled_raises_when_cancelled")

    print("\n全テスト成功!")
