from decimal import Decimal
import io

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q, Prefetch
from django.http import FileResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from .constants import ASSIGN_CANCELED
from .models import (
    CauHinhChamThi,
    ChamDiemBaiThi,
    PhieuCham,
    PhieuChamChiTiet,
    DoiChieuChamDiem,
    GanTokenBaiThi,
    PhienThi,
)
from .scoring_rules import AUTO_GK2, ACTION_LABELS, classify_score_difference
from .scoring_utils import parse_smart_score

CANCELLED_ASSIGN_STATUSES = {ASSIGN_CANCELED, "huy", "da_huy", "cancelled", "canceled"}
COLLECTED_ASSIGN_STATUSES = {"da_thu", "collected"}


def is_admin_manager(user):
    return bool(user and user.is_authenticated and (user.is_superuser or user.groups.filter(name__in=["admin", "quan_ly_thi"]).exists()))


def in_groups(user, names):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=names).exists()


def can_score_lan(user, lan_cham):
    if lan_cham == 1:
        return in_groups(user, ["admin", "quan_ly_thi", "giam_khao_1"])
    if lan_cham == 2:
        return in_groups(user, ["admin", "quan_ly_thi", "giam_khao_2"])
    return is_admin_manager(user) or in_groups(user, ["truong_hoi_dong"])


def user_display(user):
    if not user:
        return ""
    name = ""
    try:
        name = (user.get_full_name() or "").strip()
    except Exception:
        pass
    return name or getattr(user, "username", "") or ""


def fmt_score(value):
    if value in [None, ""]:
        return ""
    try:
        d = Decimal(str(value)).quantize(Decimal("0.01"))
        return f"{d:.2f}".rstrip("0").rstrip(".")
    except Exception:
        return str(value)


def find_gan_token_by_qr(qr_text):
    qr_text = str(qr_text or "").strip()
    if not qr_text:
        raise ValueError("Vui lòng quét QR bài thi.")
    gan = (
        GanTokenBaiThi.objects
        .select_related("phien_thi", "phien_thi__lop", "phien_thi__mon", "hoc_vien", "token")
        .filter(Q(token__qr_link=qr_text) | Q(token__token=qr_text) | Q(token__public_token=qr_text))
        .exclude(trang_thai__in=CANCELLED_ASSIGN_STATUSES)
        .first()
    )
    if not gan:
        raise ValueError("Không tìm thấy bài thi theo QR đã quét.")
    if getattr(gan, "trang_thai", "") not in COLLECTED_ASSIGN_STATUSES:
        raise ValueError("Chỉ được chấm bài đã thu.")
    return gan


def get_or_create_bai_cham_by_student(gan):
    """Một thí sinh = một bài chấm, dù có nhiều tờ/QR."""
    bai = (
        ChamDiemBaiThi.objects
        .select_related("gan_token", "gan_token__hoc_vien", "phien_thi", "token")
        .filter(phien_thi=gan.phien_thi, gan_token__hoc_vien=gan.hoc_vien)
        .order_by("id")
        .first()
    )
    if bai:
        return bai
    return ChamDiemBaiThi.objects.create(
        gan_token=gan,
        phien_thi=gan.phien_thi,
        token=gan.token,
        trang_thai="chua_cham",
    )


def required_students_count(phien_thi):
    return (
        GanTokenBaiThi.objects
        .filter(phien_thi=phien_thi, trang_thai__in=COLLECTED_ASSIGN_STATUSES)
        .exclude(trang_thai__in=CANCELLED_ASSIGN_STATUSES)
        .values("hoc_vien_id")
        .distinct()
        .count()
    )


def scored_students_count(phien_thi, lan_cham):
    return (
        PhieuCham.objects
        .filter(bai_cham__phien_thi=phien_thi, lan_cham=lan_cham, trang_thai="da_nop")
        .exclude(bai_cham__gan_token__trang_thai__in=CANCELLED_ASSIGN_STATUSES)
        .values("bai_cham__gan_token__hoc_vien_id")
        .distinct()
        .count()
    )


def is_lan_full(phien_thi, lan_cham):
    required = required_students_count(phien_thi)
    return required > 0 and scored_students_count(phien_thi, lan_cham) >= required


def get_config(phien_thi, lan_cham):
    return CauHinhChamThi.objects.filter(phien_thi=phien_thi, lan_cham=lan_cham).first()


