import json

from notion import fetch_page


def test_get_api_key_reads_config_file(tmp_path, monkeypatch):
    config_file = tmp_path / "printer_proxy_config.json"
    config_file.write_text(
        json.dumps(
            {
                "notion_api_key": "  test_api_key  ",
                "notion_database_id": "  test_database_id  ",
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(fetch_page, "CONFIG_FILE", str(config_file))
    monkeypatch.setattr(fetch_page, "LEGACY_CONFIG_FILES", ())
    monkeypatch.delenv("NOTION_API_KEY", raising=False)
    monkeypatch.delenv("NOTION_DATABASE_ID", raising=False)

    assert fetch_page._get_api_key() == "test_api_key"
    assert fetch_page._get_database_id() == "test_database_id"


def test_get_api_key_falls_back_to_env(tmp_path, monkeypatch):
    missing_config = tmp_path / "missing.json"

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(fetch_page, "CONFIG_FILE", str(missing_config))
    monkeypatch.setattr(fetch_page, "LEGACY_CONFIG_FILES", ())
    monkeypatch.setenv("NOTION_API_KEY", " env_api_key ")
    monkeypatch.setenv("NOTION_DATABASE_ID", " env_database_id ")

    assert fetch_page._get_api_key() == "env_api_key"
    assert fetch_page._get_database_id() == "env_database_id"
