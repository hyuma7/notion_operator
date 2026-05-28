"""
A4縦 請求書（上部）+ 領収証（下部）PDF生成

reportlab座標系メモ:
  - y=0 はページ下端、y増加で上方向
  - drawString(x, y, text) : yはテキストのベースライン
  - rect(x, y, w, h)       : yはボックスの底辺（左下コーナー）
"""

from __future__ import annotations

import glob
import os
from collections.abc import Mapping, Sequence

COMPANY_NAME = "株式会社 アーネスト"
COMPANY_REP = "代表取締役　齊藤 淳"
COMPANY_ADDRESS = "〒225-0025 神奈川県横浜市青葉区鉄町25-8"
COMPANY_TEL = "TEL：045-507-6784　FAX：045-507-6804"
STAMP_LINES = ["株式会社", "アーネスト", "代表取締役", "齊藤 淳"]

MAX_INVOICE_ROWS_PER_PAGE = 20

_JA_FONT_REGISTERED = False
_JA_FONT_NAME = "JaFont"


def _ensure_ja_font():
    global _JA_FONT_REGISTERED, _JA_FONT_NAME
    if _JA_FONT_REGISTERED:
        return

    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    candidates = [
        # Windows
        "C:/Windows/Fonts/YuGothR.ttc",
        "C:/Windows/Fonts/msgothic.ttc",
        "C:/Windows/Fonts/meiryo.ttc",
        # Linux (Noto CJK – fonts-noto-cjk パッケージ)
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Regular.ttc",
        # Linux (IPA Gothic – fonts-ipafont-gothic パッケージ)
        "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",
        "/usr/share/fonts/opentype/ipafont-gothic/ipagp.ttf",
        # Linux (Takao – fonts-takao-gothic パッケージ)
        "/usr/share/fonts/truetype/takao-gothic/TakaoGothic.ttf",
    ]
    # インストール場所がバージョンにより異なるためglobで補完
    candidates += glob.glob("/usr/share/fonts/**/Noto*CJK*Regular*.ttc", recursive=True)
    candidates += glob.glob("/usr/share/fonts/**/Noto*CJK*Regular*.otf", recursive=True)
    candidates += glob.glob("/usr/share/fonts/**/ipag*.ttf", recursive=True)

    for font_path in candidates:
        if not os.path.exists(font_path):
            continue
        for kwargs in [{"subfontIndex": 0}, {}]:
            try:
                pdfmetrics.registerFont(TTFont("JaFont", font_path, **kwargs))
                _JA_FONT_REGISTERED = True
                _JA_FONT_NAME = "JaFont"
                return
            except Exception:
                continue

    # フォールバック: ReportLab組み込みCIDフォント（インストール不要・日本語対応）
    try:
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
        _JA_FONT_REGISTERED = True
        _JA_FONT_NAME = "HeiseiKakuGo-W5"
        return
    except Exception:
        pass

    raise RuntimeError(
        "日本語フォントの登録に失敗しました。"
        "Windows: Yu Gothic / MS Gothic / Meiryo のいずれか、"
        "Linux: apt install fonts-noto-cjk が必要です。"
    )


def default_issuer_info() -> dict[str, object]:
    return {
        "company_name": COMPANY_NAME,
        "representative": COMPANY_REP,
        "address": COMPANY_ADDRESS,
        "tel": COMPANY_TEL,
        "invoice_number": "",
        "stamp_lines": STAMP_LINES.copy(),
        "stamp_image_path": "",
    }


