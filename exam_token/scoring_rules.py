from dataclasses import dataclass
from decimal import Decimal

AUTO_GK2 = "tu_dong_lay_gk2"
CBCT_THONG_NHAT = "cbct_thong_nhat"
LANH_DAO_QUYET_DINH = "lanh_dao_quyet_dinh"
CHAM_LAN_3 = "cham_lan_3"

ACTION_LABELS = {
    AUTO_GK2: "Tự động lấy điểm CBCT 2",
    CBCT_THONG_NHAT: "CBCT thống nhất điểm",
    LANH_DAO_QUYET_DINH: "Lãnh đạo quyết định điểm",
    CHAM_LAN_3: "Chấm lần 3",
}

ACTION_NOTES = {
    AUTO_GK2: "Tự động lấy điểm CBCT 2 làm điểm chính thức.",
    CBCT_THONG_NHAT: "Hai cán bộ chấm thi vui lòng thảo luận và thống nhất điểm.",
    LANH_DAO_QUYET_DINH: "Vui lòng báo cáo Lãnh đạo thống nhất hoặc quyết định điểm.",
    CHAM_LAN_3: "Vui lòng báo cáo Lãnh đạo chấm điểm lần 3.",
}

@dataclass(frozen=True)
class ScoreDifferenceResult:
    max_diff: Decimal
    total_diff: Decimal
    question_diffs: dict
    action: str
    label: str
    note: str
    is_auto: bool
    need_processing: bool

def _d(value) -> Decimal:
    if value is None or value == "":
        return Decimal("0.00")
    if isinstance(value, Decimal):
        return value.quantize(Decimal("0.01"))
    return Decimal(str(value)).quantize(Decimal("0.01"))

def classify_score_difference(gk1_scores: dict, gk2_scores: dict, gk1_total=None, gk2_total=None) -> ScoreDifferenceResult:
    """
    max_lệch <= 0.5       -> tự lấy điểm CBCT 2
    0.5 < max_lệch <= 1.0 -> 2 CBCT thống nhất
    1.0 < max_lệch <= 1.5 -> lãnh đạo quyết định/thống nhất
    max_lệch > 1.5        -> lãnh đạo chấm lần 3
    """
    keys = sorted(set(gk1_scores.keys()) | set(gk2_scores.keys()))
    question_diffs = {}
    max_diff = Decimal("0.00")
    for key in keys:
        diff = abs(_d(gk1_scores.get(key)) - _d(gk2_scores.get(key))).quantize(Decimal("0.01"))
        question_diffs[key] = diff
        max_diff = max(max_diff, diff)

    if gk1_total is None:
        gk1_total = sum((_d(v) for v in gk1_scores.values()), Decimal("0.00"))
    if gk2_total is None:
        gk2_total = sum((_d(v) for v in gk2_scores.values()), Decimal("0.00"))
    total_diff = abs(_d(gk1_total) - _d(gk2_total)).quantize(Decimal("0.01"))
    max_diff = max(max_diff, total_diff)

    if max_diff <= Decimal("0.50"):
        action, need = AUTO_GK2, False
    elif max_diff <= Decimal("1.00"):
        action, need = CBCT_THONG_NHAT, True
    elif max_diff <= Decimal("1.50"):
        action, need = LANH_DAO_QUYET_DINH, True
    else:
        action, need = CHAM_LAN_3, True

    return ScoreDifferenceResult(
        max_diff=max_diff,
        total_diff=total_diff,
        question_diffs=question_diffs,
        action=action,
        label=ACTION_LABELS[action],
        note=ACTION_NOTES[action],
        is_auto=(action == AUTO_GK2),
        need_processing=need,
    )
