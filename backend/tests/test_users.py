"""Tests for user-related pure-function helpers.

Covers:
  - compute_reputation_stats() formula stability
  - Edge cases: new user, max stats, partial data
"""

import pytest

from app.core.rewards import compute_reputation_stats
from app.models.user import GradeEnum, ReputationStats


# ─────────────────────────────────────────────
# Fixtures / helpers
# ─────────────────────────────────────────────

def _rs(**kwargs) -> ReputationStats:
    """Helper that calls compute_reputation_stats with keyword defaults."""
    return compute_reputation_stats(**kwargs)


# ─────────────────────────────────────────────
# New / empty user
# ─────────────────────────────────────────────

class TestNewUserReputationStats:
    """A brand-new user with no history should have near-zero stats."""

    def test_returns_reputation_stats_instance(self):
        result = _rs()
        assert isinstance(result, ReputationStats)

    def test_all_stats_low_for_new_user(self):
        # level=1 contributes min(1/20,1)*0.20 = 0.01 → influence=1
        result = _rs()
        assert result.reliability == 0
        assert result.craft == 0
        assert result.influence == 1  # tiny level-1 contribution
        assert result.resolve == 0

    def test_explicit_none_values_produce_zero_except_influence(self):
        # level=1 with no quests/reviews still gives influence=1
        result = _rs(
            avg_rating=None,
            completion_rate=None,
            trust_score=None,
            confirmed_quest_count=0,
            review_count=0,
            level=1,
            grade=GradeEnum.novice,
            profile_completeness_percent=0,
        )
        assert result.reliability == 0
        assert result.craft == 0
        assert result.influence == 1  # min(1/20)*0.20*100 = 1
        assert result.resolve == 0


# ─────────────────────────────────────────────
# Reliability
# ─────────────────────────────────────────────

class TestReliability:
    """reliability = completion_rate*0.70 + trust_score*0.30 (both 0-1)."""

    def test_full_completion_no_trust(self):
        # 100% completion, 0 trust → 0.70 * 100 = 70
        result = _rs(completion_rate=100.0, trust_score=0.0)
        assert result.reliability == 70

    def test_zero_completion_full_trust(self):
        # 0% completion, 1.0 trust → 0.30 * 100 = 30
        result = _rs(completion_rate=0.0, trust_score=1.0)
        assert result.reliability == 30

    def test_full_completion_full_trust(self):
        result = _rs(completion_rate=100.0, trust_score=1.0)
        assert result.reliability == 100

    def test_50pct_completion_half_trust(self):
        # 0.50*0.70 + 0.50*0.30 = 0.35 + 0.15 = 0.50 → 50
        result = _rs(completion_rate=50.0, trust_score=0.5)
        assert result.reliability == 50

    def test_completion_rate_clamped_above_100(self):
        result = _rs(completion_rate=200.0, trust_score=0.0)
        assert result.reliability == 70  # clamped to 100% completion

    def test_negative_completion_rate_clamped_to_zero(self):
        result = _rs(completion_rate=-10.0, trust_score=0.0)
        assert result.reliability == 0

    def test_trust_score_clamped_above_one(self):
        result = _rs(completion_rate=0.0, trust_score=2.0)
        assert result.reliability == 30  # clamped to 1.0


# ─────────────────────────────────────────────
# Craft
# ─────────────────────────────────────────────

class TestCraft:
    """craft = (avg_rating/5)*0.70 + level_bonus*0.30."""

    def test_perfect_rating_novice(self):
        # 5.0/5.0 * 0.70 + 0.0 * 0.30 = 70
        result = _rs(avg_rating=5.0, grade=GradeEnum.novice)
        assert result.craft == 70

    def test_perfect_rating_senior(self):
        # 5.0/5.0 * 0.70 + 1.0 * 0.30 = 70 + 30 = 100
        result = _rs(avg_rating=5.0, grade=GradeEnum.senior)
        assert result.craft == 100

    def test_zero_rating_senior(self):
        # 0 * 0.70 + 1.0 * 0.30 = 30
        result = _rs(avg_rating=0.0, grade=GradeEnum.senior)
        assert result.craft == 30

    def test_no_rating_junior(self):
        # None → 0 * 0.70 + 0.25 * 0.30 = 0 + 7.5 → 8 (round)
        result = _rs(avg_rating=None, grade=GradeEnum.junior)
        assert result.craft == round(0.25 * 0.30 * 100)

    def test_mid_rating_middle(self):
        # 2.5/5.0 = 0.5; 0.5*0.70 + 0.50*0.30 = 0.35 + 0.15 = 0.50 → 50
        result = _rs(avg_rating=2.5, grade=GradeEnum.middle)
        assert result.craft == 50

    def test_grade_string_accepted(self):
        # Accept plain string "senior" in addition to enum
        result = _rs(avg_rating=5.0, grade="senior")
        assert result.craft == 100

    def test_unknown_grade_string_treated_as_novice(self):
        result = _rs(avg_rating=5.0, grade="legendary")
        # no level_bonus → craft = 70
        assert result.craft == 70


# ─────────────────────────────────────────────
# Influence
# ─────────────────────────────────────────────

