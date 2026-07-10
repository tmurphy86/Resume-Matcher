"""Unit tests for deterministic career intelligence scoring functions.

Tests cover ``compute_attraction_score``, ``compute_fit_score``, and their
supporting helpers.  All inputs are canned — no DB or LLM calls.

Reproducibility invariant: identical inputs → identical outputs.  Every test
that asserts a specific numeric value doubles as a reproducibility check.
"""

import pytest

from app.services.career_intelligence import (
    _collect_fact_cited_block_token_sets,
    _tokenize,
    compute_attraction_score,
    compute_fit_score,
)

# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

_APP_WITH_SIGNALS = {
    "application_id": "app-1",
    "job_id": "job-A",
    "interest_signals": [
        {"dimension": "role_fit", "weight": 4},
        {"dimension": "compensation", "weight": 5},
    ],
}

_APP_NO_SIGNALS = {
    "application_id": "app-2",
    "job_id": "job-B",
    "interest_signals": [],
}

_APP_SINGLE_SIGNAL = {
    "application_id": "app-3",
    "job_id": "job-C",
    "interest_signals": [{"dimension": "role_fit", "weight": 3}],
}

_APP_OTHER_JOB = {
    "application_id": "app-4",
    "job_id": "job-X",  # not in the archetype
    "interest_signals": [{"dimension": "role_fit", "weight": 1}],
}

_PROCESSED_DATA_WITH_BLOCKS = {
    "workExperience": [
        {
            "title": "Software Engineer",
            "company": "Acme",
            "bullet_blocks": [
                {
                    "id": "block-1",
                    "active_variant_id": "v1",
                    "variants": [
                        {
                            "id": "v1",
                            "text": "Designed and implemented scalable Python microservices",
                            "fact_ids": ["fact-uuid-1"],
                        }
                    ],
                },
                {
                    "id": "block-2",
                    "active_variant_id": "v2",
                    "variants": [
                        {
                            "id": "v2",
                            "text": "Led a team of engineers on AWS cloud infrastructure",
                            "fact_ids": [],  # no fact_ids — should be excluded
                        }
                    ],
                },
            ],
        }
    ],
}

_PROCESSED_DATA_EMPTY = {}


# ---------------------------------------------------------------------------
# _tokenize
# ---------------------------------------------------------------------------


class TestTokenize:
    def test_lowercases_and_splits(self) -> None:
        tokens = _tokenize("Python AWS Experience")
        assert "python" in tokens
        assert "aws" in tokens
        assert "experience" in tokens

    def test_stop_words_removed(self) -> None:
        tokens = _tokenize("and the for of with")
        assert not tokens

    def test_short_tokens_removed(self) -> None:
        tokens = _tokenize("a b c")
        assert not tokens

    def test_plus_sign_preserved(self) -> None:
        tokens = _tokenize("C++ experience")
        assert "c++" in tokens

    def test_hash_sign_preserved(self) -> None:
        tokens = _tokenize("C# development")
        assert "c#" in tokens

    def test_numbers_kept(self) -> None:
        tokens = _tokenize("5+ years Python")
        assert "5+" in tokens or "5" in tokens

    def test_empty_string(self) -> None:
        assert _tokenize("") == set()

    def test_reproducible_same_input(self) -> None:
        """Same input always produces the same output."""
        t1 = _tokenize("FastAPI Python backend engineering")
        t2 = _tokenize("FastAPI Python backend engineering")
        assert t1 == t2


# ---------------------------------------------------------------------------
# _collect_fact_cited_block_token_sets
# ---------------------------------------------------------------------------


