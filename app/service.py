"""Question answering flow: retrieve, abstain when evidence is weak, then answer."""

from __future__ import annotations

import re
from typing import Any

from .config import MIN_QUERY_COVERAGE, MIN_RETRIEVAL_SCORE, TOP_K
from .llm import GenerationError, configured, generate_answer
from .retrieval import retrieve

ABSTENTION = "I couldn't find enough supporting information in the uploaded documents to answer that."
GREETINGS = {
    "hi", "hello", "hey", "hiya", "hi there", "hello there", "hey there",
    "good morning", "good afternoon", "good evening",
}


def answer_question(question: str) -> dict[str, Any]:
    question = question.strip()
    if not question:
        raise ValueError("Enter a question.")

    greeting = re.sub(r"[^a-z\s]", "", question.lower()).strip()
    greeting = re.sub(r"\s+", " ", greeting)
    if greeting in GREETINGS:
        return {
            "answer": "Hi! Ask me about an uploaded document, and I'll find the relevant passage for you.",
            "mode": "greeting",
            "retrieval_score": 0.0,
            "query_coverage": 0.0,
            "sources": [],
        }

    matches = retrieve(question, TOP_K)
    if (
        not matches
        or matches[0]["score"] < MIN_RETRIEVAL_SCORE
        or matches[0]["query_coverage"] < MIN_QUERY_COVERAGE
    ):
        return {
            "answer": ABSTENTION,
            "mode": "abstained",
            "retrieval_score": matches[0]["score"] if matches else 0.0,
            "query_coverage": matches[0]["query_coverage"] if matches else 0.0,
            "sources": [],
        }

    sources = [
        {
            "label": f"S{index}",
            "filename": item["filename"],
            "page_number": item["page_number"],
            "section": item["section"],
            "text": item["text"],
            "score": round(float(item["score"]), 3),
        }
        for index, item in enumerate(matches, start=1)
    ]

    if not configured():
        return {
            "answer": "Relevant passages were found. Configure an LLM endpoint to generate a concise answer; the passages below are available for review.",
            "mode": "retrieval_preview",
            "retrieval_score": round(float(matches[0]["score"]), 3),
            "query_coverage": round(float(matches[0]["query_coverage"]), 3),
            "sources": sources,
        }

    try:
        answer = generate_answer(question, matches)
        mode = "generated"
    except GenerationError:
        answer = "I found relevant passages, but answer generation is temporarily unavailable. You can still review the cited passages below."
        mode = "generation_unavailable"
    return {
        "answer": answer,
        "mode": mode,
        "retrieval_score": round(float(matches[0]["score"]), 3),
        "query_coverage": round(float(matches[0]["query_coverage"]), 3),
        "sources": sources,
    }

