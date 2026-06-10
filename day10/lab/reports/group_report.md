# Báo Cáo Nhóm — Lab Day 10: Data Pipeline & Data Observability

**MSV:** 2A202600736

**Tên:** Mai Ngọc Duy  

**Ngày nộp:** 2026-06-10  

**Repo:** Lecture-Day-08-09-10

---

## 1. Pipeline tổng quan

Pipeline dùng raw export mẫu `data/raw/policy_export_dirty.csv`, mô phỏng dữ liệu từ policy, IT SLA, IT helpdesk, HR và access control. Luồng chạy là ingest CSV, clean/quarantine từng record, validate bằng expectation suite, publish cleaned snapshot vào Chroma collection `day10_kb`, sau đó chạy eval/grading. Mỗi run có `run_id` trong log, manifest, cleaned/quarantine CSV và metadata vector. Run chính cho Sprint 3/Sprint 4 là `sprint3-good`; run inject để tạo bằng chứng dữ liệu xấu là `sprint3-bad`.

Lệnh chạy chuẩn:

```powershell
$env:PYTHONUTF8='1'; $env:HF_HUB_OFFLINE='1'; $env:TRANSFORMERS_OFFLINE='1'; python etl_pipeline.py run --run-id sprint3-good
python grading_run.py --out artifacts/eval/grading_run.jsonl
```

Artifact chính: `artifacts/logs/run_sprint3-good.log`, `artifacts/manifests/manifest_sprint3-good.json`, `artifacts/eval/grading_run.jsonl`.

---

## 2. Cleaning & expectation

Nhóm cập nhật allowlist để nhận `access_control_sop`, thêm rule loại HR 2025 còn text `10 ngày phép năm`, loại chunk noisy/mơ hồ, normalize lỗi lặp cụm `làm việc`, và enrich context P1 escalation để tránh retrieve nhầm chunk P2. Expectation mới gồm kiểm đủ doc id grading, kiểm fact Level 4 Access, không publish noisy chunk, và không còn lặp `làm việc`. Các expectation quan trọng dùng severity `halt`; `chunk_min_length_8` là `warn`.

### 2a. Bảng metric_impact

| Rule / Expectation mới | Trước / khi inject | Sau | Chứng cứ |
|------------------------|--------------------|-----|----------|
| `access_control_sop` allowlist + `required_grading_doc_ids_present` | Baseline thiếu source này sẽ quarantine nhầm và không pass `gq_d10_10` | `missing_doc_ids=[]`, `gq_d10_10 top1_doc_matches=true` | `artifacts/logs/run_sprint3-good.log`, `artifacts/eval/grading_run.jsonl` |
| `stale_hr_2025_10d_policy_text` | Raw có nhiều row HR 2025 `10 ngày phép năm` | `hr_leave_no_stale_10d_annual OK :: violations=0`, `gq_d10_09 hits_forbidden=false` | `artifacts/logs/run_sprint3-good.log`, `artifacts/eval/grading_run.jsonl` |
| `ambiguous_or_noisy_chunk_text` | Raw có chunk bắt đầu bằng `Nội dung không rõ ràng:` hoặc `!!!` | `no_ambiguous_or_noisy_chunks OK :: violations=0` | `artifacts/logs/run_sprint3-good.log` |
| `refund_no_stale_14d_window` | Inject `sprint3-bad`: `FAIL :: violations=1`; eval `q_refund_window hits_forbidden=yes` | `sprint3-good`: `OK :: violations=0`; eval `hits_forbidden=no` | `artifacts/logs/run_sprint3-bad.log`, `artifacts/eval/sprint3_bad_eval.csv`, `artifacts/eval/sprint3_good_eval.csv` |
| `p1_escalation_context` | `gq_d10_06` từng `contains_expected=false` dù top1 doc đúng | `gq_d10_06 contains_expected=true`, `top1_doc_matches=true` | `artifacts/eval/grading_run.jsonl` |

Ví dụ expectation fail: khi chạy `python etl_pipeline.py run --run-id sprint3-bad --no-refund-fix --skip-validate`, log ghi `refund_no_stale_14d_window FAIL :: violations=1`. Run này cố tình embed dữ liệu lỗi để tạo before evidence. Sau khi chạy lại pipeline chuẩn, expectation này pass.

---

## 3. Before / after ảnh hưởng retrieval hoặc agent

Sprint 3 dùng corruption inject bằng flag `--no-refund-fix`, tức là không sửa chunk stale của `policy_refund_v4` từ `14 ngày làm việc` sang `7 ngày làm việc`. Vì thêm `--skip-validate`, pipeline vẫn publish snapshot xấu để đo tác động retrieval.

Before artifact: `artifacts/eval/sprint3_bad_eval.csv`. Dòng `q_refund_window` có `top1_doc_id=policy_refund_v4`, nhưng `top1_preview` chứa `14 ngày làm việc` và `hits_forbidden=yes`. Đây là tình huống nguy hiểm vì document id đúng nhưng context sai version.

After artifact: `artifacts/eval/sprint3_good_eval.csv`. Cùng câu `q_refund_window` chuyển sang preview `7 ngày làm việc`, `contains_expected=yes`, `hits_forbidden=no`, `top1_doc_expected=yes`. Grading chính thức sau run tốt nằm ở `artifacts/eval/grading_run.jsonl`; 10/10 câu có `contains_expected=true`, `hits_forbidden=false`, và `top1_doc_matches=true` với các câu có expected doc id.

---

## 4. Freshness & monitoring

Freshness dùng `latest_exported_at` trong manifest và SLA mặc định `FRESHNESS_SLA_HOURS=24`. Với dữ liệu mẫu, cả `sprint3-bad` và `sprint3-good` đều `freshness_check=FAIL` vì `latest_exported_at=2026-04-11T00:00:00`, age khoảng 1448 giờ, vượt SLA 24 giờ. Đây là kết quả hợp lý cho snapshot lab cũ, không phải lỗi cleaning. Trong production, `FAIL` nghĩa là cần export mới hoặc tạm cảnh báo agent/user rằng knowledge base có thể stale.

PASS nghĩa là snapshot còn trong SLA; WARN có thể dùng nếu hệ thống mở rộng thêm ngưỡng gần quá hạn; FAIL nghĩa là không nên publish hoặc cần escalation cho Data Owner.

---

## 5. Liên hệ Day 09


---

## 6. Rủi ro còn lại & việc chưa làm

- `freshness_check=FAIL` do dữ liệu mẫu cũ; cần export thật hoặc SLA riêng cho demo.
- Eval hiện là retrieval + keyword, chưa có LLM judge.
- Expectation suite là custom Python, chưa tích hợp Great Expectations/pydantic.
- Danh sách canonical doc id vẫn nằm trong code; nên chuyển sang contract/env nếu mở rộng nhiều nguồn.
