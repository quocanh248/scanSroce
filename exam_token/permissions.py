from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect, render
from django.db.models import Q

from .constants import ROLE_ADMIN, ROLE_MANAGER, ROLE_MARKER, ROLE_PROCTOR, ROLE_VIEWER


# Các role bổ sung dùng cho quy trình chấm thi hai giám khảo
ROLE_GK1 = "giam_khao_1"
ROLE_GK2 = "giam_khao_2"
ROLE_CHAIRMAN = "truong_hoi_dong"
ROLE_SCORE_BOARD = "can_bo_cham_diem"


ROLE_HIERARCHY = {
    ROLE_ADMIN: {
        ROLE_ADMIN,
        ROLE_MANAGER,
        ROLE_PROCTOR,
        ROLE_MARKER,
        ROLE_VIEWER,
        ROLE_GK1,
        ROLE_GK2,
        ROLE_CHAIRMAN,
        ROLE_SCORE_BOARD,
    },
    ROLE_MANAGER: {
        ROLE_MANAGER,
        ROLE_PROCTOR,
        ROLE_MARKER,
        ROLE_VIEWER,
        ROLE_GK1,
        ROLE_GK2,
        ROLE_CHAIRMAN,
        ROLE_SCORE_BOARD,
    },
    ROLE_PROCTOR: {ROLE_PROCTOR, ROLE_VIEWER},
    ROLE_MARKER: {ROLE_MARKER, ROLE_VIEWER, ROLE_SCORE_BOARD},
    ROLE_VIEWER: {ROLE_VIEWER},
    ROLE_GK1: {ROLE_GK1},
    ROLE_GK2: {ROLE_GK2},
    ROLE_CHAIRMAN: {ROLE_CHAIRMAN, ROLE_SCORE_BOARD},
    ROLE_SCORE_BOARD: {ROLE_SCORE_BOARD},
}


def _raw_user_roles(user):
    """
    Lấy role gốc của user từ 2 nguồn:
    1. Django Group
    2. bảng can_bo.vai_tro nếu user có hồ sơ cán bộ

    Không redirect trong hàm này để tránh vòng lặp đăng nhập.
    """
    if not user or not user.is_authenticated:
        return set()

    roles = set(user.groups.values_list("name", flat=True))

    try:
        can_bo = user.can_bo
    except Exception:
        can_bo = None

    if can_bo:
        vai_tro = getattr(can_bo, "vai_tro", None)
        if vai_tro:
            roles.add(vai_tro)

    return roles


def user_roles(user):
    """
    Trả về toàn bộ role đã mở rộng theo phân cấp.
    Superuser luôn có mọi quyền.
    """
    if not user or not user.is_authenticated:
        return set()

    if user.is_superuser:
        return {
            ROLE_ADMIN,
            ROLE_MANAGER,
            ROLE_PROCTOR,
            ROLE_MARKER,
            ROLE_VIEWER,
            ROLE_GK1,
            ROLE_GK2,
            ROLE_CHAIRMAN,
            ROLE_SCORE_BOARD,
        }

    expanded = set()
    for role in _raw_user_roles(user):
        expanded |= ROLE_HIERARCHY.get(role, {role})

    return expanded


def has_any_role(user, *roles):
    if not roles:
        return True

    return bool(user_roles(user) & set(roles))


def user_has_any_group(user, group_names):
    """
    Giữ tên hàm cũ để các view cũ vẫn chạy.
    Thực tế hàm này kiểm tra cả Group và can_bo.vai_tro.
    """
    if isinstance(group_names, str):
        group_names = [group_names]

    return has_any_role(user, *group_names)