def get_or_create_config(phien_thi, lan_cham, ten_can_bo_cham, so_cau, user):
    if lan_cham == 2:
        cfg1 = get_config(phien_thi, 1)
        if not cfg1:
            raise ValueError("Chưa có cấu hình chấm lần 1.")
        so_cau = cfg1.so_cau
    so_cau = int(so_cau)
    if so_cau not in [2, 3, 4]:
        raise ValueError("Số câu hỏi chỉ được chọn 2, 3 hoặc 4.")
    cfg, created = CauHinhChamThi.objects.get_or_create(
        phien_thi=phien_thi,
        lan_cham=lan_cham,
        defaults={
            "ten_can_bo_cham": str(ten_can_bo_cham or "").strip(),
            "so_cau": so_cau,
            "created_by": user,
        },
    )
    if not created and (not cfg.is_locked or is_admin_manager(user)):
        cfg.ten_can_bo_cham = str(ten_can_bo_cham or cfg.ten_can_bo_cham or "").strip()
        cfg.so_cau = so_cau if lan_cham == 1 else (get_config(phien_thi, 1).so_cau)
        if not cfg.created_by_id:
            cfg.created_by = user
        cfg.save(update_fields=["ten_can_bo_cham", "so_cau", "created_by"])
    return cfg


def phieu_for_bai(bai, lan_cham):
    return (
        PhieuCham.objects
        .select_related("nguoi_cham")
        .prefetch_related("chi_tiet")
        .filter(bai_cham=bai, lan_cham=lan_cham, trang_thai="da_nop")
        .order_by("-submitted_at", "-id")
        .first()
    )


def scores_from_phieu(phieu):
    if not phieu:
        return {}
    return {int(x.cau_so): x.diem for x in phieu.chi_tiet.all()}


def score_rows(so_cau, phieu=None):
    scores = scores_from_phieu(phieu)
    return [{"cau_so": i, "diem": fmt_score(scores.get(i))} for i in range(1, int(so_cau) + 1)]


def collect_scores_from_post(request, so_cau):
    rows = []
    total = Decimal("0.00")
    for i in range(1, int(so_cau) + 1):
        raw = request.POST.get(f"diem_{i}", "")
        if str(raw or "").strip() == "":
            raise ValueError(f"Vui lòng nhập điểm câu {i}.")
        diem = parse_smart_score(raw)
        rows.append((i, diem))
        total += diem
    total = total.quantize(Decimal("0.01"))
    if total > Decimal("10.00"):
        raise ValueError("Tổng điểm không được vượt quá 10.")
    return rows, total


def save_or_update_phieu(request, bai, lan_cham, cfg, edit=False):
    existing = phieu_for_bai(bai, lan_cham)
    if existing and not edit:
        raise ValueError("Bài thi này đã được chấm. Vui lòng quét bài khác.")
    if existing and existing.is_locked and not is_admin_manager(request.user):
        raise ValueError("Phiếu chấm đã khóa. Chỉ admin Phòng Khảo thí được sửa.")
    rows, total = collect_scores_from_post(request, cfg.so_cau)
    with transaction.atomic():
        if existing:
            phieu = existing
            phieu.tong_diem = total
            phieu.nguoi_cham = request.user
            phieu.ten_can_bo_cham = cfg.ten_can_bo_cham
            phieu.so_cau = cfg.so_cau
            phieu.ghi_chu = request.POST.get("ghi_chu", "").strip()
            phieu.submitted_at = timezone.now()
            phieu.save(update_fields=["tong_diem", "nguoi_cham", "ten_can_bo_cham", "so_cau", "ghi_chu", "submitted_at"])
            phieu.chi_tiet.all().delete()
        else:
            phieu = PhieuCham.objects.create(
                bai_cham=bai,
                lan_cham=lan_cham,
                nguoi_cham=request.user,
                ten_can_bo_cham=cfg.ten_can_bo_cham,
                so_cau=cfg.so_cau,
                tong_diem=total,
                trang_thai="da_nop",
                submitted_at=timezone.now(),
                ghi_chu=request.POST.get("ghi_chu", "").strip(),
            )
        PhieuChamChiTiet.objects.bulk_create([PhieuChamChiTiet(phieu_cham=phieu, cau_so=cau, diem=diem) for cau, diem in rows])
        bai.trang_thai = "da_cham_gk1" if lan_cham == 1 else "da_cham_gk2" if lan_cham == 2 else "hoan_tat"
        if lan_cham == 3:
            bai.diem_chinh_thuc = total
        bai.save(update_fields=["trang_thai", "diem_chinh_thuc", "updated_at"])
    return phieu


