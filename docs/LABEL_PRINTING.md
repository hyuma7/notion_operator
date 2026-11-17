# ラベル印刷アーキテクチャ

Brother QL プリンターへのラベル印刷は **2段構え** で実行される。
実装は `brother_ql_proxy/utils/brother_format.py` の `print_label()`、
呼び出しは `brother_ql_proxy/ui/label_tab.py` の `on_print()`。

## 印刷フロー

1. **ライブラリ経路（優先）**
   `brother_ql`（PyPI パッケージ `brother-ql-next`）を **ライブラリとして直接** 利用し、
   `BrotherQLRaster` + `convert()` でラスターバイト列を生成、
   `PrinterProxy.send_raw_data_to_printer()` で TCP ソケット送信する。
   外部コマンド（`brother_ql` CLI）に依存しないため、PATH を継承しない
   Mac のパッケージ版 GUI アプリでも動作する。

2. **CLI フォールバック**
   ライブラリ経路が例外（import 失敗を含む）または送信失敗になった場合、
   `WARNING` ログを残したうえで従来の `print_with_cli()`（subprocess で
   `brother_ql` CLI を叩く方式）にフォールバックする。

`print_label()` の戻り値は `{"success": bool, "used_fallback": bool, "error": str | None}`。

## UI 表示

- 通常経路（ライブラリ）で成功 … 「印刷完了」（緑）のみ
- **フォールバックで成功 … 「印刷完了」に加えて小さく「フォールバックで実行しました」（グレー）** を表示
- 失敗 … 「印刷失敗: <error>」（赤）

「フォールバックで実行しました」が出た場合、その端末ではライブラリ経路が
機能していない（依存が同梱されていない・import エラーなど）ことを示す。

## フォールバックが動く条件

CLI フォールバックはホストに `brother_ql` CLI が入っている必要がある
（`pip install brother-ql-next` などで PATH に `brother_ql` コマンドが通っていること）。
パッケージ版アプリでは PATH を継承しないため、フォールバックは基本的に
開発環境／CLI 導入済みホストでのみ機能する。

## CLI 方式の撤去判断

CLI フォールバックは移行期の保険。運用上、
**「フォールバックで実行しました」の表示が出なくなった**（＝全端末でライブラリ経路が
安定して成功している）ことが確認できたら、
`convert_to_brother_format()` / `print_with_cli()` およびフォールバック分岐を
撤去してよい。
