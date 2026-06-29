"""
exam_token.qr_tracking
======================

Tạo nội dung QR tracking theo cấu trúc:

noi_dung
-> token_ma_hoa = AES-256-GCM(noi_dung, STUDENT_SECRET_KEY)
-> public_token = YYYY-MM-DD + token_ma_hoa + 10 ký tự nhiễu cuối
-> qr_link = https://qrdhcsnd.space/q.php?t=<public_token>

Quy tắc public_token bản v2:
    public_token = YYYY-MM-DD + token_ma_hoa + suffix_noise_10

Trong đó:
- 10 ký tự đầu là ngày in để quản lý lô in.
- 10 ký tự cuối là nhiễu.
- Hàm decode cũ vẫn hoạt động vì vẫn bỏ 10 ký tự đầu và 10 ký tự cuối
  để lấy token AES thật.
"""

from __future__ import annotations

import base64
import os
import re
import secrets
import string
from datetime import date, datetime
from urllib.parse import quote

from django.utils import timezone
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


TRACKING_DOMAIN = "https://qrdhcsnd.space"
TRACKING_PATH = "/q.php"
TRACKING_PARAM = "t"

NOISE_LEN = 10
NOISE_CHARS = string.ascii_letters + string.digits + "-_~"

_TRAILING_NUMBER_RE = re.compile(r"^(.*?)(\d+)$")


class QRTrackingError(Exception):
    """Lỗi chung khi tạo QR tracking."""


def load_student_secret_key(env_var: str = "STUDENT_SECRET_KEY") -> str:
    """
    Đọc STUDENT_SECRET_KEY từ môi trường.

    Key phải là Base64URL của 32 bytes, dùng cho AES-256-GCM.
    """
    key = os.environ.get(env_var, "").strip()

    if not key:
        raise QRTrackingError(
            f"Chưa cấu hình {env_var}. "
            f"Hãy thêm {env_var}=<key> vào file .env."
        )

    try:
        padding = "=" * (-len(key) % 4)
        key_bytes = base64.urlsafe_b64decode(key + padding)
    except Exception as exc:
        raise QRTrackingError(
            f"{env_var} không phải Base64URL hợp lệ."
        ) from exc

    if len(key_bytes) != 32:
        raise QRTrackingError(
            f"{env_var} phải là AES-256, tức 32 bytes sau khi decode. "
            f"Hiện tại decode được {len(key_bytes)} bytes."
        )

    return key


def encrypt_content(content: str, secret_key: str) -> str:
    """
    Mã hóa nội dung QR bằng AES-256-GCM.

    Input ví dụ:
        DHCSND_000001

    Output:
        token_ma_hoa dạng Base64URL, không có padding '='.
    """
    content = str(content or "").strip()

    if not content:
        raise QRTrackingError("Nội dung QR không được để trống.")

    try:
        padding = "=" * (-len(secret_key) % 4)
        key_bytes = base64.urlsafe_b64decode(secret_key + padding)
    except Exception as exc:
        raise QRTrackingError(
            "STUDENT_SECRET_KEY không hợp lệ, không decode được Base64URL."
        ) from exc

    if len(key_bytes) != 32:
        raise QRTrackingError(
            f"STUDENT_SECRET_KEY phải decode ra 32 bytes, hiện tại là {len(key_bytes)} bytes."
        )

    aesgcm = AESGCM(key_bytes)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, content.encode("utf-8"), None)

    token = base64.urlsafe_b64encode(nonce + ciphertext).decode("utf-8")
    return token.rstrip("=")


def make_noise(length: int = NOISE_LEN) -> str:
    """
    Tạo chuỗi nhiễu URL-safe.
    """
    return "".join(secrets.choice(NOISE_CHARS) for _ in range(length))


def format_print_date_prefix(print_date: date | datetime | str | None = None) -> str:
    """
    Trả về đúng 10 ký tự ngày in dạng YYYY-MM-DD.
    Không dùng timezone.localdate() hoặc timezone.localtime().
    """
    if print_date is None:
        return date.today().strftime("%Y-%m-%d")

    if isinstance(print_date, datetime):
        return print_date.date().strftime("%Y-%m-%d")

    if isinstance(print_date, date):
        return print_date.strftime("%Y-%m-%d")

    text = str(print_date or "").strip()

    if not text:
        return date.today().strftime("%Y-%m-%d")

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt).date().strftime("%d-%m-%Y")
        except ValueError:
            pass

    raise QRTrackingError(
        "Ngày in phải có dạng YYYY-MM-DD, DD/MM/YYYY hoặc YYYYMMDD."
    )

def add_print_date_to_token(
    encrypted_token: str,
    print_date_prefix: str,
    suffix: str,
) -> str:
    """
    Tạo public_token:

        public_token = YYYY-MM-DD + token_ma_hoa + suffix_noise_10
    """
    encrypted_token = str(encrypted_token or "").strip()
    print_date_prefix = str(print_date_prefix or "").strip()
    suffix = str(suffix or "").strip()

    if not encrypted_token:
        raise QRTrackingError("Token mã hóa không được để trống.")

    if len(print_date_prefix) != 10:
        raise QRTrackingError(
            "Prefix ngày in phải đúng 10 ký tự, ví dụ 2026-06-27."
        )

    if len(suffix) != NOISE_LEN:
        raise QRTrackingError(
            f"Suffix nhiễu cuối phải đúng {NOISE_LEN} ký tự."
        )

    return f"{print_date_prefix}{encrypted_token}{suffix}"