def current_session_key(lan_cham):
    return f"cham_diem_current_phien_lan_{lan_cham}"


def render_scan(request, lan_cham, **ctx):
    ctx.setdefault("lan_cham", lan_cham)
    ctx.setdefault("role_title", "Cán bộ chấm thi 1" if lan_cham == 1 else "Cán bộ chấm thi 2")
    ctx.setdefault("mode", request.GET.get("mode") or request.POST.get("mode") or "")
    return render(request, "exam_token/cham_diem_workflow_scan.html", ctx)


def check_lan2_allowed(phien_thi):
    if not is_lan_full(phien_thi, 1):
        required = required_students_count(phien_thi)
        scored = scored_students_count(phien_thi, 1)
        raise ValueError(f"CBCT 1 chưa chấm đủ bài. Đã chấm {scored}/{required} thí sinh.")


def handle_scan(request, lan_cham, allow_switch=False):
    qr_text = request.POST.get("qr_link", "").strip()
    mode = request.POST.get("mode", "") or request.GET.get("mode", "")
    gan = find_gan_token_by_qr(qr_text)
    pt = gan.phien_thi
    if lan_cham == 2:
        check_lan2_allowed(pt)
    key = current_session_key(lan_cham)
    current_id = request.session.get(key)
    if current_id and int(current_id) != int(pt.pk) and not allow_switch:
        old_pt = PhienThi.objects.select_related("lop", "mon").filter(pk=current_id).first()
        return render_scan(request, lan_cham, need_confirm_switch=True, old_pt=old_pt, new_pt=pt, qr_link=qr_text, mode=mode)
    request.session[key] = pt.pk
    cfg = get_config(pt, lan_cham)
    cfg1 = get_config(pt, 1)
    if not cfg:
        return render_scan(request, lan_cham, pending_config=True, pt=pt, qr_link=qr_text, fixed_so_cau=(cfg1.so_cau if lan_cham == 2 and cfg1 else None), mode=mode)
    bai = get_or_create_bai_cham_by_student(gan)
    existing = phieu_for_bai(bai, lan_cham)
    if existing and mode != "edit":
        messages.error(request, "Bài thi này đã được chấm. Vui lòng quét bài khác.")
        return render_scan(request, lan_cham, config=cfg, pt=pt, mode=mode)
    if existing and existing.is_locked and not is_admin_manager(request.user):
        messages.error(request, "Phiếu chấm đã khóa. Muốn sửa điểm cần tài khoản admin Phòng Khảo thí.")
        return render_scan(request, lan_cham, config=cfg, pt=pt, mode=mode)
    phieu_gk1 = phieu_for_bai(bai, 1) if lan_cham == 2 else None
    return render_scan(request, lan_cham, scoring=True, pt=pt, bai_cham=bai, gan=gan, qr_link=qr_text, config=cfg, score_rows=score_rows(cfg.so_cau, existing), existing_phieu=existing, phieu_gk1=phieu_gk1, phieu_gk1_rows=score_rows(cfg.so_cau, phieu_gk1), mode=mode)


@login_required
def cham_diem_gk1(request):
    return cham_diem_scan_workflow(request, 1)


@login_required
def cham_diem_gk2(request):
    return cham_diem_scan_workflow(request, 2)


