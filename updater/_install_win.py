"""Windows: .exe の置き換え

実行中の .exe はロックされ上書きできないため、別プロセスのスクリプトに
「本体の終了を待つ → .exe を差し替え → 再起動」を任せる。
プロセス終了直後はファイルロック解放にラグがあることがあるため、
差し替えは最大10回リトライする。
"""

import os
import subprocess
import tempfile
import zipfile
from pathlib import Path

_PS_TEMPLATE = (
    "Wait-Process -Id {pid} -ErrorAction SilentlyContinue; "
    "for ($i = 0; $i -lt 10; $i++) {{ "
    "try {{ Move-Item -Force -LiteralPath '{new_exe}' '{old_exe}'; break }} "
    "catch {{ Start-Sleep -Seconds 1 }} }}; "
    "Start-Process -FilePath '{old_exe}'"
)

_BAT_TEMPLATE = """@echo off
powershell -NoProfile -ExecutionPolicy Bypass -Command "{ps_command}"
rmdir /s /q "{workdir}"
"""


def install_and_restart(zip_path: Path, old_exe: Path) -> None:
    workdir = Path(tempfile.mkdtemp(prefix="notion_operator_update_"))
    extract_dir = workdir / "extracted"

    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(extract_dir)
    exes = sorted(extract_dir.rglob("*.exe"))
    if not exes:
        raise RuntimeError("ダウンロードしたzipに .exe が見つかりません")
    new_exe = exes[0]

    ps_command = _PS_TEMPLATE.format(pid=os.getpid(), new_exe=new_exe, old_exe=old_exe)
    script_path = workdir / "update.bat"
    # cmd はバッチをOEMコードページ（日本語環境は cp932）で読む
    script_path.write_text(
        _BAT_TEMPLATE.format(ps_command=ps_command, workdir=workdir),
        encoding="cp932",
    )

    creationflags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(
        ["cmd", "/c", str(script_path)],
        creationflags=creationflags,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )
