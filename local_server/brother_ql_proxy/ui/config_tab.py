"""
設定タブコンポーネント
"""

import flet as ft


class ConfigTab:
    def __init__(self, proxy, page: ft.Page):
        self.proxy = proxy
        self.page = page
        
        # 設定フィールド
        self.printer_ip_field = ft.TextField(
            label="プリンターIP",
            value=proxy.config['printer_ip'],
            width=300
        )
        
        self.printer_port_field = ft.TextField(
            label="プリンターポート",
            value=str(proxy.config['printer_port']),
            width=300
        )
        
        self.proxy_port_field = ft.TextField(
            label="プロキシポート",
            value=str(proxy.config['proxy_port']),
            width=300
        )
        
        self.ngrok_token_field = ft.TextField(
            label="ngrok認証トークン",
            value=proxy.config.get('ngrok_authtoken', ''),
            password=True,
            width=300
        )
        
        self.ngrok_switch = ft.Switch(
            label="ngrokを有効化",
            value=proxy.config.get('enable_ngrok', False)
        )
        
        self.label_size_dropdown = ft.Dropdown(
            label="ラベルサイズ",
            width=300,
            options=[
                ft.dropdown.Option("62x29"),
                ft.dropdown.Option("62x100"),
            ],
            value=proxy.config.get('label_size', '62x29')
        )
        
        self.ngrok_domain_field = ft.TextField(
            label="ngrok固定ドメイン（例: ○○.ngrok-free.app）",
            width=300,
            value=proxy.config.get('ngrok_domain', '')
        )
        
        self.ngrok_reserved_domain_id_field = ft.TextField(
            label="ngrok予約済みドメインID（例: rd_○○）",
            width=300,
            value=proxy.config.get('ngrok_reserved_domain_id', '')
        )
        
        self.secret_key_field = ft.TextField(
            label="外部アクセス用シークレットキー",
            value=proxy.config.get('secret_key', ''),
            password=True,
            width=300,
            helper_text="外部からのアクセス時に'secret'ヘッダーで必要です"
        )

        # Notion設定
        self.notion_api_key_field = ft.TextField(
            label="Notion API Key",
            value=proxy.config.get('notion_api_key', ''),
            password=True,
            width=300
        )

        self.notion_database_id_field = ft.TextField(
            label="Notion Database ID",
            value=proxy.config.get('notion_database_id', ''),
            width=300
        )

        self.save_btn = ft.ElevatedButton(
            "設定を保存",
            icon=ft.Icons.SAVE,
            on_click=self.save_config
        )
    
    def save_config(self, e):
        """設定を保存"""
        try:
            self.proxy.config['printer_ip'] = self.printer_ip_field.value
            self.proxy.config['printer_port'] = int(self.printer_port_field.value)
            self.proxy.config['proxy_port'] = int(self.proxy_port_field.value)
            self.proxy.config['ngrok_authtoken'] = self.ngrok_token_field.value
            self.proxy.config['enable_ngrok'] = self.ngrok_switch.value
            self.proxy.config['label_size'] = self.label_size_dropdown.value
            self.proxy.config['ngrok_domain'] = self.ngrok_domain_field.value
            self.proxy.config['ngrok_reserved_domain_id'] = self.ngrok_reserved_domain_id_field.value
            self.proxy.config['secret_key'] = self.secret_key_field.value
            self.proxy.config['notion_api_key'] = self.notion_api_key_field.value
            self.proxy.config['notion_database_id'] = self.notion_database_id_field.value

            self.proxy.save_config()
            self.show_snackbar("設定を保存しました", ft.Colors.GREEN)
        except ValueError as e:
            self.show_snackbar("ポート番号は数値で入力してください", ft.Colors.RED)
        except Exception as e:
            self.show_snackbar(f"設定の保存に失敗しました: {str(e)}", ft.Colors.RED)
    
    def show_snackbar(self, message: str, color):
        """スナックバーを表示"""
        snack = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=color
        )
        self.page.snack_bar = snack
        self.page.snack_bar.open = True
        self.page.update()
    
    def create_tab(self) -> ft.Tab:
        """タブを作成"""
        return ft.Tab(
            text="設定",
            icon=ft.Icons.SETTINGS,
            content=ft.Container(
                padding=ft.padding.all(20),
                content=ft.Column([
                    ft.Card(
                        content=ft.Container(
                            padding=ft.padding.all(20),
                            content=ft.Column([
                                ft.Text("プリンター設定", size=18, weight=ft.FontWeight.BOLD),
                                ft.Divider(),
                                self.printer_ip_field,
                                self.printer_port_field,
                                self.label_size_dropdown
                            ])
                        )
                    ),
                    ft.Card(
                        content=ft.Container(
                            padding=ft.padding.all(20),
                            content=ft.Column([
                                ft.Text("プロキシ設定", size=18, weight=ft.FontWeight.BOLD),
                                ft.Divider(),
                                self.proxy_port_field,
                                self.secret_key_field,
                                self.ngrok_token_field,
                                self.ngrok_switch,
                                self.ngrok_domain_field,
                                self.ngrok_reserved_domain_id_field
                            ])
                        )
                    ),
                    ft.Card(
                        content=ft.Container(
                            padding=ft.padding.all(20),
                            content=ft.Column([
                                ft.Text("Notion設定", size=18, weight=ft.FontWeight.BOLD),
                                ft.Divider(),
                                self.notion_api_key_field,
                                self.notion_database_id_field
                            ])
                        )
                    ),
                    ft.Container(
                        padding=ft.padding.only(top=20),
                        content=self.save_btn
                    )
                ], scroll=ft.ScrollMode.AUTO)
            )
        )


def create_config_tab(proxy, page: ft.Page) -> tuple[ft.Tab, ConfigTab]:
    """設定タブを作成して返す"""
    config_tab = ConfigTab(proxy, page)
    return config_tab.create_tab(), config_tab