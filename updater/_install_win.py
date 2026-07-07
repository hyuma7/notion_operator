"""Windows: .exe の置き換え

実行中の .exe はロックされ上書きできないため、別プロセスのスクリプトに
「本体の終了を待つ → .exe を差し替え → 再起動」を任せる。

PyInstaller onefile ではアプリ本体（子）だけでなくブートローダー（親）も
同じ .exe を実行しており、親が _MEI フォルダの削除を終えて終了するまで
.exe はロックされたままになる。そのため親子両方の PID を待ってから
差し替える。ウイルススキャンや OneDrive 同期による一時的なロックに
備えて差し替えは最大60回リトライし、それでも失敗した場合は
%TEMP% にエラーログを残して旧 exe を再起動する。
"""

import os
import subprocess
import tempfile
import zipfile
from pathlib import Path

_PS_TEMPLATE = (
    "Wait-Process -Id {pids} -ErrorAction SilentlyContinue; "
    "for ($i = 0; $i -lt 60; $i++) {{ "
    "try {{ Move-Item -Force -LiteralPath '{new_exe}' '{old_exe}'; break }} "
    "catch {{ Start-Sleep -Seconds 1 }} }}; "
    "if (Test-Path -LiteralPath '{new_exe}') {{ "
    "Set-Content -LiteralPath '{error_log}' "
    "'update failed: could not replace exe' }}; "
    "Start-Process -FilePath '{old_exe}'"
)

_BAT_TEMPLATE = """@echo off
powershell -NoProfile -ExecutionPolicy Bypass -Command "{ps_command}"
rmdir /s /q "{workdir}"
"""


def _clean_env() -> dict:
    """PyInstaller onefile の内部環境変数を除去した環境を返す

    _PYI_* が新しい exe まで相続されると、ブートローダーが自身を
    「実行中アプリのサブプロセス」と誤認して再展開をスキップし、
    旧プロセスの終了時に削除済みの _MEI フォルダから DLL を
    ロードしようとして起動に失敗する。
    """
    return {
        k: v
        for k, v in os.environ.items()
        if not k.startswith("_PYI_") and k != "_MEIPASS2"
    }


def install_and_restart(zip_path: Path, old_exe: Path) -> None:
    workdir = Path(tempfile.mkdtemp(prefix="notion_operator_update_"))
    extract_dir = workdir / "extracted"

    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(extract_dir)
    exes = sorted(extract_dir.rglob("*.exe"))
    if not exes:
        raise RuntimeError("ダウンロードしたzipに .exe が見つかりません")
    new_exe = exes[0]

    error_log = Path(tempfile.gettempdir()) / "NotionOperator-update-error.log"
    ps_command = _PS_TEMPLATE.format(
        pids=f"{os.getpid()},{os.getppid()}",
        new_exe=new_exe,
        old_exe=old_exe,
        error_log=error_log,
    )
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
        env=_clean_env(),
    )