@login_required
def cham_diem_scan_workflow(request, lan_cham):
    if not can_score_lan(request.user, lan_cham):
        return HttpResponseForbidden("Bạn không có quyền chấm lượt này.")
    if request.method == "POST":
        action = request.POST.get("action", "")
        try:
            if action == "scan":
                return handle_scan(request, lan_cham)
            if action == "confirm_switch":
                request.session.pop(current_session_key(lan_cham), None)
                return handle_scan(request, lan_cham, allow_switch=True)
            if action == "cancel_switch":
                messages.info(request, "Đã hủy chuyển sang lớp/môn khác.")
                return redirect("cham_diem_gk1" if lan_cham == 1 else "cham_diem_gk2")
            if action == "save_config_then_scan":
                qr_text = request.POST.get("qr_link", "").strip()
                gan = find_gan_token_by_qr(qr_text)
                if lan_cham == 2:
                    check_lan2_allowed(gan.phien_thi)
                ten = request.POST.get("ten_can_bo_cham", "").strip()
                if not ten:
                    raise ValueError("Vui lòng nhập tên cán bộ chấm thi.")
                get_or_create_config(gan.phien_thi, lan_cham, ten, request.POST.get("so_cau") or 2, request.user)
                request.session[current_session_key(lan_cham)] = gan.phien_thi_id
                messages.success(request, "Đã lưu cấu hình phiên chấm.")
                return handle_scan(request, lan_cham, allow_switch=True)
            if action == "submit_score":
                qr_text = request.POST.get("qr_link", "").strip()
                mode = request.POST.get("mode", "")
                gan = find_gan_token_by_qr(qr_text)
                if lan_cham == 2:
                    check_lan2_allowed(gan.phien_thi)
                cfg = get_config(gan.phien_thi, lan_cham)
                if not cfg:
                    raise ValueError("Chưa có cấu hình phiên chấm. Vui lòng quét lại QR để cấu hình.")
                bai = get_or_create_bai_cham_by_student(gan)
                save_or_update_phieu(request, bai, lan_cham, cfg, edit=(mode == "edit"))
                messages.success(request, "Đã lưu phiếu chấm.")
                return redirect("cham_diem_gk1" if lan_cham == 1 else "cham_diem_gk2")
        except Exception as exc:
            messages.error(request, str(exc))
    return render_scan(request, lan_cham)


@login_required
def cham_diem_tong_hop_can_bo(request, lan_cham, phien_thi_id):
    if not can_score_lan(request.user, lan_cham):
        return HttpResponseForbidden("Bạn không có quyền xem phiếu tổng hợp lượt này.")
    pt = get_object_or_404(PhienThi.objects.select_related("lop", "mon"), pk=phien_thi_id)
    cfg = get_config(pt, lan_cham)
    if request.method == "POST" and request.POST.get("action") == "finish":
        if not cfg:
            messages.error(request, "Chưa có cấu hình phiên chấm.")
            return redirect("cham_diem_tong_hop_can_bo", lan_cham=lan_cham, phien_thi_id=pt.pk)
        now = timezone.now()
        cfg.is_completed = True
        cfg.completed_at = now
        cfg.is_locked = True
        cfg.locked_at = now
        cfg.save(update_fields=["is_completed", "completed_at", "is_locked", "locked_at"])
        PhieuCham.objects.filter(bai_cham__phien_thi=pt, lan_cham=lan_cham, trang_thai="da_nop").update(is_locked=True, locked_at=now)
        messages.success(request, "Đã hoàn thành việc nhập điểm. Phiếu đã nhập đã được khóa.")
        return redirect("cham_diem_tong_hop_can_bo", lan_cham=lan_cham, phien_thi_id=pt.pk)
    required = required_students_count(pt)
    scored = scored_students_count(pt, lan_cham)
    is_full = required > 0 and scored >= required
    phieus = (
        PhieuCham.objects.select_related("bai_cham", "bai_cham__gan_token", "bai_cham__gan_token__hoc_vien", "bai_cham__token", "nguoi_cham")
        .prefetch_related("chi_tiet")
        .filter(bai_cham__phien_thi=pt, lan_cham=lan_cham, trang_thai="da_nop")
        .order_by("bai_cham__gan_token__hoc_vien__so_bao_danh", "id")
    )
    rows = []
    for p in phieus:
        rows.append({"phieu": p, "bai": p.bai_cham, "token_id": getattr(p.bai_cham.token, "id", "") if p.bai_cham and p.bai_cham.token_id else "", "scores": scores_from_phieu(p), "total": p.tong_diem})
    so_cau = int(cfg.so_cau if cfg else 2)
    return render(request, "exam_token/cham_diem_tong_hop_can_bo.html", {"pt": pt, "config": cfg, "lan_cham": lan_cham, "role_title": "Cán bộ chấm thi 1" if lan_cham == 1 else "Cán bộ chấm thi 2", "required": required, "scored": scored, "is_full": is_full, "rows": rows, "cau_range": range(1, so_cau + 1), "can_compare": (lan_cham == 2 and is_full)})