def issuer_info_from_config(config: Mapping | None) -> dict[str, object]:
    """proxy.config から請求書・領収証の発行者情報を取り出す。"""
    issuer = default_issuer_info()
    if not config:
        return issuer

    key_map = {
        "issuer_company_name": "company_name",
        "issuer_representative": "representative",
        "issuer_address": "address",
        "issuer_tel": "tel",
        "issuer_invoice_number": "invoice_number",
        "issuer_stamp_image_path": "stamp_image_path",
    }
    for config_key, issuer_key in key_map.items():
        if config_key in config:
            value = config.get(config_key)
            issuer[issuer_key] = "" if value is None else str(value).replace("\n", " ").strip()

    if "issuer_stamp_lines" in config:
        stamp_lines = config.get("issuer_stamp_lines")
        if isinstance(stamp_lines, str):
            lines = [line.strip() for line in stamp_lines.splitlines() if line.strip()]
        elif isinstance(stamp_lines, Sequence):
            lines = [str(line).strip() for line in stamp_lines if str(line).strip()]
        else:
            lines = []
        issuer["stamp_lines"] = lines

    return issuer


def _normalize_issuer(issuer: Mapping | None) -> dict[str, object]:
    result = default_issuer_info()
    if not issuer:
        return result

    for key in ["company_name", "representative", "address", "tel", "invoice_number", "stamp_image_path"]:
        if key in issuer:
            value = issuer.get(key)
            result[key] = "" if value is None else str(value).replace("\n", " ").strip()

    if "stamp_lines" in issuer:
        stamp_lines = issuer.get("stamp_lines")
        if isinstance(stamp_lines, str):
            lines = [line.strip() for line in stamp_lines.splitlines() if line.strip()]
        elif isinstance(stamp_lines, Sequence):
            lines = [str(line).strip() for line in stamp_lines if str(line).strip()]
        else:
            lines = []
        result["stamp_lines"] = lines

    return result


def _chunks(items: list[tuple[str, str, int]], size: int) -> list[list[tuple[str, str, int]]]:
    if not items:
        return [[]]
    return [items[i:i + size] for i in range(0, len(items), size)]


def _fit_text(c, text: object, font_name: str, font_size: float, max_width: float) -> str:
    value = "" if text is None else str(text)
    if c.stringWidth(value, font_name, font_size) <= max_width:
        return value

    ellipsis = "..."
    if c.stringWidth(ellipsis, font_name, font_size) > max_width:
        return ""

    lo = 0
    hi = len(value)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        candidate = value[:mid] + ellipsis
        if c.stringWidth(candidate, font_name, font_size) <= max_width:
            lo = mid
        else:
            hi = mid - 1
    return value[:lo] + ellipsis


def _draw_fit(c, text: object, x: float, y: float, max_width: float, *, align: str = "left",
              font_name: str | None = None, font_size: float = 8):
    fn = font_name if font_name is not None else _JA_FONT_NAME
    c.setFont(fn, font_size)
    fitted = _fit_text(c, text, fn, font_size, max_width)
    if align == "right":
        c.drawRightString(x + max_width, y, fitted)
    elif align == "center":
        c.drawCentredString(x + max_width / 2, y, fitted)
    else:
        c.drawString(x, y, fitted)


def _currency(value: int) -> str:
    return f"¥{value:,}"


def _draw_issuer_lines(c, lines: list[str], right_x: float, y: float, line_gap: float,
                       max_width: float, font_size: float):
    left_x = right_x - max_width
    for line in lines:
        _draw_fit(c, line, left_x, y, max_width, align="right", font_size=font_size)
        y -= line_gap


def _draw_cut_line(c, mg: float, width: float, div_y: float):
    c.setLineWidth(0.6)
    c.setDash([4, 3])
    c.line(mg, div_y, width - mg, div_y)
    c.setDash([])