def role_required(*allowed_roles):
    """
    Decorator phân quyền an toàn:
    - Chưa đăng nhập: redirect về login.
    - Đăng nhập nhưng không đủ quyền: trả 403, KHÔNG redirect dashboard.
    - Superuser: luôn được phép.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user = request.user

            if not user.is_authenticated:
                return redirect("login")

            if has_any_role(user, *allowed_roles):
                return view_func(request, *args, **kwargs)

            return render(request, "exam_token/permission_denied.html", status=403)

        return wrapper

    return decorator


def require_groups(request, group_names, message="Bạn không có quyền truy cập chức năng này."):
    """
    Hàm tương thích với code cũ.
    Trả None nếu có quyền.
    Trả response 403 nếu không có quyền.
    Tuyệt đối không redirect dashboard để tránh ERR_TOO_MANY_REDIRECTS.
    """
    if user_has_any_group(request.user, group_names):
        return None

    messages.error(request, message)
    return render(request, "exam_token/permission_denied.html", status=403)


# Decorator dùng trong views.py
can_manage_users = role_required(ROLE_ADMIN)
can_manage_exam = role_required(ROLE_ADMIN, ROLE_MANAGER, ROLE_PROCTOR)
can_manage_qr = role_required(ROLE_ADMIN, ROLE_MANAGER)
can_mark_exam = role_required(ROLE_ADMIN, ROLE_MANAGER, ROLE_MARKER, ROLE_GK1, ROLE_GK2)
can_import_students = role_required(ROLE_ADMIN, ROLE_MANAGER)
can_view_dashboard = role_required(ROLE_ADMIN, ROLE_MANAGER, ROLE_PROCTOR, ROLE_MARKER, ROLE_VIEWER)


def is_admin_or_quan_ly_thi(user):
    """
    Admin hoặc quản lý thi được xem toàn bộ dữ liệu.
    """
    return has_any_role(user, ROLE_ADMIN, ROLE_MANAGER)


def filter_visible_phien_thi(queryset, user):
    """
    Lọc dữ liệu phiên thi theo quyền:
    - admin, quan_ly_thi: xem toàn bộ
    - user khác: chỉ xem phiên chưa hoàn thành
    """
    if is_admin_or_quan_ly_thi(user):
        return queryset

    return queryset.exclude(
        Q(trang_thai="hoan_thanh") | Q(finished_at__isnull=False)
    )


def can_view_phien_thi(user, phien_thi):
    """
    Dùng để chặn truy cập trực tiếp vào phiên thi đã hoàn thành.
    """
    if is_admin_or_quan_ly_thi(user):
        return True

    if phien_thi.trang_thai == "hoan_thanh" or phien_thi.finished_at:
        return False

    return True


def can_mark_gk1(user):
    return has_any_role(user, ROLE_ADMIN, ROLE_MANAGER, ROLE_GK1)


def can_mark_gk2(user):
    return has_any_role(user, ROLE_ADMIN, ROLE_MANAGER, ROLE_GK2)


def can_view_score_board(user):
    return has_any_role(user, ROLE_ADMIN, ROLE_MANAGER, ROLE_CHAIRMAN, ROLE_SCORE_BOARD)


def can_chairman(user):
    return has_any_role(user, ROLE_ADMIN, ROLE_MANAGER, ROLE_CHAIRMAN)


def home_url_name_for_user(user):
    """
    Trả về URL name phù hợp sau đăng nhập.
    Không trả về login cho user đã đăng nhập, để tránh loop ở login_view.
    """
    if not user or not user.is_authenticated:
        return "login"

    roles = user_roles(user)

    if roles & {ROLE_ADMIN, ROLE_MANAGER}:
        return "dashboard"

    if ROLE_GK1 in roles:
        return "cham_diem_gk1"

    if ROLE_GK2 in roles:
        return "cham_diem_gk2"

    if ROLE_CHAIRMAN in roles:
        return "cham_diem_truong_hoi_dong"

    if ROLE_SCORE_BOARD in roles or ROLE_MARKER in roles:
        return "bang_diem_lop"

    if ROLE_PROCTOR in roles or ROLE_VIEWER in roles:
        return "dashboard"

    return None
