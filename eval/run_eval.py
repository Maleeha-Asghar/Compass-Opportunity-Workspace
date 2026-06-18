import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Any

from agents.extraction_agent import OpportunityExtractionAgent
from agents.source_verification_agent import SourceVerificationAgent
from tools.supabase_tool import SupabaseRepository


def load_cases(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    candidate = {
        "source_url": f"https://eval.local/{case['id']}",
        "source_title": case["id"],
        "title": case["id"],
        "page_text": case["source_text"],
        "source_tier": "A",
        "content_type": "html",
        "snippet": "",
    }
    extracted = OpportunityExtractionAgent().extract(candidate)
    verification = SourceVerificationAgent().verify(extracted, candidate)
    expected = case["expected"]

    checks = []
    if "title_contains" in expected:
        checks.append(expected["title_contains"].lower() in extracted["title"].lower())
    for field in ("country", "funding_type", "deadline", "payment_requested"):
        if field in expected:
            checks.append(extracted.get(field) == expected[field])

    hallucination_flags = []
    for field in ("contact_email", "country", "funding_type"):
        value = extracted.get(field)
        if value and str(value).lower() not in case["source_text"].lower():
            hallucination_flags.append(field)

    return {
        "id": case["id"],
        "accuracy": sum(checks) / len(checks) if checks else 1.0,
        "hallucination_count": len(hallucination_flags),
        "hallucination_flags": hallucination_flags,
        "trust_level": verification["trust_level"],
        "extracted": extracted,
    }


def run_eval(path: Path, output_path: Path | None = None, resume: bool = False) -> dict[str, Any]:
    cases = load_cases(path)
    results: list[dict[str, Any]] = []
    completed_ids: set[str] = set()
    if resume and output_path and output_path.exists():
        previous = json.loads(output_path.read_text(encoding="utf-8"))
        results = previous.get("results", [])
        completed_ids = {item["id"] for item in results}

    for case in cases:
        if case["id"] in completed_ids:
            continue
        results.append(evaluate_case(case))
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(_build_report(results), indent=2), encoding="utf-8")
    return _build_report(results)


def _build_report(results: list[dict[str, Any]]) -> dict[str, Any]:
    hallucination_rate = mean(1.0 if item["hallucination_count"] else 0.0 for item in results) if results else 0.0
    return {
        "case_count": len(results),
        "extraction_accuracy": mean(item["accuracy"] for item in results) if results else 0.0,
        "hallucination_rate": hallucination_rate,
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Compass extraction evals.")
    parser.add_argument("--golden-set", default="eval/golden_set/sample_opportunities.json")
    parser.add_argument("--output", default="eval/latest_eval_report.json")
    parser.add_argument("--resume", action="store_true", help="Resume from --output if it already has completed cases.")
    parser.add_argument("--save", action="store_true", help="Persist aggregate metrics to Supabase eval_runs.")
    args = parser.parse_args()

    report = run_eval(Path(args.golden_set), output_path=Path(args.output), resume=args.resume)
    print(json.dumps(report, indent=2))

    if args.save:
        SupabaseRepository().save_eval_run(
            {
                "model_name": "mistral-extraction-eval",
                "extraction_accuracy": report["extraction_accuracy"],
                "hallucination_rate": report["hallucination_rate"],
                "notes": f"{report['case_count']} golden-set cases",
            }
        )


if __name__ == "__main__":
    main()
