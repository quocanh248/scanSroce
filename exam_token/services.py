import uuid
from datetime import timedelta, date
from decimal import Decimal

from django.db import transaction
from django.db.models import Max, Sum
from django.utils import timezone
from .qr_tracking import QRTrackingError, build_qr_items, generate_sequence, format_print_date_prefix

from .constants import (
    ASSIGN_ASSIGNED,
    ASSIGN_CANCELED,
    ASSIGN_COLLECTED,
    QR_ASSIGNED,
    QR_CANCELED,
    QR_COLLECTED,
    QR_UNUSED,
    SESSION_COLLECTED,
    SESSION_FINISHED,
    SESSION_OPEN,
    SESSION_RUNNING,
)
from .models import ExamSessionLog, GanTokenBaiThi, HocVien, PhienThi, QRBatch, QRTokenBaiThi


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def log_action(request, action, phien_thi=None, object_type=None, object_id=None, message=None, old_data=None, new_data=None):
    user = getattr(request, 'user', None)
    can_bo = getattr(user, 'can_bo', None) if user and user.is_authenticated else None
    return ExamSessionLog.objects.create(
        user=user if user and user.is_authenticated else None,
        can_bo=can_bo,
        phien_thi=phien_thi,
        action=action,
        object_type=object_type,
        object_id=str(object_id) if object_id is not None else None,
        message=message,
        old_data=old_data,
        new_data=new_data,
        ip_address=get_client_ip(request) if request else None,
        user_agent=request.META.get('HTTP_USER_AGENT') if request else None,
    )


def normalize_status_values():
    """Helper for legacy DBs that contain broken Vietnamese encoded statuses."""
    QRTokenBaiThi.objects.filter(trang_thai__in=['Chã░a g├ín', 'Chưa gán', 'Chưa gắn']).update(trang_thai=QR_UNUSED)
    QRTokenBaiThi.objects.filter(trang_thai__in=['─É├ú g├ín', 'Đã gán']).update(trang_thai=QR_ASSIGNED)
    GanTokenBaiThi.objects.filter(trang_thai__in=['─É├ú g├ín', 'Đã gán']).update(trang_thai=ASSIGN_ASSIGNED)
    PhienThi.objects.filter(trang_thai__in=['─Éang mß╗ƒ', 'Đang mở']).update(trang_thai=SESSION_OPEN)


def create_qr_batch(ma_dot, so_luong, user=None, noi_dung_bat_dau=None, ngay_in=None):
    """
    Tạo đợt QR tracking v2:
    noi_dung -> token_ma_hoa AES -> public_token = YYYY-MM-DD + token_ma_hoa + suffix_10 -> qr_link.

    token trong qr_token_bai_thi lưu qr_link để khi quét QR có thể đối chiếu trực tiếp.
    """
    ma_dot = str(ma_dot or '').strip()
    noi_dung_bat_dau = str(noi_dung_bat_dau or 'DHCSND_000001').strip()

    if not ma_dot:
        raise ValueError('Mã lô/đợt QR không được để trống.')
    if int(so_luong) <= 0:
        raise ValueError('Số lượng QR phải lớn hơn 0.')
    if not noi_dung_bat_dau:
        raise ValueError('Vui lòng nhập nội dung mã đầu tiên, ví dụ DHCSND_000001.')

    if ngay_in is None:
        ngay_in = date.today()

    ngay_in_prefix = format_print_date_prefix(ngay_in)
    items = build_qr_items(noi_dung_bat_dau, int(so_luong), print_date=ngay_in)
    contents = [x['noi_dung'] for x in items]

    with transaction.atomic():
        batch = QRBatch.objects.create(
            ma_dot=ma_dot,
            so_luong=so_luong,
            ngay_in=ngay_in,
            ngay_in_prefix=ngay_in_prefix,
            noi_dung_bat_dau=contents[0] if contents else noi_dung_bat_dau,
            noi_dung_ket_thuc=contents[-1] if contents else noi_dung_bat_dau,
            created_by=user,
        )

        tokens = []
        for item in items:
            tokens.append(QRTokenBaiThi(
                batch=batch,
                token=item['qr_link'],
                noi_dung=item['noi_dung'],
                token_ma_hoa=item['token_ma_hoa'],
                public_token=item['public_token'],
                qr_link=item['qr_link'],
                ngay_in_prefix=item['ngay_in_prefix'],
                trang_thai=QR_UNUSED,
            ))
        QRTokenBaiThi.objects.bulk_create(tokens)
        return batch



def auto_collect_if_expired(request, phien_thi):
    if phien_thi.trang_thai == SESSION_RUNNING and phien_thi.ended_at and timezone.now() >= phien_thi.ended_at:
        collect_papers(request, phien_thi, auto=True)
        phien_thi.refresh_from_db()
        return True
    return False