def build_tracking_link(public_token: str) -> str:
    """
    Tạo link QR:

        https://qrdhcsnd.space/q.php?t=<public_token>
    """
    public_token = str(public_token or "").strip()

    if not public_token:
        raise QRTrackingError("Public token không được để trống.")

    return (
        f"{TRACKING_DOMAIN}"
        f"{TRACKING_PATH}"
        f"?{TRACKING_PARAM}={quote(public_token, safe='')}"
    )


def split_text_and_number(start_text: str) -> tuple[str, int, int]:
    """
    Tách chuỗi bắt đầu thành phần chữ + số cuối.

    Ví dụ:
        DHCSND_000001 -> ("DHCSND_", 1, 6)
        ABC001        -> ("ABC", 1, 3)
    """
    start_text = str(start_text or "").strip()

    if not start_text:
        raise QRTrackingError("Nội dung bắt đầu không được để trống.")

    match = _TRAILING_NUMBER_RE.match(start_text)

    if not match:
        raise QRTrackingError(
            "Nội dung bắt đầu phải kết thúc bằng số thứ tự. "
            "Ví dụ hợp lệ: DHCSND_000001, ABC001, PHIEU-000001."
        )

    prefix, number_text = match.groups()
    return prefix, int(number_text), len(number_text)


def generate_sequence(start_text: str, quantity: int) -> list[str]:
    """
    Sinh danh sách nội dung tăng dần từ chuỗi bắt đầu.

    Ví dụ:
        start_text = DHCSND_000001
        quantity = 3

    Kết quả:
        DHCSND_000001
        DHCSND_000002
        DHCSND_000003
    """
    try:
        quantity = int(quantity)
    except (TypeError, ValueError) as exc:
        raise QRTrackingError("Số lượng QR phải là số nguyên dương.") from exc

    if quantity <= 0:
        raise QRTrackingError("Số lượng QR phải lớn hơn 0.")

    prefix, start_number, width = split_text_and_number(start_text)

    return [
        f"{prefix}{number:0{width}d}"
        for number in range(start_number, start_number + quantity)
    ]


def build_qr_items(
    start_text: str,
    quantity: int,
    secret_key: str | None = None,
    print_date: date | datetime | str | None = None,
) -> list[dict]:
    """
    Tạo danh sách QR theo lô in.

    Trả về list dict gồm:
        noi_dung
        token_ma_hoa
        public_token
        qr_link
        ngay_in_prefix

    Cấu trúc:
        public_token = YYYY-MM-DD + token_ma_hoa + suffix_noise_10

    Quy tắc suffix:
        Cứ mỗi 10 mã QR đổi 1 suffix mới.
    """
    secret_key = secret_key or load_student_secret_key()
    contents = generate_sequence(start_text, quantity)
    print_date_prefix = format_print_date_prefix(print_date)

    items: list[dict] = []
    current_suffix = ""

    for idx, content in enumerate(contents):
        token_ma_hoa = encrypt_content(content, secret_key)

        if idx % 10 == 0:
            current_suffix = make_noise(NOISE_LEN)

        public_token = add_print_date_to_token(
            encrypted_token=token_ma_hoa,
            print_date_prefix=print_date_prefix,
            suffix=current_suffix,
        )

        qr_link = build_tracking_link(public_token)

        items.append({
            "stt": idx + 1,
            "noi_dung": content,
            "token_ma_hoa": token_ma_hoa,
            "public_token": public_token,
            "qr_link": qr_link,
            "ngay_in_prefix": print_date_prefix,
        })

    return items


def extract_encrypted_token_from_public_token(public_token: str) -> str:
    """
    Hàm tiện ích để kiểm tra lại:
    public_token -> bỏ 10 ký tự đầu và 10 ký tự cuối -> token AES thật.
    """
    public_token = str(public_token or "").strip()

    if len(public_token) <= NOISE_LEN * 2:
        raise QRTrackingError(
            "Public token quá ngắn, không đủ để bỏ ngày in và nhiễu cuối."
        )

    return public_token[NOISE_LEN:-NOISE_LEN]


def extract_public_token_from_qr(qr_value: str) -> str:
    """
    Nếu QR là link tracking thì lấy tham số t.
    Nếu QR là token thuần thì trả về nguyên chuỗi.
    """
    from urllib.parse import urlparse, parse_qs

    qr_value = str(qr_value or "").strip()

    if qr_value.startswith("http://") or qr_value.startswith("https://"):
        parsed = urlparse(qr_value)
        qs = parse_qs(parsed.query)
        return qs.get(TRACKING_PARAM, [""])[0].strip()

    return qr_value