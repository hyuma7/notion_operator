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
        
        self.label_size_dropdown = ft.Dropdown(
            label="ラベルサイズ",
            width=300,
            options=[
                ft.dropdown.Option("62x29"),
                ft.dropdown.Option("62x100"),
            ],
            value=proxy.config.get('label_size', '62x29')
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

        self.vercel_base_url_field = ft.TextField(
            label="Vercel URL（商品管理Webアプリ）",
            hint_text="例: https://your-app.vercel.app",
            value=proxy.config.get('vercel_base_url', ''),
            width=300
        )

        stamp_lines = proxy.config.get('issuer_stamp_lines', [])
        if isinstance(stamp_lines, str):
            stamp_text = stamp_lines
        else:
            stamp_text = "\n".join(str(line) for line in stamp_lines)

        self.issuer_company_name_field = ft.TextField(
            label="発行者名（会社名）",
            value=proxy.config.get('issuer_company_name', ''),
            width=420,
            dense=True,
        )

        self.issuer_representative_field = ft.TextField(
            label="代表者・担当者名",
            value=proxy.config.get('issuer_representative', ''),
            width=420,
            dense=True,
        )

        self.issuer_address_field = ft.TextField(
            label="住所",
            value=proxy.config.get('issuer_address', ''),
            width=520,
            dense=True,
            multiline=True,
            min_lines=1,
            max_lines=2,
        )

        self.issuer_tel_field = ft.TextField(
            label="電話・FAX",
            value=proxy.config.get('issuer_tel', ''),
            width=420,
            dense=True,
        )

        self.issuer_invoice_number_field = ft.TextField(
            label="インボイス番号",
            hint_text="例: T1234567890123",
            value=proxy.config.get('issuer_invoice_number', ''),
            width=300,
            dense=True,
        )

        self.issuer_stamp_lines_field = ft.TextField(
            label="印影の文字（1行ずつ）",
            value=stamp_text,
            width=300,
            dense=True,
            multiline=True,
            min_lines=4,
            max_lines=4,
        )

        self.issuer_stamp_image_path_field = ft.TextField(
            label="印影画像パス（任意）",
            value=proxy.config.get('issuer_stamp_image_path', ''),
            width=520,
            dense=True,
            hint_text="例: C:\\stamps\\inkan.png",
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
            self.proxy.config['label_size'] = self.label_size_dropdown.value
            self.proxy.config['notion_api_key'] = self.notion_api_key_field.value
            self.proxy.config['notion_database_id'] = self.notion_database_id_field.value
            self.proxy.config['vercel_base_url'] = self.vercel_base_url_field.value.rstrip('/')
            self.proxy.config['issuer_company_name'] = (self.issuer_company_name_field.value or "").strip()
            self.proxy.config['issuer_representative'] = (self.issuer_representative_field.value or "").strip()
            self.proxy.config['issuer_address'] = (self.issuer_address_field.value or "").strip()
            self.proxy.config['issuer_tel'] = (self.issuer_tel_field.value or "").strip()
            self.proxy.config['issuer_invoice_number'] = (
                self.issuer_invoice_number_field.value or ""
            ).strip()
            self.proxy.config['issuer_stamp_lines'] = [
                line.strip()
                for line in (self.issuer_stamp_lines_field.value or "").splitlines()
                if line.strip()
            ]
            self.proxy.config['issuer_stamp_image_path'] = (
                self.issuer_stamp_image_path_field.value or ""
            ).strip()

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
                                ft.Text("Notion設定", size=18, weight=ft.FontWeight.BOLD),
                                ft.Divider(),
                                self.notion_api_key_field,
                                self.notion_database_id_field,
                                ft.Divider(height=4),
                                ft.Text("Webアプリ設定", size=14, weight=ft.FontWeight.BOLD,
                                        color=ft.Colors.BLUE_GREY_600),
                                self.vercel_base_url_field,
                                ft.Text(
                                    "設定するとQRコードがVercel URLになります（未設定はNotionページURL）",
                                    size=11, color=ft.Colors.GREY_500,
                                ),
                            ])
                        )
                    ),
                    ft.Card(
                        content=ft.Container(
                            padding=ft.padding.all(20),
                            content=ft.Column([
                                ft.Text("請求書・領収証の発行者", size=18, weight=ft.FontWeight.BOLD),
                                ft.Divider(),
                                self.issuer_company_name_field,
                                self.issuer_representative_field,
                                self.issuer_address_field,
                                self.issuer_tel_field,
                                self.issuer_invoice_number_field,
                                ft.Divider(height=4),
                                self.issuer_stamp_lines_field,
                                self.issuer_stamp_image_path_field,
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