class TestInfluence:
    """influence = min(quests/50,1)*0.50 + min(reviews/20,1)*0.30 + min(level/20,1)*0.20."""

    def test_all_caps(self):
        # quests=50, reviews=20, level=20 → 0.50+0.30+0.20 = 1.0 → 100
        result = _rs(confirmed_quest_count=50, review_count=20, level=20)
        assert result.influence == 100

    def test_capped_beyond_50_quests(self):
        result1 = _rs(confirmed_quest_count=50, review_count=0, level=1)
        result2 = _rs(confirmed_quest_count=200, review_count=0, level=1)
        assert result1.influence == result2.influence  # capped

    def test_zero_history(self):
        result = _rs(confirmed_quest_count=0, review_count=0, level=1)
        # only level factor: min(1/20,1)*0.20*100 = 0.05*0.20*100 = 1
        assert result.influence == 1

    def test_level_1(self):
        # level_factor=0.05, weighted by 0.20 → 0.01 → 1
        result = _rs(confirmed_quest_count=0, review_count=0, level=1)
        assert result.influence == 1

    def test_only_quests(self):
        # 25 quests → 0.50 * 0.50 = 0.25 → 25 (+ level=1: 0.05 → 25+5=30? let me compute)
        # quests=25/50=0.5, reviews=0, level=1/20=0.05
        # 0.5*0.50 + 0*0.30 + 0.05*0.20 = 0.25 + 0 + 0.01 = 0.26 → 26
        result = _rs(confirmed_quest_count=25, review_count=0, level=1)
        assert result.influence == round((0.50 * 0.50 + 0.0 + (1 / 20) * 0.20) * 100)

    def test_only_reviews(self):
        # 10 reviews → 10/20=0.5 * 0.30 = 0.15, level=1: 0.05*0.20=0.01 → 0.16 → 16
        result = _rs(review_count=10, level=1)
        assert result.influence == round(((10 / 20) * 0.30 + (1 / 20) * 0.20) * 100)


# ─────────────────────────────────────────────
# Resolve
# ─────────────────────────────────────────────

class TestResolve:
    """resolve = trust_score*0.60 + (completeness/100)*0.40."""

    def test_full_trust_full_completeness(self):
        result = _rs(trust_score=1.0, profile_completeness_percent=100)
        assert result.resolve == 100

    def test_zero_trust_full_completeness(self):
        result = _rs(trust_score=0.0, profile_completeness_percent=100)
        assert result.resolve == 40

    def test_full_trust_zero_completeness(self):
        result = _rs(trust_score=1.0, profile_completeness_percent=0)
        assert result.resolve == 60

    def test_half_trust_half_completeness(self):
        # 0.5*0.60 + 0.5*0.40 = 0.30 + 0.20 = 0.50 → 50
        result = _rs(trust_score=0.5, profile_completeness_percent=50)
        assert result.resolve == 50

    def test_completeness_clamped(self):
        result1 = _rs(trust_score=0.0, profile_completeness_percent=100)
        result2 = _rs(trust_score=0.0, profile_completeness_percent=999)
        assert result1.resolve == result2.resolve  # clamped to 40

    def test_negative_trust_clamped(self):
        result = _rs(trust_score=-0.5, profile_completeness_percent=0)
        assert result.resolve == 0


# ─────────────────────────────────────────────
# Max-rep user
# ─────────────────────────────────────────────

class TestMaxRepUser:
    def test_all_stats_at_100_for_ideal_user(self):
        result = compute_reputation_stats(
            avg_rating=5.0,
            completion_rate=100.0,
            trust_score=1.0,
            confirmed_quest_count=50,
            review_count=20,
            level=20,
            grade=GradeEnum.senior,
            profile_completeness_percent=100,
        )
        assert result.reliability == 100
        assert result.craft == 100
        assert result.influence == 100
        assert result.resolve == 100

    def test_values_stay_within_0_100_bounds(self):
        result = compute_reputation_stats(
            avg_rating=10.0,    # out of range
            completion_rate=200.0,
            trust_score=5.0,
            confirmed_quest_count=9999,
            review_count=9999,
            level=9999,
            grade=GradeEnum.senior,
            profile_completeness_percent=9999,
        )
        assert 0 <= result.reliability <= 100
        assert 0 <= result.craft <= 100
        assert 0 <= result.influence <= 100
        assert 0 <= result.resolve <= 100


# ─────────────────────────────────────────────
# Model field constraints
# ─────────────────────────────────────────────

class TestReputationStatsModel:
    def test_reputation_stats_has_four_fields(self):
        rs = ReputationStats()
        assert hasattr(rs, "reliability")
        assert hasattr(rs, "craft")
        assert hasattr(rs, "influence")
        assert hasattr(rs, "resolve")

    def test_defaults_are_zero(self):
        rs = ReputationStats()
        assert rs.reliability == 0
        assert rs.craft == 0
        assert rs.influence == 0
        assert rs.resolve == 0

    def test_rejects_value_above_100(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ReputationStats(reliability=101)

    def test_rejects_negative_value(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ReputationStats(craft=-1)