def _draw_invoice_section(
    c,
    *,
    width: float,
    height: float,
    mg: float,
    inv_top: float,
    inv_limit: float,
    chunk: list[tuple[str, str, int]],
    row_offset: int,
    page_no: int,
    page_count: int,
    issue_date: str,
    recipient: str,
    issuer: Mapping,
    invoice_number: str,
    subtotal: int,
    tax: int,
    total: int,
    show_totals: bool,
):
    from reportlab.lib import colors

    c.setFont(_JA_FONT_NAME, 20)
    title = "請　求　書" if page_no == 1 else "請　求　書（続き）"
    c.drawCentredString(width / 2, inv_top - 22, title)

    issuer_lines = [
        str(issuer.get("company_name", "")),
        str(issuer.get("address", "")),
        str(issuer.get("tel", "")),
    ]
    if invoice_number:
        issuer_lines.append(f"登録番号：{invoice_number}")
    _draw_issuer_lines(c, issuer_lines, width - mg, inv_top - 10, 12, 255, 8.5)

    issue_y = inv_top - (62 if invoice_number else 50)
    _draw_fit(c, f"発行日：{issue_date}", width - mg - 150, issue_y, 150, align="right", font_size=8)
    if page_count > 1:
        _draw_fit(c, f"{page_no}/{page_count}ページ", width - mg - 150, issue_y - 14, 150, align="right", font_size=8)

    recip_y = inv_top - 62
    recip_text = f"{recipient}　御中" if recipient else "　　　　　　　　　　　　　御中"
    _draw_fit(c, recip_text, mg, recip_y, 230, font_size=12)
    c.setLineWidth(0.5)
    c.line(mg, recip_y - 4, mg + 230, recip_y - 4)

    amt_box_h = 24
    amt_box_y = recip_y - 4 - 16 - amt_box_h
    amt_box_x = mg + 70
    amt_box_w = 190

    c.setFont(_JA_FONT_NAME, 9)
    c.drawString(mg, amt_box_y + amt_box_h / 2 - 3, "ご請求金額")
    c.setLineWidth(1.0)
    c.rect(amt_box_x, amt_box_y, amt_box_w, amt_box_h)
    _draw_fit(c, f"¥ {total:,}", amt_box_x + 4, amt_box_y + 6, amt_box_w - 8, align="right", font_size=14)
    c.setFont(_JA_FONT_NAME, 10)
    c.drawString(amt_box_x + amt_box_w + 4, amt_box_y + 6, "円")

    tbl_top = amt_box_y - 14
    tbl_x = mg
    tbl_w = width - 2 * mg

    fixed_w = 22 + 200 + 30 + 80 + 40
    col_widths = [22, 200, 30, 80, 40, int(tbl_w - fixed_w)]
    col_headers = ["連番", "品名", "数量", "金額", "税率", "備考"]
    col_aligns = ["center", "left", "center", "right", "center", "left"]

    col_xs = [tbl_x]
    for col_w in col_widths[:-1]:
        col_xs.append(col_xs[-1] + col_w)

    hdr_h = 16
    num_rows = MAX_INVOICE_ROWS_PER_PAGE
    tot_reserved = 45
    avail_h = tbl_top - inv_limit
    row_h = min(16.0, max(10.0, (avail_h - hdr_h - tot_reserved) / num_rows))

    c.setFillColor(colors.Color(0.82, 0.82, 0.82))
    c.rect(tbl_x, tbl_top - hdr_h, tbl_w, hdr_h, fill=1, stroke=0)
    c.setFillColor(colors.black)

    for hdr, cx, cw in zip(col_headers, col_xs, col_widths):
        _draw_fit(c, hdr, cx, tbl_top - hdr_h + 4, cw, align="center", font_size=8)

    c.setLineWidth(0.5)
    c.line(tbl_x, tbl_top, tbl_x + tbl_w, tbl_top)
    c.line(tbl_x, tbl_top - hdr_h, tbl_x + tbl_w, tbl_top - hdr_h)
    for cx in col_xs:
        c.line(cx, tbl_top, cx, tbl_top - hdr_h)
    c.line(tbl_x + tbl_w, tbl_top, tbl_x + tbl_w, tbl_top - hdr_h)

    for i in range(num_rows):
        row_y = tbl_top - hdr_h - (i + 1) * row_h
        if i < len(chunk):
            name, model, amount = chunk[i]
            cells = [
                str(row_offset + i + 1),
                name,
                "1",
                _currency(amount) if amount else "",
                "10%" if amount else "",
                model,
            ]
        else:
            cells = ["", "", "", "", "", ""]

        text_y = row_y + row_h / 2 - 3
        for text, cx, cw, align in zip(cells, col_xs, col_widths, col_aligns):
            _draw_fit(c, text, cx + 3, text_y, cw - 6, align=align, font_size=7.5)
        c.line(tbl_x, row_y, tbl_x + tbl_w, row_y)

    data_bottom = tbl_top - hdr_h - num_rows * row_h
    for cx in col_xs:
        c.line(cx, tbl_top - hdr_h, cx, data_bottom)
    c.line(tbl_x + tbl_w, tbl_top - hdr_h, tbl_x + tbl_w, data_bottom)

    tot_x = col_xs[3]
    tot_w = tbl_x + tbl_w - tot_x
    tot_y = data_bottom - 3

    if show_totals:
        for label, val, bold in [
            ("小計", subtotal, False),
            ("消費税（10%）", tax, False),
            ("合　計", total, True),
        ]:
            tot_y -= 14
            c.setFont(_JA_FONT_NAME, 9 if bold else 8)
            c.drawString(tot_x + 4, tot_y + 4, label)
            _draw_fit(c, _currency(val), tot_x + 4, tot_y + 4, tot_w - 8, align="right", font_size=9 if bold else 8)
            c.setLineWidth(0.5 if bold else 0.4)
            c.line(tot_x, tot_y, tot_x + tot_w, tot_y)
            c.line(tot_x, tot_y + 14, tot_x, tot_y)
            c.line(tot_x + tot_w, tot_y + 14, tot_x + tot_w, tot_y)
    else:
        _draw_fit(c, "次ページへ続く", tot_x, tot_y - 18, tot_w, align="right", font_size=9)


