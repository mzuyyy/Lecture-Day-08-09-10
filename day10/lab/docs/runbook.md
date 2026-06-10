# Runbook — Lab Day 10 (incident tối giản)

---

## Symptom

User hoặc agent trả lời bằng dữ liệu stale/sai version, ví dụ:

- Trả lời chính sách hoàn tiền là `14 ngày làm việc` thay vì `7 ngày làm việc`.
- Trả lời HR dưới 3 năm kinh nghiệm là `10 ngày phép năm` thay vì `12 ngày phép năm`.
- Không trả lời được escalation P1 `10 phút` dù top-1 document đúng `sla_p1_2026`.
- Retrieval context lấy đúng `doc_id` nhưng `hits_forbidden=yes` trong eval.

---

## Detection

Các tín hiệu chính:

- Log pipeline có expectation `FAIL`, đặc biệt `refund_no_stale_14d_window`, `hr_leave_no_stale_10d_annual`, `required_grading_doc_ids_present`.
- Eval CSV có `contains_expected=no`, `hits_forbidden=yes`, hoặc `top1_doc_expected=no`.
- Grading JSONL có `contains_expected=false`, `hits_forbidden=true`, hoặc `top1_doc_matches=false`.
- Manifest freshness có `freshness_check=FAIL` khi `latest_exported_at` vượt SLA.

---

## Diagnosis

| Bước | Việc làm | Kết quả mong đợi |
|------|----------|------------------|
| 1 | Kiểm tra `artifacts/logs/run_<run_id>.log` | Có `raw_records`, `cleaned_records`, `quarantine_records`, expectation pass/fail và `PIPELINE_OK` hoặc halt |
| 2 | Kiểm tra `artifacts/manifests/manifest_<run_id>.json` | Xác nhận đúng `cleaned_csv`, `chroma_collection`, `latest_exported_at`, flag `no_refund_fix/skipped_validate` nếu inject |
| 3 | Mở `artifacts/quarantine/quarantine_<run_id>.csv` | Biết record bị loại vì `unknown_doc_id`, stale HR, missing date/text, duplicate, noisy |
| 4 | Chạy `python eval_retrieval.py --out artifacts/eval/debug_eval.csv` | Xem câu nào `contains_expected=no`, `hits_forbidden=yes`, hoặc `top1_doc_expected=no` |
| 5 | Chạy `python grading_run.py --out artifacts/eval/grading_run.jsonl` | Xác nhận 10 câu grading chính thức pass/fail sau khi publish |

---

## Mitigation

Nếu expectation halt:

1. Không dùng `--skip-validate` cho run production.
2. Sửa source hoặc cleaning rule tương ứng.
3. Rerun pipeline chuẩn:

```powershell
$env:PYTHONUTF8='1'
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
python etl_pipeline.py run --run-id fix-<issue>
python grading_run.py --out artifacts/eval/grading_run.jsonl
```

Nếu đã lỡ publish dữ liệu xấu, rerun pipeline chuẩn sẽ upsert cleaned snapshot và prune vector id cũ. Nếu freshness `FAIL` do snapshot quá cũ, hiển thị cảnh báo data stale hoặc yêu cầu export mới từ source system trước khi publish.

---

## Prevention

Các guardrail đang áp dụng:

- Allowlist `doc_id` và expectation `required_grading_doc_ids_present`.
- Halt nếu refund còn `14 ngày làm việc` hoặc HR còn `10 ngày phép năm`.
- Halt nếu chunk noisy/mơ hồ hoặc effective_date không ISO.
- Eval/grading sau mỗi publish để bắt lỗi retrieval trước khi agent dùng context.
- Freshness check trên manifest để phát hiện snapshot quá SLA.

Việc nên làm tiếp: đưa `FRESHNESS_SLA_HOURS` và danh sách canonical doc id vào contract/env thay vì hard-code, thêm alert CI cho `grading_run.jsonl`, và cân nhắc pydantic/Great Expectations để validate schema cleaned chặt hơn.
