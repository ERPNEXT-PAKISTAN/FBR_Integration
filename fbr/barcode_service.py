import base64
from io import BytesIO

import qrcode
from barcode import Code128
from barcode.writer import ImageWriter


def make_qr_png_base64(text: str, box_size: int = 6, border: int = 2) -> str:
    """Return QR PNG as base64 string (without data:image prefix)."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(text)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def make_barcode_png_base64(text: str) -> str:
    """Return Code128 barcode PNG as base64 string (without data:image prefix)."""
    writer = ImageWriter()
    # Keep it readable
    options = {
        "module_height": 12.0,
        "module_width": 0.22,
        "quiet_zone": 3.0,
        "font_size": 12,
        "text_distance": 4,      # <-- more distance between bars and text
        "write_text": True,
        "dpi": 200
    }
    barcode_obj = Code128(text, writer=writer)
    buf = BytesIO()
    barcode_obj.write(buf, options=options)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def get_qr_and_barcode_data_urls(text: str) -> dict:
    """Return ready-to-use data URLs for frontend."""
    qr_b64 = make_qr_png_base64(text)
    bc_b64 = make_barcode_png_base64(text)

    return {
        "qr_data_url": f"data:image/png;base64,{qr_b64}",
        "barcode_data_url": f"data:image/png;base64,{bc_b64}",
        "value": text,
    }