"""Score retrieval coverage and abstention on the included labeled questions."""

from __future__ import annotations

import json
from pathlib import Path

from app.config import MIN_QUERY_COVERAGE, MIN_RETRIEVAL_SCORE, PROJECT_ROOT, TOP_K
from app.ingestion import make_chunks, parse_document
from app.retrieval import rank_records


def load_sample_chunks() -> list[dict[str, object]]:
    chunks: list[dict[str, object]] = []
    for path in sorted((PROJECT_ROOT / "data" / "sample_docs").glob("*.md")):
        pages = parse_document(path.name, path.read_bytes())
        chunks.extend(make_chunks(path.name, pages))
    return chunks


def main() -> None:
    dataset_path = PROJECT_ROOT / "evals" / "dataset.json"
    questions = json.loads(dataset_path.read_text(encoding="utf-8"))
    chunks = load_sample_chunks()
    report: list[dict[str, object]] = []
    answerable = [item for item in questions if item["answerable"]]
    unanswerable = [item for item in questions if not item["answerable"]]
    hits_at_1 = hits_at_k = covered = correct_abstentions = 0

    print(
        f"TF-IDF retrieval evaluation | k={TOP_K} | score cutoff={MIN_RETRIEVAL_SCORE:.3f} "
        f"| term coverage cutoff={MIN_QUERY_COVERAGE:.2f}\n"
    )
    for item in questions:
        ranked = rank_records(item["question"], chunks, TOP_K)
        best_score = float(ranked[0]["score"]) if ranked else 0.0
        best_coverage = float(ranked[0]["query_coverage"]) if ranked else 0.0
        predicted_answerable = best_score >= MIN_RETRIEVAL_SCORE and best_coverage >= MIN_QUERY_COVERAGE
        top_files = list(dict.fromkeys(str(row["filename"]) for row in ranked))
        expected = item["expected_document"]

        if item["answerable"]:
            hit = expected in top_files
            hits_at_k += int(hit)
            hits_at_1 += int(bool(ranked) and ranked[0]["filename"] == expected)
            covered += int(predicted_answerable)
            outcome = "retrieved" if hit else "wrong source"
            if not predicted_answerable:
                outcome += "; abstained"
        else:
            correct_abstentions += int(not predicted_answerable)
            outcome = "correct abstention" if not predicted_answerable else "false match"

        report.append(
            {
                "id": item["id"],
                "question": item["question"],
                "answerable": item["answerable"],
                "expected_document": expected,
                "top_documents": top_files,
                "top_score": round(best_score, 4),
                "top_query_coverage": round(best_coverage, 4),
                "predicted_answerable": predicted_answerable,
                "outcome": outcome,
            }
        )
        expected_label = expected or "—"
        print(
            f"{item['id']:<24} {outcome:<28} score={best_score:.3f} "
            f"coverage={best_coverage:.2f} expected={expected_label}"
        )

    count_answerable = len(answerable)
    count_unanswerable = len(unanswerable)
    summary = {
        "question_count": len(questions),
        "top_k": TOP_K,
        "minimum_retrieval_score": MIN_RETRIEVAL_SCORE,
        "minimum_query_coverage": MIN_QUERY_COVERAGE,
        "recall_at_1": hits_at_1 / count_answerable if count_answerable else 0.0,
        "recall_at_k": hits_at_k / count_answerable if count_answerable else 0.0,
        "answerable_coverage": covered / count_answerable if count_answerable else 0.0,
        "unanswerable_abstention_rate": correct_abstentions / count_unanswerable if count_unanswerable else 0.0,
    }
    print("\nSummary")
    print(f"  Recall@1 on answerable questions:       {summary['recall_at_1']:.1%}")
    print(f"  Recall@{TOP_K} on answerable questions: {summary['recall_at_k']:.1%}")
    print(f"  Answerable question coverage:          {summary['answerable_coverage']:.1%}")
    print(f"  Abstention on unanswerable questions:  {summary['unanswerable_abstention_rate']:.1%}")
    print("\nThese scores measure retrieval behavior, not generated-answer correctness.")

    report_path = PROJECT_ROOT / "evals" / "report.json"
    report_path.write_text(
        json.dumps({"summary": summary, "questions": report}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Detailed report saved to {report_path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()