@login_required
def phieu_cham_can_bo_pdf(request, lan_cham, phien_thi_id):
    if not can_score_lan(request.user, lan_cham):
        return HttpResponseForbidden("Bạn không có quyền in phiếu.")
    pt = get_object_or_404(PhienThi.objects.select_related("lop", "mon"), pk=phien_thi_id)
    cfg = get_config(pt, lan_cham)
    phieus = PhieuCham.objects.select_related("bai_cham", "bai_cham__token", "bai_cham__gan_token", "bai_cham__gan_token__hoc_vien").filter(bai_cham__phien_thi=pt, lan_cham=lan_cham, trang_thai="da_nop").order_by("bai_cham__gan_token__hoc_vien__so_bao_danh", "id")
    buf = io.BytesIO(); c = canvas.Canvas(buf, pagesize=A4); w, h = A4; x = 12*mm; y = h-15*mm
    c.setFont("Helvetica-Bold", 13); c.drawCentredString(w/2, y, f"PHIEU CHAM CAN BO {lan_cham}"); y -= 10*mm
    c.setFont("Helvetica", 10); c.drawString(x, y, f"Mon: {pt.mon.ten_mon if pt.mon else ''}"); c.drawString(95*mm, y, f"Lop: {pt.lop.ten_lop if pt.lop else ''}"); y -= 6*mm
    c.drawString(x, y, f"Can bo cham: {cfg.ten_can_bo_cham if cfg else ''}"); y -= 10*mm
    headers = ["STT", "ID QR", "Tong", "Ghi chu"]; widths = [15*mm, 35*mm, 25*mm, 110*mm]; row_h = 8*mm
    for idx, p in enumerate(phieus, 1):
        if y < 20*mm:
            c.showPage(); y = h-15*mm
        cells = [idx, getattr(p.bai_cham.token, "id", "") if p.bai_cham and p.bai_cham.token_id else "", fmt_score(p.tong_diem), p.ghi_chu or ""]
        xx = x
        for cell, cw in zip(cells, widths):
            c.rect(xx, y-row_h, cw, row_h); c.drawString(xx+1*mm, y-5*mm, str(cell)[:50]); xx += cw
        y -= row_h
    y -= 18*mm; c.setFont("Helvetica-Bold", 10); c.drawCentredString(145*mm, y, "CAN BO CHAM THI"); y -= 18*mm; c.setFont("Helvetica", 10); c.drawCentredString(145*mm, y, cfg.ten_can_bo_cham if cfg else "")
    c.save(); buf.seek(0)
    return FileResponse(buf, filename=f"phieu_cham_cbct_{lan_cham}_{pt.pk}.pdf", content_type="application/pdf")


@login_required
def cham_diem_doi_chieu_phien(request, phien_thi_id):
    if not (is_admin_manager(request.user) or in_groups(request.user, ["giam_khao_2", "truong_hoi_dong", "can_bo_cham_diem"])):
        return HttpResponseForbidden("Bạn không có quyền đối chiếu điểm.")
    pt = get_object_or_404(PhienThi.objects.select_related("lop", "mon"), pk=phien_thi_id)
    if not is_lan_full(pt, 2):
        messages.error(request, "CBCT 2 chưa chấm đủ số thí sinh đã thu bài. Chưa được đối chiếu toàn phiên.")
        return redirect("cham_diem_tong_hop_can_bo", lan_cham=2, phien_thi_id=pt.pk)
    cfg = get_config(pt, 1) or get_config(pt, 2); so_cau = int(cfg.so_cau if cfg else 2)
    bai_chams = ChamDiemBaiThi.objects.select_related("gan_token", "gan_token__hoc_vien", "token", "phien_thi").prefetch_related(Prefetch("phieu_cham", queryset=PhieuCham.objects.select_related("nguoi_cham").prefetch_related("chi_tiet").order_by("lan_cham", "id"))).filter(phien_thi=pt, gan_token__trang_thai__in=COLLECTED_ASSIGN_STATUSES).exclude(gan_token__trang_thai__in=CANCELLED_ASSIGN_STATUSES).order_by("gan_token__hoc_vien__so_bao_danh", "id")
    rows = []; all_done = True
    for bai in bai_chams:
        phieu1 = next((p for p in bai.phieu_cham.all() if p.lan_cham == 1 and p.trang_thai == "da_nop"), None)
        phieu2 = next((p for p in bai.phieu_cham.all() if p.lan_cham == 2 and p.trang_thai == "da_nop"), None)
        if not phieu1 or not phieu2:
            all_done = False; continue
        s1 = scores_from_phieu(phieu1); s2 = scores_from_phieu(phieu2); result = classify_score_difference(s1, s2, phieu1.tong_diem, phieu2.tong_diem)
        if result.action == AUTO_GK2 and not bai.doi_chieu_done:
            bai.max_do_lech = result.max_diff; bai.do_lech = result.total_diff; bai.hinh_thuc_xu_ly = AUTO_GK2; bai.ghi_chu_doi_chieu = result.note; bai.diem_chinh_thuc = phieu2.tong_diem; bai.diem_xu_ly = phieu2.tong_diem; bai.doi_chieu_done = True; bai.trang_thai = "hoan_tat"
            bai.save(update_fields=["max_do_lech", "do_lech", "hinh_thuc_xu_ly", "ghi_chu_doi_chieu", "diem_chinh_thuc", "diem_xu_ly", "doi_chieu_done", "trang_thai", "updated_at"])
        if result.need_processing and not bai.doi_chieu_done:
            all_done = False
        rows.append({"bai": bai, "token_id": getattr(bai.token, "id", ""), "phieu1": phieu1, "phieu2": phieu2, "scores1": s1, "scores2": s2, "diffs": result.question_diffs, "total_diff": result.total_diff, "max_diff": result.max_diff, "action": result.action, "action_label": ACTION_LABELS.get(result.action, result.action), "note": result.note, "doi_chieu_done": bai.doi_chieu_done, "diem_chinh_thuc": bai.diem_chinh_thuc})
    return render(request, "exam_token/cham_diem_doi_chieu_phien.html", {"pt": pt, "rows": rows, "cau_range": range(1, so_cau + 1), "can_publish": all_done and bool(rows)})


