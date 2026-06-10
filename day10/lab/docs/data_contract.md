# Data contract — Lab Day 10

> Bắt đầu từ `contracts/data_contract.yaml` — mở rộng và đồng bộ file này.

---

## 1. Nguồn dữ liệu (source map)

| Nguồn | Phương thức ingest | Failure mode chính | Metric / alert |
|-------|-------------------|-------------------|----------------|
| `policy_refund_v4` | CSV export từ policy/CS system (`data/raw/policy_export_dirty.csv`) | Stale refund window còn ghi `14 ngày làm việc`; duplicate chunk; lỗi sync lặp cụm `làm việc` | `refund_window_current_policy` phải pass; `hits_forbidden=14 ngày` trong eval phải là `no`; đếm quarantine/fix stale refund trong log |
| `hr_leave_policy` | CSV export từ HR policy system | Xung đột version HR 2025 vs 2026: text `10 ngày phép năm` hoặc `effective_date < 2026-01-01` | `no_stale_hr_2025_10d_policy_text`; `gq_d10_09` phải `contains_expected=true`, `hits_forbidden=false`; số dòng quarantine reason `stale_hr_*` |
| `access_control_sop` | CSV export từ IAM/access workflow | Source hợp lệ bị thiếu allowlist dẫn đến `unknown_doc_id`; missing fact Level 4 approval | `required_grading_doc_ids_present`; `access_control_level4_fact_present`; `gq_d10_10` top-1 phải là `access_control_sop` |
| `sla_p1_2026` | CSV export từ incident/SLA system | Retrieval lấy nhầm chunk P2 escalation thay vì P1 escalation `10 phút`; noisy chunk `!!!` | `gq_d10_06` phải chứa `10 phút`; `no_ambiguous_or_noisy_chunks`; theo dõi top-k preview trong eval/grading |

---

## 2. Schema cleaned

| Cột | Kiểu | Bắt buộc | Ghi chú |
|-----|------|----------|---------|
| chunk_id | string | Có | Id stable sinh từ `doc_id`, `chunk_text`, `seq`; dùng làm Chroma id để upsert/prune |
| doc_id | string | Có | Phải thuộc allowlist: `policy_refund_v4`, `sla_p1_2026`, `it_helpdesk_faq`, `hr_leave_policy`, `access_control_sop` |
| chunk_text | string | Có | Text đã normalize; không được rỗng, không chứa marker noisy `Nội dung không rõ ràng:` hoặc `!!!` |
| effective_date | date | Có | Chuẩn ISO `YYYY-MM-DD`; DMY slash được normalize, format không parse được thì quarantine |
| exported_at | datetime | Có | Timestamp export từ source; dùng để tính `latest_exported_at` trong manifest/freshness |

---

## 3. Quy tắc quarantine vs drop

Record lỗi được ghi vào `artifacts/quarantine/quarantine_<run_id>.csv` cùng `reason`, không embed vào Chroma. Không drop im lặng, trừ trường hợp snapshot prune vector cũ sau khi cleaned set thay đổi.

Các nhóm quarantine chính:

- `unknown_doc_id`: source chưa đăng ký trong allowlist hoặc export lỗi.
- `missing_effective_date`, `invalid_effective_date_format`: không đủ căn cứ versioning.
- `stale_hr_policy_effective_date`, `stale_hr_2025_10d_policy_text`: HR 2025 không được publish cho policy 2026.
- `missing_chunk_text`, `ambiguous_or_noisy_chunk_text`: thiếu/nhiễu nội dung.
- `duplicate_chunk_text`: dedupe giữ bản đầu tiên trong cleaned snapshot.

Owner duyệt merge lại: Cleaning & Quality Owner kiểm tra source gốc, cập nhật allowlist/contract nếu là source hợp lệ, rồi rerun pipeline. Nếu là dữ liệu thật bị sai, sửa ở source system trước khi export lại.

---

## 4. Phiên bản & canonical

Canonical source cho các policy trong lab là raw export sau khi được đối chiếu với tài liệu tham khảo trong `data/docs/` và expectation suite:

- Refund hiện hành: `policy_refund_v4`, cửa sổ yêu cầu hoàn tiền là `7 ngày làm việc`; chunk `14 ngày làm việc` là stale và phải được fix/quarantine trước khi publish.
- HR hiện hành: `hr_leave_policy` với `effective_date >= 2026-01-01`; nhân viên dưới 3 năm kinh nghiệm là `12 ngày phép năm`, không dùng bản HR 2025 `10 ngày phép năm`.
- SLA hiện hành: `sla_p1_2026`, P1 first response `15 phút`, resolution `4 giờ`, escalation `10 phút`.
- Access control: `access_control_sop`, Level 4 Admin Access cần `IT Manager` và `CISO`.

Manifest `artifacts/manifests/manifest_<run_id>.json` là bản ghi publish snapshot: `run_id`, `cleaned_csv`, `chroma_collection`, `latest_exported_at`, và trạng thái freshness.