@transaction.atomic
def start_exam_timer(request, phien_thi):
    pt = PhienThi.objects.select_for_update().get(pk=phien_thi.pk)
    if pt.trang_thai in [SESSION_COLLECTED, SESSION_FINISHED]:
        raise ValueError('Phiên thi đã thu/hoàn thành, không thể tính giờ.')
    if pt.started_at:
        return pt
    now = timezone.now()
    pt.started_at = now
    pt.ended_at = now + timedelta(minutes=int(pt.thoi_gian_lam_bai))
    pt.trang_thai = SESSION_RUNNING
    pt.save(update_fields=['started_at', 'ended_at', 'trang_thai'])
    log_action(request, 'start_timer', pt, 'phien_thi', pt.pk, 'Tính giờ làm bài', new_data={'started_at': str(pt.started_at), 'ended_at': str(pt.ended_at)})
    return pt


@transaction.atomic
def collect_papers(request, phien_thi, auto=False):
    pt = PhienThi.objects.select_for_update().get(pk=phien_thi.pk)
    if pt.trang_thai == SESSION_FINISHED:
        raise ValueError('Phiên thi đã hoàn thành.')
    now = timezone.now()
    assignments = GanTokenBaiThi.objects.select_for_update().filter(phien_thi=pt, trang_thai=ASSIGN_ASSIGNED)
    token_ids = list(assignments.values_list('token_id', flat=True))
    assignments.update(trang_thai=ASSIGN_COLLECTED, thoi_gian_thu=now)
    QRTokenBaiThi.objects.filter(id__in=token_ids).update(trang_thai=QR_COLLECTED, collected_at=now)
    pt.trang_thai = SESSION_COLLECTED
    pt.collected_at = now
    pt.save(update_fields=['trang_thai', 'collected_at'])
    log_action(request, 'auto_collect' if auto else 'collect_papers', pt, 'phien_thi', pt.pk, 'Tự động thu bài do hết giờ' if auto else 'Thu bài', new_data={'collected_at': str(now), 'count': len(token_ids)})
    return pt


def student_has_previous_sheet(phien_thi, hoc_vien):
    return GanTokenBaiThi.objects.filter(phien_thi=phien_thi, hoc_vien=hoc_vien).exists()


@transaction.atomic
def assign_qr_to_student(request, phien_thi, token_text, so_bao_danh):
    pt = PhienThi.objects.select_for_update().get(pk=phien_thi.pk)
    auto_collect_if_expired(request, pt)
    pt.refresh_from_db()
    if pt.trang_thai in [SESSION_COLLECTED, SESSION_FINISHED]:
        raise ValueError('Phiên thi đã thu/hoàn thành. Chỉ được hủy bài hoặc in biên bản.')
    token_text = (token_text or '').strip()
    so_bao_danh = str(so_bao_danh or '').strip()
    if not token_text or not so_bao_danh:
        raise ValueError('Vui lòng quét QR và nhập số báo danh.')
    try:
        token = QRTokenBaiThi.objects.select_for_update().get(token=token_text)
    except QRTokenBaiThi.DoesNotExist:
        raise ValueError('QR không tồn tại trong DB.')
    if token.trang_thai != QR_UNUSED:
        raise ValueError(f'QR không hợp lệ để gán. Trạng thái hiện tại: {token.get_trang_thai_display()}')
    try:
        hoc_vien = HocVien.objects.get(lop=pt.lop, so_bao_danh=int(so_bao_danh))
    except (HocVien.DoesNotExist, ValueError):
        raise ValueError('Không tìm thấy thí sinh theo SBD trong lớp của phiên thi.')
    if pt.started_at and not student_has_previous_sheet(pt, hoc_vien):
        raise ValueError('Đã tính giờ làm bài. Thí sinh chưa được phát bài trước đó không được gán QR mới.')
    max_to = GanTokenBaiThi.objects.filter(phien_thi=pt, hoc_vien=hoc_vien).aggregate(m=Max('so_to'))['m'] or 0
    assignment = GanTokenBaiThi.objects.create(
        token=token,
        phien_thi=pt,
        hoc_vien=hoc_vien,
        so_to=max_to + 1,
        trang_thai=ASSIGN_ASSIGNED,
    )
    now = timezone.now()
    token.trang_thai = QR_ASSIGNED
    token.assigned_at = now
    token.save(update_fields=['trang_thai', 'assigned_at'])
    log_action(request, 'assign_qr', pt, 'gan_token_bai_thi', assignment.pk, f'Gán QR {token.token} cho {hoc_vien.ho_ten}', new_data={'token': token.token, 'ma_hoc_vien': hoc_vien.ma_hoc_vien, 'sbd': hoc_vien.so_bao_danh, 'so_to': assignment.so_to})
    return assignment