@login_required
def cham_diem_xu_ly_lech(request, bai_cham_id):
    bai = get_object_or_404(ChamDiemBaiThi.objects.select_related("phien_thi", "phien_thi__lop", "phien_thi__mon", "token"), pk=bai_cham_id)
    if not (is_admin_manager(request.user) or in_groups(request.user, ["truong_hoi_dong", "giam_khao_1", "giam_khao_2"])):
        return HttpResponseForbidden("Bạn không có quyền xử lý lệch điểm.")
    phieu1 = phieu_for_bai(bai, 1); phieu2 = phieu_for_bai(bai, 2)
    if not phieu1 or not phieu2:
        messages.error(request, "Bài này chưa đủ 2 phiếu chấm."); return redirect("cham_diem_doi_chieu_phien", phien_thi_id=bai.phien_thi_id)
    cfg = get_config(bai.phien_thi, 1) or get_config(bai.phien_thi, 2); so_cau = int(cfg.so_cau if cfg else 2)
    s1 = scores_from_phieu(phieu1); s2 = scores_from_phieu(phieu2); result = classify_score_difference(s1, s2, phieu1.tong_diem, phieu2.tong_diem)
    if request.method == "POST":
        try:
            rows_score, total = collect_scores_from_post(request, so_cau)
            ten = request.POST.get("ten_can_bo_cham", "").strip() or ("CBCT thống nhất" if result.action != "cham_lan_3" else "Lãnh đạo chấm lần 3")
            with transaction.atomic():
                phieu3 = phieu_for_bai(bai, 3)
                if phieu3:
                    phieu3.tong_diem = total; phieu3.nguoi_cham = request.user; phieu3.ten_can_bo_cham = ten; phieu3.so_cau = so_cau; phieu3.trang_thai = "da_nop"; phieu3.submitted_at = timezone.now(); phieu3.ghi_chu = request.POST.get("ghi_chu", "").strip(); phieu3.save(); phieu3.chi_tiet.all().delete()
                else:
                    phieu3 = PhieuCham.objects.create(bai_cham=bai, lan_cham=3, nguoi_cham=request.user, ten_can_bo_cham=ten, so_cau=so_cau, tong_diem=total, trang_thai="da_nop", submitted_at=timezone.now(), ghi_chu=request.POST.get("ghi_chu", "").strip())
                PhieuChamChiTiet.objects.bulk_create([PhieuChamChiTiet(phieu_cham=phieu3, cau_so=cau, diem=diem) for cau, diem in rows_score])
                bai.max_do_lech = result.max_diff; bai.do_lech = result.total_diff; bai.hinh_thuc_xu_ly = result.action; bai.ghi_chu_doi_chieu = ACTION_LABELS.get(result.action, result.action); bai.diem_xu_ly = total; bai.diem_chinh_thuc = total; bai.doi_chieu_done = True; bai.trang_thai = "hoan_tat"; bai.save(update_fields=["max_do_lech", "do_lech", "hinh_thuc_xu_ly", "ghi_chu_doi_chieu", "diem_xu_ly", "diem_chinh_thuc", "doi_chieu_done", "trang_thai", "updated_at"])
            messages.success(request, "Đã xử lý lệch điểm."); return redirect("cham_diem_doi_chieu_phien", phien_thi_id=bai.phien_thi_id)
        except Exception as exc:
            messages.error(request, str(exc))
    return render(request, "exam_token/cham_diem_xu_ly_lech.html", {"bai": bai, "phieu1": phieu1, "phieu2": phieu2, "scores1": s1, "scores2": s2, "diffs": result.question_diffs, "total_diff": result.total_diff, "max_diff": result.max_diff, "action_label": ACTION_LABELS.get(result.action, result.action), "note": result.note, "cau_range": range(1, so_cau + 1), "score_rows": score_rows(so_cau, phieu_for_bai(bai, 3))})