class TestCollectFactCitedBlockTokenSets:
    def test_extracts_fact_cited_variants_only(self) -> None:
        """Block with empty fact_ids is excluded; block with fact_ids is included."""
        token_sets = _collect_fact_cited_block_token_sets(_PROCESSED_DATA_WITH_BLOCKS)
        # Only block-1 has fact_ids; block-2 has [] and must be excluded.
        assert len(token_sets) == 1
        assert "python" in token_sets[0]

    def test_empty_processed_data_returns_empty(self) -> None:
        result = _collect_fact_cited_block_token_sets(_PROCESSED_DATA_EMPTY)
        assert result == []

    def test_summary_blocks_included(self) -> None:
        data = {
            "summary_blocks": [
                {
                    "id": "sb-1",
                    "active_variant_id": "sv1",
                    "variants": [
                        {
                            "id": "sv1",
                            "text": "Experienced machine learning engineer",
                            "fact_ids": ["fact-ml"],
                        }
                    ],
                }
            ]
        }
        token_sets = _collect_fact_cited_block_token_sets(data)
        assert len(token_sets) == 1
        assert "machine" in token_sets[0]

    def test_project_blocks_included(self) -> None:
        data = {
            "personalProjects": [
                {
                    "name": "ML Tool",
                    "bullet_blocks": [
                        {
                            "id": "pb-1",
                            "active_variant_id": "pv1",
                            "variants": [
                                {
                                    "id": "pv1",
                                    "text": "Built MLflow experiment tracking pipeline",
                                    "fact_ids": ["fact-proj-1"],
                                }
                            ],
                        }
                    ],
                }
            ]
        }
        token_sets = _collect_fact_cited_block_token_sets(data)
        assert len(token_sets) == 1
        assert "mlflow" in token_sets[0]


# ---------------------------------------------------------------------------
# compute_attraction_score — deterministic
# ---------------------------------------------------------------------------


class TestComputeAttractionScore:
    def test_single_app_mean_weight(self) -> None:
        """Mean of weights 4 and 5 across one application = 4.5."""
        score = compute_attraction_score([_APP_WITH_SIGNALS], ["job-A"])
        assert score == pytest.approx(4.5)

    def test_reproducible_identical_input(self) -> None:
        """Same inputs always produce the same float."""
        s1 = compute_attraction_score([_APP_WITH_SIGNALS], ["job-A"])
        s2 = compute_attraction_score([_APP_WITH_SIGNALS], ["job-A"])
        assert s1 == s2

    def test_no_matching_applications(self) -> None:
        """No applications for the given jd_ids → 0.0."""
        score = compute_attraction_score([_APP_WITH_SIGNALS], ["job-Z"])
        assert score == 0.0

    def test_no_applications_at_all(self) -> None:
        score = compute_attraction_score([], ["job-A"])
        assert score == 0.0

    def test_empty_signals(self) -> None:
        """Application with empty interest_signals contributes nothing."""
        score = compute_attraction_score([_APP_NO_SIGNALS], ["job-B"])
        assert score == 0.0

    def test_excludes_other_job_applications(self) -> None:
        """Applications for jobs outside the archetype must not affect the score."""
        apps = [_APP_WITH_SIGNALS, _APP_OTHER_JOB]
        score = compute_attraction_score(apps, ["job-A"])
        # Only job-A signals counted (4 + 5) / 2 = 4.5; job-X must not pollute.
        assert score == pytest.approx(4.5)

    def test_multiple_apps_multiple_signals(self) -> None:
        """Mean is across ALL signals from ALL member applications."""
        apps = [
            {
                "application_id": "a1",
                "job_id": "job-A",
                "interest_signals": [{"dimension": "x", "weight": 2}],
            },
            {
                "application_id": "a2",
                "job_id": "job-B",
                "interest_signals": [
                    {"dimension": "y", "weight": 4},
                    {"dimension": "z", "weight": 4},
                ],
            },
        ]
        # (2 + 4 + 4) / 3 = 10/3 ≈ 3.333...
        score = compute_attraction_score(apps, ["job-A", "job-B"])
        assert score == pytest.approx(10.0 / 3.0)

    def test_weight_must_be_numeric(self) -> None:
        """Non-numeric weight is silently skipped."""
        app = {
            "application_id": "a1",
            "job_id": "job-A",
            "interest_signals": [
                {"dimension": "x", "weight": "high"},  # string — skip
                {"dimension": "y", "weight": 3},
            ],
        }
        score = compute_attraction_score([app], ["job-A"])
        assert score == pytest.approx(3.0)


# ---------------------------------------------------------------------------
# compute_fit_score — deterministic
# ---------------------------------------------------------------------------


