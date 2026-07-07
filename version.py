"""アプリのバージョン定義（唯一のソース）

リリース手順:
1. ここの __version__ を上げる
2. コミットして v{__version__} のタグを push
3. GitHub Actions が両OSのビルドを Release に添付する
"""

__version__ = "0.4.5"