def _draw_receipt_section(
    c,
    *,
    width: float,
    mg: float,
    rcpt_top: float,
    issue_date: str,
    recipient: str,
    issuer: Mapping,
    invoice_number: str,
    total: int,
    receipt_note: str,
):
    from reportlab.lib import colors
    from reportlab.lib.utils import ImageReader

    c.setFont(_JA_FONT_NAME, 20)
    c.drawCentredString(width / 2, rcpt_top - 22, "領　収　証")

    rname_y = rcpt_top - 50
    rname_text = f"{recipient}　　様" if recipient else "　　　　　　　　　　　　　　　様"
    _draw_fit(c, rname_text, mg, rname_y, 250, font_size=11)
    c.setLineWidth(0.5)
    c.line(mg, rname_y - 4, mg + 250, rname_y - 4)

    c.setFont(_JA_FONT_NAME, 15)
    c.drawString(mg, rcpt_top - 74, f"金　¥ {total:,} -")

    note_text = receipt_note.strip() if receipt_note else "上記金額正に領収いたしました"
    _draw_fit(c, f"但し　{note_text}", mg, rcpt_top - 96, 285, font_size=9)
    c.setFont(_JA_FONT_NAME, 9)
    c.drawString(mg, rcpt_top - 112, f"{issue_date}　受領")

    issuer_lines = [
        str(issuer.get("company_name", "")),
        str(issuer.get("representative", "")),
        str(issuer.get("address", "")),
        str(issuer.get("tel", "")),
    ]
    if invoice_number:
        issuer_lines.append(f"登録番号：{invoice_number}")
    _draw_issuer_lines(c, issuer_lines, width - mg, rcpt_top - 52, 13, 265, 8.5)

    hanko_cx = mg + 58
    hanko_cy = rcpt_top - 88
    hanko_r = 36
    stamp_image_path = str(issuer.get("stamp_image_path", "") or "")

    c.saveState()
    try:
        if stamp_image_path and os.path.exists(stamp_image_path):
            c.setFillAlpha(0.45)
            image = ImageReader(stamp_image_path)
            c.drawImage(
                image,
                hanko_cx - hanko_r,
                hanko_cy - hanko_r,
                width=hanko_r * 2,
                height=hanko_r * 2,
                preserveAspectRatio=True,
                mask="auto",
            )
        else:
            stamp_color = colors.Color(0.70, 0.0, 0.0, alpha=0.35)
            c.setStrokeColor(stamp_color)
            c.setFillColor(stamp_color)
            c.setLineWidth(1.8)
            c.circle(hanko_cx, hanko_cy, hanko_r, fill=0, stroke=1)
            c.circle(hanko_cx, hanko_cy, hanko_r - 4, fill=0, stroke=1)

            stamp_lines = issuer.get("stamp_lines") or []
            if not stamp_lines:
                stamp_lines = STAMP_LINES
            stamp_lines = list(stamp_lines)[:5]
            line_gap = 9 if len(stamp_lines) >= 5 else 10
            start_y = hanko_cy + ((len(stamp_lines) - 1) * line_gap) / 2 - 3
            for i, text in enumerate(stamp_lines):
                _draw_fit(
                    c,
                    text,
                    hanko_cx - hanko_r + 6,
                    start_y - i * line_gap,
                    hanko_r * 2 - 12,
                    align="center",
                    font_size=7,
                )
    finally:
        c.restoreState()


