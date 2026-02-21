"""Tests for Phase 0 chunking plan validator."""

import pytest

from src.validation.phase0_validator import (
    ValidationResult,
    validate_chunking_plan,
    validate_document_schema,
    _find_marker,
)


# --- Sample document text (simplified) ---
SAMPLE_DOC = """
Introduction to Condition Variables

In particular, there are many cases where a thread wishes to check whether
a condition is true before continuing. For example, a parent thread might
wish to check whether a child thread has completed before continuing.

The Definition and Routines

A condition variable has two operations associated with it: wait() and signal().
The wait() call is executed when a thread wishes to put itself to sleep.
The signal() call is executed when a thread has changed something.

The Producer/Consumer Problem

The next synchronization problem we will confront in this chapter is known
as the producer/consumer problem. Producers generate data items and place
them in a buffer; consumers grab said items.

Mesa vs Hoare Semantics

Signaling a thread only wakes them up; it is thus a hint that the state
of the world has changed. This interpretation is referred to as Mesa semantics.

Summary and Key Points

Condition variables are a powerful synchronization primitive that enable
threads to wait for conditions efficiently.
""".strip()


class TestFindMarker:
    def test_exact_match(self):
        pos = _find_marker(SAMPLE_DOC, "The Definition and Routines")
        assert pos is not None
        assert pos > 0

    def test_case_insensitive(self):
        pos = _find_marker(SAMPLE_DOC, "the definition and routines")
        assert pos is not None

    def test_not_found(self):
        pos = _find_marker(SAMPLE_DOC, "This text does not exist anywhere")
        assert pos is None

    def test_whitespace_normalized(self):
        # The marker has different whitespace than the doc
        pos = _find_marker(SAMPLE_DOC, "wait()  and  signal()")
        assert pos is not None


class TestValidateChunkingPlan:
    def _make_plan(self):
        return [
            {
                "chunk_id": 1,
                "section": "Introduction",
                "start_marker": "Introduction to Condition Variables",
                "end_marker": "The Definition and Routines",
                "expected_token_range": [50, 200],
            },
            {
                "chunk_id": 2,
                "section": "API",
                "start_marker": "The Definition and Routines",
                "end_marker": "The Producer/Consumer Problem",
                "expected_token_range": [50, 200],
            },
            {
                "chunk_id": 3,
                "section": "Producer/Consumer",
                "start_marker": "The Producer/Consumer Problem",
                "end_marker": "Mesa vs Hoare Semantics",
                "expected_token_range": [50, 200],
            },
            {
                "chunk_id": 4,
                "section": "Semantics",
                "start_marker": "Mesa vs Hoare Semantics",
                "end_marker": "Summary and Key Points",
                "expected_token_range": [50, 200],
            },
        ]

    def test_valid_plan(self):
        result = validate_chunking_plan(SAMPLE_DOC, self._make_plan())
        assert len(result.resolved_chunks) == 4
        assert len(result.errors) == 0

    def test_empty_plan(self):
        result = validate_chunking_plan(SAMPLE_DOC, [])
        assert not result.valid
        assert len(result.errors) == 1

    def test_missing_marker(self):
        plan = [
            {
                "chunk_id": 1,
                "section": "Bad",
                "start_marker": "NONEXISTENT MARKER TEXT",
                "end_marker": "The Definition and Routines",
            }
        ]
        result = validate_chunking_plan(SAMPLE_DOC, plan)
        assert not result.valid
        assert any("not found" in e.message for e in result.errors)

    def test_coverage_warning(self):
        # Only cover a small part of the doc
        plan = [
            {
                "chunk_id": 1,
                "section": "Intro only",
                "start_marker": "Introduction to Condition Variables",
                "end_marker": "The Definition and Routines",
            }
        ]
        result = validate_chunking_plan(SAMPLE_DOC, plan)
        # Should have low coverage warning/error
        assert result.coverage_ratio < 0.5

    def test_chunks_in_order(self):
        result = validate_chunking_plan(SAMPLE_DOC, self._make_plan())
        positions = [c.start_pos for c in result.resolved_chunks]
        assert positions == sorted(positions)


class TestValidateDocumentSchema:
    def test_valid_schema(self):
        schema = {
            "topic": "Condition Variables",
            "theme": "Efficient thread waiting",
            "content_type": "textbook_chapter",
            "narrative_root": {
                "summary": "This chapter covers CVs...",
                "key_tension": "Efficiency vs correctness",
                "learning_arc": "motivation → mechanism → application",
            },
            "expected_core_entities": [
                {"label": "Condition Variable", "type": "Concept"}
            ],
            "document_structure": [
                {"section": "Intro", "purpose": "Motivation"}
            ],
            "chunking_plan": [
                {"chunk_id": 1, "start_marker": "foo", "end_marker": "bar"}
            ],
        }
        issues = validate_document_schema(schema)
        errors = [i for i in issues if i.severity == "error"]
        assert len(errors) == 0

    def test_missing_fields(self):
        schema = {"topic": "Test"}  # missing most fields
        issues = validate_document_schema(schema)
        errors = [i for i in issues if i.severity == "error"]
        assert len(errors) >= 3  # missing theme, narrative_root, etc.

    def test_missing_markers(self):
        schema = {
            "topic": "Test",
            "content_type": "textbook_chapter",
            "theme": "Test",
            "narrative_root": {"summary": "x", "key_tension": "y", "learning_arc": "z"},
            "expected_core_entities": [{"label": "A", "type": "Concept"}],
            "document_structure": [{"section": "Intro"}],
            "chunking_plan": [
                {"chunk_id": 1, "section": "Intro"}  # no markers!
            ],
        }
        issues = validate_document_schema(schema)
        errors = [i for i in issues if i.severity == "error"]
        assert any("start_marker" in e.message for e in errors)