@login_required
def xuat_bang_diem_tong_hop_cuoi(request, phien_thi_id):
    if not (is_admin_manager(request.user) or in_groups(request.user, ["truong_hoi_dong", "can_bo_cham_diem"])):
        return HttpResponseForbidden("Bạn không có quyền xuất bảng điểm.")
    pt = get_object_or_404(PhienThi, pk=phien_thi_id)
    unfinished = ChamDiemBaiThi.objects.filter(phien_thi=pt, gan_token__trang_thai__in=COLLECTED_ASSIGN_STATUSES, doi_chieu_done=False).count()
    if unfinished:
        messages.error(request, "Còn bài chưa xử lý lệch điểm. Chưa được xuất bảng điểm cuối.")
        return redirect("cham_diem_doi_chieu_phien", phien_thi_id=pt.pk)
    ChamDiemBaiThi.objects.filter(phien_thi=pt, published_at__isnull=True).update(published_at=timezone.now())
    messages.success(request, "Đã xuất bản điểm tổng hợp cuối cùng.")
    return redirect("bang_diem_lop")

@login_required
def cham_diem_tong_hop_man_hinh(request):
    """Trang xem điểm tổng hợp trực tiếp trên màn hình, không cần quét QR trước."""
    if not (is_admin_manager(request.user) or in_groups(request.user, ["giam_khao_1", "giam_khao_2", "truong_hoi_dong", "can_bo_cham_diem"])):
        return HttpResponseForbidden("Bạn không có quyền xem điểm tổng hợp.")

    q = (request.GET.get("q") or "").strip()
    selected_id = (request.GET.get("phien_thi") or "").strip()

    phien_qs = PhienThi.objects.select_related("lop", "mon").order_by("-id")
    if q:
        q_filter = Q(lop__ten_lop__icontains=q) | Q(mon__ten_mon__icontains=q)
        if q.isdigit():
            q_filter = q_filter | Q(id=int(q))
        phien_qs = phien_qs.filter(q_filter)

    phien_list = list(phien_qs[:100])
    selected_pt = None
    rows = []
    cfg1 = cfg2 = None
    required = scored1 = scored2 = 0
    so_cau = 2
    can_open_compare = False

    if selected_id:
        selected_pt = get_object_or_404(PhienThi.objects.select_related("lop", "mon"), pk=selected_id)
        cfg1 = get_config(selected_pt, 1)
        cfg2 = get_config(selected_pt, 2)
        cfg_any = cfg1 or cfg2
        so_cau = int(cfg_any.so_cau if cfg_any else 2)
        required = required_students_count(selected_pt)
        scored1 = scored_students_count(selected_pt, 1)
        scored2 = scored_students_count(selected_pt, 2)
        can_open_compare = required > 0 and scored2 >= required

        assignments = (
            GanTokenBaiThi.objects
            .select_related("hoc_vien", "token")
            .filter(phien_thi=selected_pt, trang_thai__in=COLLECTED_ASSIGN_STATUSES)
            .exclude(trang_thai__in=CANCELLED_ASSIGN_STATUSES)
            .order_by("hoc_vien__so_bao_danh", "hoc_vien_id", "id")
        )

        by_student = {}
        student_order = []
        for a in assignments:
            hv_id = a.hoc_vien_id
            if hv_id not in by_student:
                by_student[hv_id] = {"hoc_vien_id": hv_id, "token_ids": [], "first_assignment": a}
                student_order.append(hv_id)
            token_id = getattr(a.token, "id", "") if a.token_id else ""
            if token_id and token_id not in by_student[hv_id]["token_ids"]:
                by_student[hv_id]["token_ids"].append(token_id)

        bai_by_student = {}
        if student_order:
            bai_qs = (
                ChamDiemBaiThi.objects
                .select_related("gan_token", "gan_token__hoc_vien", "token")
                .prefetch_related(Prefetch(
                    "phieu_cham",
                    queryset=PhieuCham.objects.select_related("nguoi_cham").prefetch_related("chi_tiet").order_by("lan_cham", "id"),
                ))
                .filter(phien_thi=selected_pt, gan_token__hoc_vien_id__in=student_order)
                .order_by("id")
            )
            for bai in bai_qs:
                hv_id = bai.gan_token.hoc_vien_id if bai.gan_token_id else None
                if hv_id and hv_id not in bai_by_student:
                    bai_by_student[hv_id] = bai

        for hv_id in student_order:
            item = by_student[hv_id]
            bai = bai_by_student.get(hv_id)
            phieu1 = phieu2 = phieu3 = None
            s1 = {}
            s2 = {}
            s3 = {}
            diffs = {}
            total_diff = ""
            max_diff = ""
            action_label = ""
            note = "Chưa chấm"
            status = "Chưa chấm"
            final_score = ""
            need_processing = False
            doi_chieu_done = False

            if bai:
                phieus = list(bai.phieu_cham.all())
                phieu1 = next((p for p in phieus if p.lan_cham == 1 and p.trang_thai == "da_nop"), None)
                phieu2 = next((p for p in phieus if p.lan_cham == 2 and p.trang_thai == "da_nop"), None)
                phieu3 = next((p for p in phieus if p.lan_cham == 3 and p.trang_thai == "da_nop"), None)
                s1 = scores_from_phieu(phieu1)
                s2 = scores_from_phieu(phieu2)
                s3 = scores_from_phieu(phieu3)
                final_score = fmt_score(getattr(bai, "diem_chinh_thuc", ""))
                doi_chieu_done = bool(getattr(bai, "doi_chieu_done", False))

                if phieu1 and phieu2:
                    result = classify_score_difference(s1, s2, phieu1.tong_diem, phieu2.tong_diem)
                    diffs = result.question_diffs
                    total_diff = result.total_diff
                    max_diff = result.max_diff
                    need_processing = bool(result.need_processing and not doi_chieu_done)
                    action_label = ACTION_LABELS.get(getattr(bai, "hinh_thuc_xu_ly", "") or result.action, result.action)
                    note = getattr(bai, "ghi_chu_doi_chieu", "") or result.note
                    if doi_chieu_done:
                        status = "Đã xử lý"
                    elif result.need_processing:
                        status = "Cần xử lý lệch"
                    else:
                        status = "Tự động lấy CBCT 2"
                elif phieu1 and not phieu2:
                    status = "Chờ CBCT 2"
                    note = "CBCT 1 đã chấm, CBCT 2 chưa chấm"
                elif phieu2 and not phieu1:
                    status = "Thiếu CBCT 1"
                    note = "Có phiếu CBCT 2 nhưng chưa có phiếu CBCT 1"

            rows.append({
                "bai": bai,
                "token_ids": ", ".join(str(x) for x in item["token_ids"]),
                "phieu1": phieu1,
                "phieu2": phieu2,
                "phieu3": phieu3,
                "scores1": s1,
                "scores2": s2,
                "scores3": s3,
                "diffs": diffs,
                "total_diff": total_diff,
                "max_diff": max_diff,
                "final_score": final_score,
                "action_label": action_label,
                "note": note,
                "status": status,
                "need_processing": need_processing,
                "doi_chieu_done": doi_chieu_done,
            })

    return render(request, "exam_token/cham_diem_tong_hop_man_hinh.html", {
        "q": q,
        "phien_list": phien_list,
        "selected_pt": selected_pt,
        "cfg1": cfg1,
        "cfg2": cfg2,
        "required": required,
        "scored1": scored1,
        "scored2": scored2,
        "so_cau": so_cau,
        "cau_range": range(1, so_cau + 1),
        "rows": rows,
        "can_open_compare": can_open_compare,
    })
