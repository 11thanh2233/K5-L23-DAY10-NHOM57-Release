#!/usr/bin/env python3
"""Score a student error list against ground truth from an injector.

Both files use the same list. Only type and target are compared.
Extra keys on a truth item are ignored.

  python scripts/score_findings.py --run runs/s11
  python scripts/score_findings.py --truth runs/s11/_private/truth.json --errors runs/s11/errors.json
  python scripts/score_findings.py --run runs/s93751 --run runs/p93751

Student file:
  {"errors": [{"type": "class_swap", "target": "000000000139"}]}

Ground truth file:
  {"seed": 11, "task": "detection", "errors": [{"type": "class_swap", "target": "000000000139", "unit": "image"}]}
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import metrics  # noqa: E402


def load_errors(path: Path) -> list[dict]:
    document = json.loads(path.read_text(encoding="utf-8"))
    rows = document.get("errors")
    if not isinstance(rows, list):
        raise SystemExit(f"{path} cần khóa errors là một list")
    for row in rows:
        if not isinstance(row, dict) or "type" not in row or "target" not in row:
            raise SystemExit(f"{path} mỗi phần tử cần type và target")
    return rows


def build(truth_path: Path, errors_path: Path) -> dict:
    truth_doc = json.loads(truth_path.read_text(encoding="utf-8"))
    truth_rows = load_errors(truth_path)
    predicted = load_errors(errors_path)
    truth = metrics.pairs(truth_rows)
    pred = metrics.pairs(predicted)
    return {
        "truth": str(truth_path),
        "errors": str(errors_path),
        "task": truth_doc.get("task"),
        "seed": truth_doc.get("seed"),
        "decision": metrics.decision(predicted),
        "error_count": len(predicted),
        "truth_count": len(truth),
        "score": {
            "overall": metrics.score(truth, pred),
            "groups": metrics.group_scores(truth, pred),
            "by_type": metrics.by_type(truth, pred),
        },
    }


def fmt(value) -> str:
    return "—" if value is None else str(value)


def render(report: dict) -> str:
    overall = report["score"]["overall"]
    lines = [
        f"# Score — seed {report.get('seed')} {report.get('task') or ''}".rstrip(),
        "",
        f"- Quyết định từ danh sách nộp: **{report['decision']}**",
        f"- Số lỗi nộp: {report['error_count']}",
        f"- Overall: precision {fmt(overall['precision'])} · recall {fmt(overall['recall'])} · F1 {fmt(overall['f1'])} "
        f"(TP {overall['tp']} / FP {overall['fp']} / FN {overall['fn']})",
        "",
    ]
    for name, row in report["score"]["groups"].items():
        lines.append(
            f"- {name}: precision {fmt(row['precision'])} · recall {fmt(row['recall'])} · F1 {fmt(row['f1'])} "
            f"(TP {row['tp']} / FP {row['fp']} / FN {row['fn']})"
        )
    lines += ["", "| type | group | TP | FP | FN | recall |", "|---|---|---:|---:|---:|---:|"]
    for row in report["score"]["by_type"]:
        lines.append(
            f"| {row['type']} | {row['group']} | {row['tp']} | {row['fp']} | {row['fn']} | {row['recall']} |"
        )
    lines.append("")
    return "\n".join(lines)


def score_run(run: Path) -> dict:
    truth_path = run / "_private" / "truth.json"
    errors_path = run / "errors.json"
    if not truth_path.is_file():
        raise SystemExit(f"Thiếu {truth_path}. Chạy inject trước.")
    if not errors_path.is_file():
        raise SystemExit(f"Thiếu {errors_path}. Ghi danh sách lỗi của nhóm vào file này.")
    report = build(truth_path, errors_path)
    report["run"] = str(run)
    (run / "metrics.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    text = render(report)
    (run / "report.md").write_text(text, encoding="utf-8")
    print(text)
    return report


def rank_line(reports: list[dict]) -> str:
    graded = [report for report in reports if report.get("truth_count", 0) > 0]
    by_task = {report.get("task"): report for report in graded}
    det = by_task.get("detection")
    pan = by_task.get("panoptic")
    if det is None or pan is None:
        return ""
    det_r = det["score"]["groups"].get("reference_or_review", {}).get("recall")
    pan_r = pan["score"]["groups"].get("reference_or_review", {}).get("recall")
    if not isinstance(det_r, float) or not isinstance(pan_r, float):
        return ""
    return f"rank recall = {round((det_r + pan_r) / 2, 4)}  (trung bình label recall detection và panoptic)\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare a student error list with injector ground truth")
    parser.add_argument("--run", action="append", default=[], help="Run directory with _private/truth.json and errors.json")
    parser.add_argument("--truth", help="Ground truth JSON from an injector")
    parser.add_argument("--errors", help="Student JSON with the same errors list")
    args = parser.parse_args()
    reports = []
    if args.run:
        for raw in args.run:
            reports.append(score_run(Path(raw)))
    elif args.truth and args.errors:
        report = build(Path(args.truth), Path(args.errors))
        text = render(report)
        out = Path(args.errors).resolve().parent / "report.md"
        out.write_text(text, encoding="utf-8")
        print(text)
        print(f"wrote {out}")
        reports.append(report)
    else:
        raise SystemExit("Cần --run, hoặc cả --truth và --errors")
    summary = rank_line(reports)
    if summary:
        print(summary, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
