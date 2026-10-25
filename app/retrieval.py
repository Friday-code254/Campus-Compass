"""Transparent TF-IDF cosine retrieval with no external vector database."""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from .db import connect

TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)
STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "but", "by", "can", "do", "does",
    "for", "from", "had", "has", "have", "how", "i", "in", "is", "it", "of", "on", "or",
    "our", "should", "the", "their", "this", "to", "we", "what", "when", "where", "which",
    "who", "will", "with", "you", "your",
}
NORMALIZATION = {
    "attendance": "attend", "attending": "attend", "attended": "attend",
    "percentage": "percent", "percentages": "percent", "percent": "percent",
    "advisor": "advise", "adviser": "advise", "advising": "advise", "advice": "advise",
    "appointment": "appointment", "appointments": "appointment",
    "renewal": "renew", "renewals": "renew", "renewed": "renew", "renewing": "renew",
    "laboratory": "laboratory", "laboratories": "laboratory", "lab": "laboratory", "labs": "laboratory",
    "weekday": "weekday", "weekdays": "weekday", "weekend": "weekend", "weekends": "weekend",
    "close": "close", "closes": "close", "closed": "close", "closing": "close",
    "exam": "exam", "exams": "exam", "examination": "exam", "examinations": "exam",
    "required": "require", "requires": "require", "requirement": "require", "requirements": "require",
    "career": "career", "careers": "career", "review": "review", "reviews": "review",
    "class": "class", "classes": "class", "appeals": "appeal",
    "meeting": "meet", "meetings": "meet",
}

# Words that describe the requested response format rather than the evidence.
# They still participate in ranking; they are omitted only from the coverage
# gate so a request such as "list the hours" does not require "list" to appear
# in the source document.
COVERAGE_INTENT_TERMS = {"list"}


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for match in TOKEN_RE.findall(text):
        token = match.lower()
        if token in STOP_WORDS:
            continue
        token = NORMALIZATION.get(token, token)
        if token not in NORMALIZATION.values():
            if len(token) > 5 and token.endswith("ing"):
                token = token[:-3]
                if len(token) > 2 and token[-1] == token[-2]:
                    token = token[:-1]
            elif len(token) > 4 and token.endswith("ies"):
                token = token[:-3] + "y"
            elif len(token) > 4 and token.endswith("ed"):
                token = token[:-2]
            elif len(token) > 4 and token.endswith("s") and not token.endswith("ss"):
                token = token[:-1]
        tokens.append(token)
    return tokens


def tfidf_vectors(texts: list[str]) -> tuple[list[dict[str, float]], dict[str, float]]:
    counters = [Counter(tokenize(text)) for text in texts]
    document_frequency: Counter[str] = Counter()
    for counter in counters:
        document_frequency.update(counter.keys())
    count = max(len(counters), 1)
    idf = {term: math.log((count + 1) / (frequency + 1)) + 1 for term, frequency in document_frequency.items()}
    vectors: list[dict[str, float]] = []
    for counter in counters:
        vector = {term: (1 + math.log(freq)) * idf[term] for term, freq in counter.items()}
        norm = math.sqrt(sum(weight * weight for weight in vector.values()))
        vectors.append({term: weight / norm for term, weight in vector.items()} if norm else {})
    return vectors, idf


def rank_records(question: str, records: list[dict[str, Any]], top_k: int = 4) -> list[dict[str, Any]]:
    if not records:
        return []
    corpus = [record["retrieval_text"] for record in records]
    vectors, idf = tfidf_vectors(corpus)
    query_counts = Counter(tokenize(question))
    query = {term: (1 + math.log(freq)) * idf[term] for term, freq in query_counts.items() if term in idf}
    query_norm = math.sqrt(sum(weight * weight for weight in query.values()))
    if not query_norm:
        return []
    query = {term: weight / query_norm for term, weight in query.items()}

    results: list[dict[str, Any]] = []
    for row, vector in zip(records, vectors):
        score = sum(weight * vector.get(term, 0.0) for term, weight in query.items())
        if score <= 0:
            continue
        # The model receives the retrieved text with its document and section
        # labels. Measure coverage against that same evidence, while excluding
        # request-format words such as "list" from the denominator.
        evidence_terms = set(tokenize(row.get("retrieval_text", row.get("body", row.get("text", "")))))
        query_terms = set(query_counts) - COVERAGE_INTENT_TERMS
        coverage = len(evidence_terms & query_terms) / len(query_terms) if query_terms else 0.0
        results.append(
            {
                **row,
                "chunk_id": row.get("id", row.get("chunk_id")),
                "text": row.get("body", row.get("text", "")),
                "score": score,
                "query_coverage": coverage,
            }
        )
    return sorted(results, key=lambda item: item["score"], reverse=True)[:top_k]


def retrieve(question: str, top_k: int = 4) -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            """SELECT c.id, c.document_id, d.filename, c.page_number, c.section,
                      c.body, c.retrieval_text
               FROM chunks c JOIN documents d ON d.id = c.document_id"""
        ).fetchall()
    return rank_records(question, [dict(row) for row in rows], top_k)

