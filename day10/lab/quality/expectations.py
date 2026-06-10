"""
Expectation suite đơn giản (không bắt buộc Great Expectations).

Sinh viên có thể thay bằng GE / pydantic / custom — miễn là có halt có kiểm soát.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

REQUIRED_GRADING_DOC_IDS = frozenset(
    {
        "policy_refund_v4",
        "sla_p1_2026",
        "it_helpdesk_faq",
        "hr_leave_policy",
        "access_control_sop",
    }
)


@dataclass
class ExpectationResult:
    name: str
    passed: bool
    severity: str  # "warn" | "halt"
    detail: str


def run_expectations(cleaned_rows: List[Dict[str, Any]]) -> Tuple[List[ExpectationResult], bool]:
    """
    Trả về (results, should_halt).

    should_halt = True nếu có bất kỳ expectation severity halt nào fail.
    """
    results: List[ExpectationResult] = []

    # E1: có ít nhất 1 dòng sau clean
    ok = len(cleaned_rows) >= 1
    results.append(
        ExpectationResult(
            "min_one_row",
            ok,
            "halt",
            f"cleaned_rows={len(cleaned_rows)}",
        )
    )

    # E2: không doc_id rỗng
    bad_doc = [r for r in cleaned_rows if not (r.get("doc_id") or "").strip()]
    ok2 = len(bad_doc) == 0
    results.append(
        ExpectationResult(
            "no_empty_doc_id",
            ok2,
            "halt",
            f"empty_doc_id_count={len(bad_doc)}",
        )
    )

    # E3: policy refund không được chứa cửa sổ sai 14 ngày (sau khi đã fix)
    bad_refund = [
        r
        for r in cleaned_rows
        if r.get("doc_id") == "policy_refund_v4"
        and "14 ngày làm việc" in (r.get("chunk_text") or "")
    ]
    ok3 = len(bad_refund) == 0
    results.append(
        ExpectationResult(
            "refund_no_stale_14d_window",
            ok3,
            "halt",
            f"violations={len(bad_refund)}",
        )
    )

    # E4: chunk_text đủ dài
    short = [r for r in cleaned_rows if len((r.get("chunk_text") or "")) < 8]
    ok4 = len(short) == 0
    results.append(
        ExpectationResult(
            "chunk_min_length_8",
            ok4,
            "warn",
            f"short_chunks={len(short)}",
        )
    )

    # E5: effective_date đúng định dạng ISO sau clean (phát hiện parser lỏng)
    iso_bad = [
        r
        for r in cleaned_rows
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", (r.get("effective_date") or "").strip())
    ]
    ok5 = len(iso_bad) == 0
    results.append(
        ExpectationResult(
            "effective_date_iso_yyyy_mm_dd",
            ok5,
            "halt",
            f"non_iso_rows={len(iso_bad)}",
        )
    )

    # E6: không còn marker phép năm cũ 10 ngày trên doc HR (conflict version sau clean)
    bad_hr_annual = [
        r
        for r in cleaned_rows
        if r.get("doc_id") == "hr_leave_policy"
        and "10 ngày phép năm" in (r.get("chunk_text") or "")
    ]
    ok6 = len(bad_hr_annual) == 0
    results.append(
        ExpectationResult(
            "hr_leave_no_stale_10d_annual",
            ok6,
            "halt",
            f"violations={len(bad_hr_annual)}",
        )
    )

    # E7: cleaned export phải còn đủ các nguồn mà grading chính thức yêu cầu.
    present_doc_ids = {r.get("doc_id") for r in cleaned_rows}
    missing_doc_ids = sorted(REQUIRED_GRADING_DOC_IDS - present_doc_ids)
    ok7 = len(missing_doc_ids) == 0
    results.append(
        ExpectationResult(
            "required_grading_doc_ids_present",
            ok7,
            "halt",
            f"missing_doc_ids={missing_doc_ids}",
        )
    )

    # E8: access_control_sop phải có fact Level 4 Admin Access cho gq_d10_10.
    acl_level4 = [
        r
        for r in cleaned_rows
        if r.get("doc_id") == "access_control_sop"
        and "Level 4 Admin Access" in (r.get("chunk_text") or "")
        and "IT Manager" in (r.get("chunk_text") or "")
        and "CISO" in (r.get("chunk_text") or "")
    ]
    ok8 = len(acl_level4) >= 1
    results.append(
        ExpectationResult(
            "access_control_level4_fact_present",
            ok8,
            "halt",
            f"matching_rows={len(acl_level4)}",
        )
    )

    # E9: không publish chunk bị đánh dấu mơ hồ / nhiễu ingest.
    noisy = [
        r
        for r in cleaned_rows
        if (r.get("chunk_text") or "").startswith("Nội dung không rõ ràng:")
        or (r.get("chunk_text") or "").startswith("!!!")
    ]
    ok9 = len(noisy) == 0
    results.append(
        ExpectationResult(
            "no_ambiguous_or_noisy_chunks",
            ok9,
            "halt",
            f"violations={len(noisy)}",
        )
    )

    # E10: lỗi sync lặp cụm "làm việc" phải được normalize trước khi embed.
    repeated_workday = [
        r
        for r in cleaned_rows
        if re.search(r"(làm việc)(?:\s+làm việc)+", r.get("chunk_text") or "", re.IGNORECASE)
    ]
    ok10 = len(repeated_workday) == 0
    results.append(
        ExpectationResult(
            "no_repeated_lam_viec_phrase",
            ok10,
            "halt",
            f"violations={len(repeated_workday)}",
        )
    )

    halt = any(not r.passed and r.severity == "halt" for r in results)
    return results, halt
