"""macOS: .app バンドルの置き換え

実行中のアプリは自分自身を消せないため、別プロセスのシェルスクリプトに
「本体の終了を待つ → .app を差し替え → quarantine 除去 → 再起動」を任せる。
quarantine 属性はブラウザ経由のダウンロードでしか付かないが、
念のためスクリプト内でも除去する。
"""

import os
import subprocess
import tempfile
from pathlib import Path

_SCRIPT_TEMPLATE = """#!/bin/bash
while kill -0 {pid} 2>/dev/null; do sleep 0.5; done
rm -rf "{old_app}"
ditto "{new_app}" "{old_app}"
xattr -dr com.apple.quarantine "{old_app}" 2>/dev/null || true
open "{old_app}"
rm -rf "{workdir}"
"""


def install_and_restart(zip_path: Path, old_app: Path) -> None:
    workdir = Path(tempfile.mkdtemp(prefix="notion_operator_update_"))
    extract_dir = workdir / "extracted"

    # macOSのリソースフォーク・署名を保持するため unzip ではなく ditto を使う
    subprocess.run(
        ["/usr/bin/ditto", "-x", "-k", str(zip_path), str(extract_dir)],
        check=True,
        capture_output=True,
    )
    apps = sorted(extract_dir.glob("*.app"))
    if not apps:
        raise RuntimeError("ダウンロードしたzipに .app が見つかりません")
    new_app = apps[0]

    script_path = workdir / "update.sh"
    script_path.write_text(
        _SCRIPT_TEMPLATE.format(
            pid=os.getpid(),
            old_app=old_app,
            new_app=new_app,
            workdir=workdir,
        )
    )
    script_path.chmod(0o755)

    subprocess.Popen(
        ["/bin/bash", str(script_path)],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
