"""单元测试 — 期刊推荐引擎"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(__file__) + "/..")

from journal_recommender import recommend_journals, JOURNAL_DB


class TestJournalRecommender:
    def test_returns_limit(self):
        result = recommend_journals(
            "This is a paper about NLP and large language models.",
            overall_score=80,
            limit=5,
        )
        assert len(result) <= 5

    def test_returns_journals_list(self):
        result = recommend_journals(
            "This paper proposes a novel method for NLP tasks.",
            overall_score=70,
        )
        assert len(result) > 0
        for j in result:
            assert "name" in j
            assert "level" in j
            assert "match" in j
            assert "reason" in j

    def test_exclude_works(self):
        text = "NLP paper about large language models."
        result = recommend_journals(
            text,
            exclude=["ACL (Annual Meeting of the ACL)"],
            limit=10,
        )
        names = [j["name"] for j in result]
        assert "ACL (Annual Meeting of the ACL)" not in names

    def test_journal_db_not_empty(self):
        assert len(JOURNAL_DB) > 0

    def test_journal_has_required_fields(self):
        required = {"name", "level", "scope", "desc"}
        for j in JOURNAL_DB:
            for field in required:
                assert field in j, f"Journal {j.get('name', '?')} missing {field}"
