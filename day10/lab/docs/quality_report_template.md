# Quality report — Lab Day 10

**run_id:** `sprint3-bad` / `sprint3-good`  
**Ngày:** 2026-06-10

---

## 1. Tóm tắt số liệu

| Chỉ số | Trước | Sau | Ghi chú |
|--------|-------|-----|---------|
| raw_records | 247 | 247 | Cùng raw export `data/raw/policy_export_dirty.csv` |
| cleaned_records | 36 | 36 | Số dòng publish giữ nguyên; khác biệt nằm ở nội dung refund stale có được fix hay không |
| quarantine_records | 211 | 211 | Các rule quarantine chạy giống nhau trong hai run |
| Expectation halt? | Có: `refund_no_stale_14d_window FAIL`, `violations=1` | Không: tất cả expectation `OK` | Run xấu dùng `--skip-validate` để cố tình vẫn embed dữ liệu lỗi cho Sprint 3 |

---

## 2. Before / after retrieval (bắt buộc)

File before/after:

- Before: `artifacts/eval/sprint3_bad_eval.csv`
- After: `artifacts/eval/sprint3_good_eval.csv`

**Câu hỏi then chốt:** refund window (`q_refund_window`)  

**Trước:** `top1_doc_id=policy_refund_v4`, `top1_preview=Yêu cầu hoàn tiền được chấp nhận trong vòng 14 ngày làm việc kể từ xác nhận đơn.`, `contains_expected=yes`, `hits_forbidden=yes`, `top1_doc_expected=yes`

**Sau:** `top1_doc_id=policy_refund_v4`, `top1_preview=Yêu cầu được gửi trong vòng 7 ngày làm việc kể từ thời điểm xác nhận đơn hàng.`, `contains_expected=yes`, `hits_forbidden=no`, `top1_doc_expected=yes`

Kết luận: before nhìn có vẻ vẫn retrieve đúng document, nhưng context còn chứa chính sách stale `14 ngày`, nên `hits_forbidden=yes`. Sau khi bật rule fix refund window, top-k không còn chứa forbidden phrase và câu hỏi pass.

**Merit (khuyến nghị):** versioning HR — `q_hr_annual_leave_under3`

**Trước:** `top1_doc_id=hr_leave_policy`, `top1_preview=Nhân viên dưới 3 năm kinh nghiệm được 12 ngày phép năm theo chính sách 2026.`, `contains_expected=yes`, `hits_forbidden=no`, `top1_doc_expected=yes`

**Sau:** `top1_doc_id=hr_leave_policy`, `top1_preview=Nhân viên dưới 3 năm kinh nghiệm được 12 ngày phép năm theo chính sách 2026.`, `contains_expected=yes`, `hits_forbidden=no`, `top1_doc_expected=yes`

Kết luận: HR stale data đã được xử lý ổn định ở cả hai run vì corruption Sprint 3 chỉ tắt refund fix, không tắt rule quarantine HR 2025.

---

## 3. Freshness & monitor

Kết quả freshness ở cả hai run là `FAIL`:

- `sprint3-bad`: `latest_exported_at=2026-04-11T00:00:00`, `age_hours=1448.638`, `sla_hours=24.0`, `reason=freshness_sla_exceeded`
- `sprint3-good`: `latest_exported_at=2026-04-11T00:00:00`, `age_hours=1448.664`, `sla_hours=24.0`, `reason=freshness_sla_exceeded`

Giải thích: dữ liệu lab là snapshot mẫu có timestamp cũ hơn SLA 24 giờ, nên freshness `FAIL` là đúng theo monitoring. Đây không phải lỗi cleaning/retrieval; nếu chạy trên export thật, SLA này dùng để cảnh báo snapshot quá cũ trước khi publish cho agent.

---

## 4. Corruption inject (Sprint 3)

Kịch bản inject:

```powershell
$env:PYTHONUTF8='1'
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
python etl_pipeline.py run --run-id sprint3-bad --no-refund-fix --skip-validate
python eval_retrieval.py --out artifacts/eval/sprint3_bad_eval.csv
```

`--no-refund-fix` cố tình không sửa chunk stale trong `policy_refund_v4` từ `14 ngày làm việc` về `7 ngày làm việc`. Expectation phát hiện bằng `refund_no_stale_14d_window FAIL :: violations=1`. Vì có `--skip-validate`, pipeline vẫn embed để tạo bằng chứng retrieval xấu.

Run phục hồi:

```powershell
python etl_pipeline.py run --run-id sprint3-good
python eval_retrieval.py --out artifacts/eval/sprint3_good_eval.csv
```

Run tốt có `refund_no_stale_14d_window OK :: violations=0`, `PIPELINE_OK`, và eval `q_refund_window` đổi từ `hits_forbidden=yes` sang `hits_forbidden=no`.

---

## 5. Hạn chế & việc chưa làm

- `freshness_check=FAIL` do timestamp dữ liệu mẫu cũ; cần ghi rõ trong runbook hoặc chỉnh SLA/timestamp nếu demo môi trường production.
- Eval retrieval dùng keyword/top-k, chưa có LLM judge để đánh giá câu trả lời tự nhiên.
- Một số câu trong `test_questions.json` vẫn có ranking chưa tối ưu ở top-1, ví dụ P1 first response có thể preview chunk P2 trong eval top-3; bộ grading chính thức đã pass sau khi enrich context P1.
- Chưa tích hợp Great Expectations hoặc pydantic schema thật; expectation hiện là custom Python.
