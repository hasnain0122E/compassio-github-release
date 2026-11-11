"""Faithful explanations for a fitted ``[TfidfVectorizer, LogisticRegression]`` pipeline.

The model is linear in its TF-IDF features, so the decomposition is EXACT:

    logit = intercept + sum_i tfidf_i * coef_i,     score = sigmoid(logit)

Each feature's contribution is reported as is. For word-level evidence, each n-gram's
contribution is split equally across its occurrences in the text and, within an occurrence,
equally across the words it spans, so word attributions sum exactly to the feature total. The
n-gram occurrences are re-derived and checked against the vectoriser's own analyser output;
if they differ, word attribution is omitted rather than approximated.
"""

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

import numpy as np

METHOD = (
    "Exact linear decomposition: logit = intercept + sum(tf-idf value x coefficient); "
    "word attributions redistribute each n-gram's contribution equally over its occurrences."
)


@dataclass(frozen=True)
class WordSpan:
    word: str
    start: int
    end: int


@dataclass
class Explanation:
    intercept: float
    logit: float
    score: float
    faithfulness_abs_error: float
    positive_features: list[tuple[str, float]]
    negative_features: list[tuple[str, float]]
    word_attributions: list[tuple[WordSpan, float]]
    word_attribution_available: bool
    nonzero_features: int
    feature_contribution_total: float
    word_contribution_total: float | None


class FeatureNames:
    """Index -> feature name, built once per model (vocabularies are ~100-200k)."""

    def __init__(self, vectorizer: Any) -> None:
        names = np.empty(len(vectorizer.vocabulary_), dtype=object)
        for term, index in vectorizer.vocabulary_.items():
            names[index] = term
        self.names = names


def _occurrences_word(vec: Any, lowered: str) -> tuple[list[str], list[list[WordSpan]]] | None:
    pattern = re.compile(vec.token_pattern)
    tokens = [WordSpan(m.group(), m.start(), m.end()) for m in pattern.finditer(lowered)]
    lo, hi = vec.ngram_range
    grams: list[str] = []
    spans: list[list[WordSpan]] = []
    for n in range(lo, hi + 1):
        for i in range(len(tokens) - n + 1):
            window = tokens[i : i + n]
            grams.append(" ".join(t.word for t in window))
            spans.append(window)
    return grams, spans


def _occurrences_char_wb(vec: Any, lowered: str) -> tuple[list[str], list[list[WordSpan]]] | None:
    lo, hi = vec.ngram_range
    grams: list[str] = []
    spans: list[list[WordSpan]] = []
    for m in re.finditer(r"\S+", lowered):
        span = WordSpan(m.group(), m.start(), m.end())
        w = " " + m.group() + " "
        for n in range(lo, hi + 1):
            offset = 0
            grams.append(w[offset : offset + n])
            spans.append([span])
            while offset + n < len(w):
                offset += 1
                grams.append(w[offset : offset + n])
                spans.append([span])
            if offset == 0:
                break
    return grams, spans


def explain(pipeline: Any, names: FeatureNames, text: str, top_k: int) -> Explanation:
    vec, clf = pipeline.steps[0][1], pipeline.steps[-1][1]
    row = vec.transform([text]).tocsr()
    idx, vals = row.indices, row.data.astype(float)
    coef = clf.coef_[0]
    contrib = vals * coef[idx]
    intercept = float(clf.intercept_[0])
    logit = intercept + float(contrib.sum())
    decomposed = 1.0 / (1.0 + math.exp(-logit))
    # The reported score is the model's own output; the decomposition is checked against it.
    model_score = float(pipeline.predict_proba([text])[0, 1])
    order = np.argsort(-contrib, kind="stable")
    feats = [(str(names.names[idx[i]]), float(contrib[i])) for i in order]
    positive = [f for f in feats if f[1] > 0][:top_k]
    negative = sorted((f for f in feats if f[1] < 0), key=lambda f: f[1])[:top_k]

    words, available = _word_attributions(vec, text, dict(feats))
    return Explanation(
        intercept=intercept,
        logit=logit,
        score=model_score,
        faithfulness_abs_error=abs(decomposed - model_score),
        positive_features=positive,
        negative_features=negative,
        word_attributions=words,
        word_attribution_available=available,
        nonzero_features=len(idx),
        feature_contribution_total=float(contrib.sum()),
        word_contribution_total=float(sum(v for _, v in words)) if available else None,
    )


def _word_attributions(
    vec: Any, text: str, contributions: dict[str, float]
) -> tuple[list[tuple[WordSpan, float]], bool]:
    lowered = vec.build_preprocessor()(text)
    if vec.analyzer == "char_wb":
        # sklearn collapses runs of whitespace and then splits on whitespace; splitting the
        # un-collapsed text on \S+ yields the same words while keeping true offsets.
        built = _occurrences_char_wb(vec, lowered)
    elif vec.analyzer == "word":
        built = _occurrences_word(vec, lowered)
    else:
        return [], False
    if built is None:
        return [], False
    grams, spans = built
    if Counter(grams) != Counter(vec.build_analyzer()(text)):
        return [], False  # could not reproduce the analyser exactly: no approximation
    counts = Counter(grams)
    per_word: dict[tuple[int, int, str], float] = {}
    for gram, window in zip(grams, spans, strict=True):
        value = contributions.get(gram)
        if value is None:
            continue  # n-gram outside the vocabulary contributes nothing
        share = value / counts[gram] / len(window)
        for span in window:
            key = (span.start, span.end, span.word)
            per_word[key] = per_word.get(key, 0.0) + share
    offsets_valid = len(lowered) == len(text)
    out = [
        (
            WordSpan(
                text[s:e] if offsets_valid else w,
                s if offsets_valid else -1,
                e if offsets_valid else -1,
            ),
            v,
        )
        for (s, e, w), v in per_word.items()
    ]
    out.sort(key=lambda item: -abs(item[1]))
    return out, True
