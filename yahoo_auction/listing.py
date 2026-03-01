"""
ヤフオク出品フォーム自動入力
"""

import time
from typing import Any, Callable, Dict, Optional

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .config import (
    CONDITION_MAPPING,
    DEFAULTS,
    PROPERTY_MAPPING,
    YAHOO_SELL_URL,
    WAIT_SHORT,
    WAIT_MEDIUM,
    WAIT_LONG,
)
from .image_handler import ImageHandler


class YahooAuctionListing:
    """ヤフオク出品フォームへの自動入力"""

    def __init__(self, driver: WebDriver):
        self.driver = driver
        self.wait = WebDriverWait(driver, 15)
        self.image_handler = ImageHandler(driver)
        self._on_progress: Optional[Callable] = None

    def fill_form(self, notion_data: Dict[str, Any], on_progress: Optional[Callable] = None):
        """Notionデータからフォームを自動入力

        Args:
            notion_data: Notionから取得したデータ
            on_progress: 進捗コールバック (step, message) -> None
        """
        self._on_progress = on_progress
        props = notion_data.get("properties", {})

        # 出品ページに遷移
        self._report("open", "出品フォームを開いています...")
        self.driver.get(YAHOO_SELL_URL)
        time.sleep(WAIT_LONG)

        # フリマ（定額）モードに切り替え
        self._select_sales_mode()

        # 各フィールドを入力
        self._fill_title(props)
        self._fill_condition(props)
        self._fill_description(props)
        self._fill_images(props)
        self._fill_price(props)
        self._fill_shipping(props)

        self._report("done", "自動入力が完了しました")
        print("\n" + "=" * 60)
        print("自動入力が完了しました")
        print("フォームの内容を確認し、必要に応じて修正してください")
        print("出品ボタンは手動で押してください")
        print("=" * 60)

    def _select_sales_mode(self):
        """フリマ（定額）モードに切り替え"""
        try:
            buynow = self.driver.find_element(By.ID, "salesmode_buynow")
            buynow.click()
            self._report("sales_mode", "販売形式: フリマ（定額）")
            time.sleep(WAIT_MEDIUM)
        except Exception as e:
            self._report("sales_mode", f"[エラー] 販売形式切り替え: {e}")

    def _fill_title(self, props: Dict[str, Any]):
        """タイトルを入力"""
        title = self._get_prop_value(props, "商品名")
        if not title:
            self._report("title", "[スキップ] タイトル: データなし")
            return

        # 65文字制限
        title = str(title)[:65]

        try:
            element = self._find_input_element([
                (By.NAME, "title"),
                (By.ID, "fleaTitleForm"),
                (By.CSS_SELECTOR, "input[name='title']"),
                (By.XPATH, "//input[contains(@placeholder, 'タイトル')]"),
                (By.XPATH, "//input[contains(@placeholder, '商品名')]"),
                (By.CSS_SELECTOR, "#Title input"),
            ])

            if element:
                element.clear()
                element.send_keys(title)
                self._report("title", f"タイトル: {title}")
            else:
                self._report("title", f"[要素未発見] タイトル: {title}")
        except Exception as e:
            self._report("title", f"[エラー] タイトル入力: {e}")

    def _fill_condition(self, props: Dict[str, Any]):
        """商品の状態を選択"""
        rank = self._get_prop_value(props, "ランク")
        condition = CONDITION_MAPPING.get(str(rank), DEFAULTS["condition_default"]) if rank else DEFAULTS["condition_default"]

        try:
            elements = self.driver.find_elements(By.XPATH, f"//*[contains(text(), '{condition}')]")
            if elements:
                elements[0].click()
                self._report("condition", f"商品の状態: {condition}")
                time.sleep(WAIT_SHORT)
            else:
                self._report("condition", f"[要素未発見] 商品の状態: {condition}")
        except Exception as e:
            self._report("condition", f"[エラー] 商品の状態: {e}")

    def _fill_description(self, props: Dict[str, Any]):
        """商品説明を入力（iframe内リッチテキストエディタ）"""
        # HTML説明文を優先、なければ通常説明文、なければ追加説明文
        description = self._get_prop_value(props, "説明文HTML")
        if not description or (isinstance(description, list) and not description):
            description = self._get_prop_value(props, "説明文")
        if not description or (isinstance(description, list) and not description):
            description = self._get_prop_value(props, "追加説明文")

        if isinstance(description, list):
            description = "\n".join(str(d) for d in description if d)

        if not description:
            self._report("description", "[スキップ] 商品説明: データなし")
            return

        try:
            # iframe内のリッチテキストエディタに入力
            iframe = self.driver.find_element(By.ID, "rteEditorComposition0")
            self.driver.switch_to.frame(iframe)

            body = self.driver.find_element(By.TAG_NAME, "body")
            body.click()
            body.send_keys(str(description))

            # メインフレームに戻る
            self.driver.switch_to.default_content()
            self._report("description", f"商品説明: {str(description)[:50]}...")
        except Exception as e:
            # iframeから戻れていない場合に備える
            try:
                self.driver.switch_to.default_content()
            except Exception:
                pass
            self._report("description", f"[エラー] 商品説明: {e}")

    def _fill_images(self, props: Dict[str, Any]):
        """画像をアップロード"""
        # 「画像」(rollup) を優先、なければ「個別画像」(files)
        images = self._get_prop_value(props, "画像")
        if not images:
            images = self._get_prop_value(props, "個別画像")
        if not images:
            self._report("images", "[スキップ] 画像: データなし")
            return

        try:
            self._report("images", "画像をダウンロード中...")
            paths = self.image_handler.download_from_notion(images)

            if paths:
                self._report("images", f"{len(paths)}枚の画像をアップロード中...")
                count = self.image_handler.upload_to_form(paths)
                self._report("images", f"画像アップロード完了: {count}枚")
            else:
                self._report("images", "[スキップ] ダウンロードできた画像なし")
        except Exception as e:
            self._report("images", f"[エラー] 画像処理: {e}")

    def _fill_price(self, props: Dict[str, Any]):
        """価格を入力"""
        price = self._get_prop_value(props, "売上金")
        if price is None:
            self._report("price", "[スキップ] 開始価格: データなし")
            return

        try:
            price_val = int(float(price))
        except (ValueError, TypeError):
            self._report("price", f"[スキップ] 開始価格: 数値変換エラー ({price})")
            return

        try:
            element = self._find_input_element([
                (By.ID, "auc_StartPrice"),
                (By.NAME, "StartPrice"),
                (By.CSS_SELECTOR, "input[name='StartPrice']"),
                (By.XPATH, "//input[contains(@placeholder, '開始価格')]"),
                (By.XPATH, "//input[contains(@placeholder, '価格')]"),
            ])

            if element:
                element.clear()
                element.send_keys(str(price_val))
                self._report("price", f"開始価格: {price_val:,}円")
            else:
                self._report("price", f"[要素未発見] 開始価格: {price_val:,}円")
        except Exception as e:
            self._report("price", f"[エラー] 価格入力: {e}")

    def _js_click(self, element):
        """JavaScript経由でクリック（element not interactable対策）"""
        self.driver.execute_script("arguments[0].click();", element)

    def _fill_shipping(self, props: Dict[str, Any]):
        """配送関連を設定"""
        shipping_payer = DEFAULTS["shipping_payer"]

        try:
            if shipping_payer == "seller":
                # ラベルまたはラジオボタンを探す
                elements = self.driver.find_elements(By.XPATH,
                    "//label[contains(text(), '出品者負担')] | //input[@value='seller']/parent::label")
                if not elements:
                    elements = self.driver.find_elements(By.XPATH, "//*[contains(text(), '出品者負担')]")
                if not elements:
                    elements = self.driver.find_elements(By.XPATH, "//*[contains(text(), '送料無料')]")
                if elements:
                    self._js_click(elements[0])
                    self._report("shipping", "送料負担: 出品者負担")
                    time.sleep(WAIT_SHORT)
                else:
                    self._report("shipping", "[要素未発見] 送料負担設定")
            else:
                elements = self.driver.find_elements(By.XPATH,
                    "//label[contains(text(), '落札者負担')] | //input[@value='buyer']/parent::label")
                if not elements:
                    elements = self.driver.find_elements(By.XPATH, "//*[contains(text(), '落札者負担')]")
                if elements:
                    self._js_click(elements[0])
                    self._report("shipping", "送料負担: 落札者負担")
                    time.sleep(WAIT_SHORT)
        except Exception as e:
            self._report("shipping", f"[エラー] 配送設定: {e}")

        # 発送元の地域
        region = DEFAULTS["shipping_region"]
        try:
            # select要素を探してJavaScriptで選択
            selects = self.driver.find_elements(By.XPATH,
                "//select[contains(@name, 'loc') or contains(@name, 'region') or contains(@name, 'pref')]")
            if selects:
                self.driver.execute_script(
                    f"var sel = arguments[0]; "
                    f"for(var i=0; i<sel.options.length; i++) {{ "
                    f"  if(sel.options[i].text.indexOf('{region}') >= 0) {{ "
                    f"    sel.selectedIndex = i; "
                    f"    sel.dispatchEvent(new Event('change')); break; "
                    f"  }} "
                    f"}}",
                    selects[0]
                )
                self._report("shipping", f"発送元: {region}")
            else:
                # option要素を直接クリック
                options = self.driver.find_elements(By.XPATH, f"//option[contains(text(), '{region}')]")
                if options:
                    self._js_click(options[0])
                    self._report("shipping", f"発送元: {region}")
        except Exception as e:
            self._report("shipping", f"[エラー] 発送元設定: {e}")

    def _find_input_element(self, selectors: list) -> Optional[Any]:
        """複数のセレクタを試行して要素を取得"""
        for by, selector in selectors:
            try:
                elements = self.driver.find_elements(by, selector)
                if elements:
                    return elements[0]
            except Exception:
                continue
        return None

    def _get_prop_value(self, props: Dict[str, Any], prop_name: str) -> Any:
        """プロパティから値を取得"""
        prop_info = props.get(prop_name)
        if prop_info:
            return prop_info.get("value")
        return None

    def _report(self, step: str, message: str):
        """進捗をコールバックに通知"""
        print(f"  {message}")
        if self._on_progress:
            self._on_progress(step, message)

    def cleanup(self):
        """一時ファイルを削除"""
        self.image_handler.cleanup()