class TestComputeFitScore:
    def test_no_requirements_returns_perfect_fit(self) -> None:
        fit, gaps = compute_fit_score(_PROCESSED_DATA_WITH_BLOCKS, [])
        assert fit == 1.0
        assert gaps == []

    def test_covered_requirement(self) -> None:
        """Requirement whose key terms appear in a fact-cited block → covered."""
        reqs = ["Python microservices experience"]
        fit, gaps = compute_fit_score(_PROCESSED_DATA_WITH_BLOCKS, reqs)
        # "python" and "microservices" are in block-1's fact-cited text.
        assert fit == pytest.approx(1.0)
        assert gaps == []

    def test_uncovered_requirement_in_gaps(self) -> None:
        """Requirement with no fact coverage → fit < 1.0 and gap listed."""
        reqs = ["Machine learning MLflow pipeline"]
        fit, gaps = compute_fit_score(_PROCESSED_DATA_WITH_BLOCKS, reqs)
        # None of these tokens appear in the (only) fact-cited block.
        assert fit == pytest.approx(0.0)
        assert reqs[0] in gaps

    def test_partial_coverage(self) -> None:
        """2 requirements; 1 covered → fit = 0.5, 1 gap."""
        reqs = [
            "Python microservices experience",  # covered
            "Machine learning MLflow skills",   # not covered
        ]
        fit, gaps = compute_fit_score(_PROCESSED_DATA_WITH_BLOCKS, reqs)
        assert fit == pytest.approx(0.5)
        assert len(gaps) == 1
        assert gaps[0] == reqs[1]

    def test_empty_processed_data_all_gaps(self) -> None:
        """No fact-cited blocks in resume → every requirement is a gap."""
        reqs = ["Python skills", "AWS experience"]
        fit, gaps = compute_fit_score({}, reqs)
        assert fit == pytest.approx(0.0)
        assert set(gaps) == set(reqs)

    def test_unfactored_block_not_used(self) -> None:
        """Block with empty fact_ids must not contribute to coverage."""
        data = {
            "workExperience": [
                {
                    "bullet_blocks": [
                        {
                            "id": "b1",
                            "active_variant_id": "v1",
                            "variants": [
                                {
                                    "id": "v1",
                                    "text": "Python AWS backend engineer",
                                    "fact_ids": [],  # no provenance
                                }
                            ],
                        }
                    ]
                }
            ]
        }
        reqs = ["Python backend engineering"]
        fit, gaps = compute_fit_score(data, reqs)
        # Block has no fact_ids → must be excluded → requirement is uncovered.
        assert fit == pytest.approx(0.0)
        assert reqs[0] in gaps

    def test_reproducible_same_input(self) -> None:
        """Same inputs always produce the same (score, gaps) pair."""
        reqs = ["Python microservices experience", "Machine learning MLflow"]
        r1 = compute_fit_score(_PROCESSED_DATA_WITH_BLOCKS, reqs)
        r2 = compute_fit_score(_PROCESSED_DATA_WITH_BLOCKS, reqs)
        assert r1 == r2

    def test_stop_word_only_requirement_is_covered(self) -> None:
        """Requirement that tokenizes to empty set is treated as covered."""
        fit, gaps = compute_fit_score({}, ["the and or of"])
        assert fit == pytest.approx(1.0)
        assert gaps == []

    def test_exact_score_with_three_requirements(self) -> None:
        """Deterministic: 3 requirements, 1 covered → exactly 1/3."""
        data = {
            "workExperience": [
                {
                    "bullet_blocks": [
                        {
                            "id": "b1",
                            "active_variant_id": "v1",
                            "variants": [
                                {
                                    "id": "v1",
                                    "text": "Python developer",
                                    "fact_ids": ["f1"],
                                }
                            ],
                        }
                    ]
                }
            ]
        }
        reqs = ["Python experience", "AWS cloud skills", "MLflow pipeline"]
        fit, gaps = compute_fit_score(data, reqs)
        assert fit == pytest.approx(1.0 / 3.0)
        assert len(gaps) == 2
        assert "Python experience" not in gaps