@transaction.atomic
def cancel_assignment_by_token(request, phien_thi, token_text, reason=''):
    pt = PhienThi.objects.select_for_update().get(pk=phien_thi.pk)
    if pt.trang_thai == SESSION_FINISHED:
        raise ValueError('Phiên thi đã hoàn thành, không thể hủy bài.')
    token_text = (token_text or '').strip()
    try:
        assignment = GanTokenBaiThi.objects.select_for_update().select_related('token', 'hoc_vien').get(
            phien_thi=pt,
            token__token=token_text,
            trang_thai__in=[ASSIGN_ASSIGNED, ASSIGN_COLLECTED],
        )
    except GanTokenBaiThi.DoesNotExist:
        raise ValueError('Không tìm thấy QR đang hiệu lực trong phiên thi này.')
    old_data = {'trang_thai': assignment.trang_thai, 'token_status': assignment.token.trang_thai}
    now = timezone.now()
    assignment.trang_thai = ASSIGN_CANCELED
    assignment.ly_do_huy = reason
    assignment.thoi_gian_huy = now
    assignment.save(update_fields=['trang_thai', 'ly_do_huy', 'thoi_gian_huy'])
    assignment.token.trang_thai = QR_CANCELED
    assignment.token.canceled_at = now
    assignment.token.ghi_chu = reason
    assignment.token.save(update_fields=['trang_thai', 'canceled_at', 'ghi_chu'])
    log_action(request, 'cancel_qr', pt, 'gan_token_bai_thi', assignment.pk, f'Hủy bài của {assignment.hoc_vien.ho_ten}', old_data=old_data, new_data={'reason': reason, 'token': token_text})
    return assignment


@transaction.atomic
def edit_assignment_sbd(request, assignment_id, edit_token, new_sbd):
    assignment = GanTokenBaiThi.objects.select_for_update().select_related('phien_thi', 'token').get(pk=assignment_id)
    pt = assignment.phien_thi
    if pt.started_at:
        raise ValueError('Đã tính giờ làm bài, không được sửa SBD.')
    if assignment.token.token != (edit_token or '').strip():
        raise ValueError('QR quét lại không khớp với bài thi đang sửa.')
    try:
        hoc_vien = HocVien.objects.get(lop=pt.lop, so_bao_danh=int(new_sbd))
    except (HocVien.DoesNotExist, ValueError):
        raise ValueError('Không tìm thấy SBD mới trong lớp của phiên thi.')
    old_data = {'ma_hoc_vien': assignment.hoc_vien_id, 'sbd': assignment.hoc_vien.so_bao_danh}
    assignment.hoc_vien = hoc_vien
    assignment.save(update_fields=['hoc_vien'])
    log_action(request, 'edit_sbd', pt, 'gan_token_bai_thi', assignment.pk, 'Sửa số báo danh', old_data=old_data, new_data={'ma_hoc_vien': hoc_vien.ma_hoc_vien, 'sbd': hoc_vien.so_bao_danh})
    return assignment


@transaction.atomic
def finish_session(request, phien_thi):
    pt = PhienThi.objects.select_for_update().get(pk=phien_thi.pk)
    if pt.trang_thai not in [SESSION_COLLECTED, SESSION_FINISHED]:
        collect_papers(request, pt, auto=False)
        pt.refresh_from_db()
    pt.trang_thai = SESSION_FINISHED
    pt.finished_at = timezone.now()
    pt.save(update_fields=['trang_thai', 'finished_at'])
    log_action(request, 'finish_session', pt, 'phien_thi', pt.pk, 'Hoàn thành việc coi thi và khóa phiên')
    return pt


def grouped_assignments(phien_thi):
    rows = []
    active = GanTokenBaiThi.objects.filter(phien_thi=phien_thi).exclude(trang_thai=ASSIGN_CANCELED).select_related('hoc_vien', 'token').order_by('hoc_vien__so_bao_danh', 'so_to')
    by_student = {}
    for a in active:
        key = a.hoc_vien_id
        if key not in by_student:
            by_student[key] = {
                'ma_hoc_vien': a.hoc_vien_id,
                'sbd': a.hoc_vien.so_bao_danh,
                'ho_ten': a.hoc_vien.ho_ten,
                'ngay_sinh': a.hoc_vien.ngay_sinh,
                'tokens': [],
                'so_to_list': [],
                'tong_so_to': 0,
            }
        by_student[key]['tokens'].append(a)
        by_student[key]['so_to_list'].append(a.so_to)
        by_student[key]['tong_so_to'] += 1
    rows = list(by_student.values())
    rows.sort(key=lambda x: (x['sbd'] or 0, x['ho_ten']))
    return rows


def session_totals(phien_thi):
    active = GanTokenBaiThi.objects.filter(phien_thi=phien_thi).exclude(trang_thai=ASSIGN_CANCELED)
    return {
        'total_students': active.values('hoc_vien_id').distinct().count(),
        'total_sheets': active.count(),
    }


def score_total(details):
    return sum((d.diem_dat or Decimal('0')) for d in details)
