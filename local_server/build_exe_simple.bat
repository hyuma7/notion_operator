@echo off
echo Brother QL プリンタープロキシ 簡単EXE作成
echo.

REM 仮想環境をアクティベート
call .\venv\Scripts\activate.bat

REM PyInstallerでシンプルなEXEを作成
echo EXEファイルを作成中...
pyinstaller --onefile --name "BrotherQL_Proxy" run_proxy.py

echo.
echo 完了！ dist\BrotherQL_Proxy.exe を確認してください
pause