def _draw_blank_receipt_area(c, *, width: float, mg: float, rcpt_top: float):
    c.setFont(_JA_FONT_NAME, 10)
    c.drawCentredString(width / 2, rcpt_top - 82, "明細は次ページへ続きます")


def generate_invoice_receipt_pdf(
    path,
    items: list[tuple[str, str, int]],
    issue_date: str,
    recipient: str = "",
    issuer: Mapping | None = None,
    receipt_note: str = "上記金額正に領収いたしました",
    invoice_number: str = "",
):
    """
    A4縦 請求書（上部）+ 領収証（下部）のPDFを生成する。

    path         : 保存先パス（str）またはファイルオブジェクト（BytesIO等）
    items        : [(品名, 型番/備考, 金額), ...]
    issue_date   : 発行日文字列（例: 2026年5月22日）
    recipient    : 宛先名（空の場合は空欄）
    issuer       : 発行者情報（未指定時は既定値）
    receipt_note : 領収証の但し書き
    invoice_number : インボイス登録番号（空の場合は issuer から取得）
    """
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4

    _ensure_ja_font()

    width, height = A4
    mg = 42

    subtotal = sum(a for _, _, a in items)
    tax = int(subtotal * 0.1)
    total = subtotal + tax
    issuer_info = _normalize_issuer(issuer)
    recipient = recipient.strip()
    invoice_number = (invoice_number or str(issuer_info.get("invoice_number", ""))).strip()

    c = canvas.Canvas(path, pagesize=A4)
    c.setTitle("請求書・領収証")

    inv_top = height - mg
    div_y = 355
    div_gap = 22
    inv_limit = div_y + div_gap
    rcpt_top = div_y - div_gap

    pages = _chunks(items, MAX_INVOICE_ROWS_PER_PAGE)
    page_count = len(pages)

    for page_index, chunk in enumerate(pages):
        page_no = page_index + 1
        is_last_page = page_no == page_count

        _draw_cut_line(c, mg, width, div_y)
        _draw_invoice_section(
            c,
            width=width,
            height=height,
            mg=mg,
            inv_top=inv_top,
            inv_limit=inv_limit,
            chunk=chunk,
            row_offset=page_index * MAX_INVOICE_ROWS_PER_PAGE,
            page_no=page_no,
            page_count=page_count,
            issue_date=issue_date,
            recipient=recipient,
            issuer=issuer_info,
            invoice_number=invoice_number,
            subtotal=subtotal,
            tax=tax,
            total=total,
            show_totals=is_last_page,
        )

        if is_last_page:
            _draw_receipt_section(
                c,
                width=width,
                mg=mg,
                rcpt_top=rcpt_top,
                issue_date=issue_date,
                recipient=recipient,
                issuer=issuer_info,
                invoice_number=invoice_number,
                total=total,
                receipt_note=receipt_note,
            )
        else:
            _draw_blank_receipt_area(c, width=width, mg=mg, rcpt_top=rcpt_top)
            c.showPage()

    c.save()
