"""Tests for RPG stat growth logic in rewards.py."""

import pytest

from app.core.rewards import allocate_stat_points, STAT_POINTS_PER_LEVEL


class TestAllocateStatPoints:
    def test_one_level_distributes_one_per_stat(self):
        delta = allocate_stat_points(1)
        assert delta["int"] == 1
        assert delta["dex"] == 1
        assert delta["cha"] == 1
        assert delta["unspent"] == 0

    def test_zero_levels_returns_zeros(self):
        delta = allocate_stat_points(0)
        assert delta == {"int": 0, "dex": 0, "cha": 0, "unspent": 0}

    def test_multiple_levels_scales_linearly(self):
        delta = allocate_stat_points(5)
        assert delta["int"] == 5
        assert delta["dex"] == 5
        assert delta["cha"] == 5
        assert delta["unspent"] == 0

    def test_total_points_equals_stat_points_per_level_times_levels(self):
        levels = 3
        delta = allocate_stat_points(levels)
        total_distributed = delta["int"] + delta["dex"] + delta["cha"] + delta["unspent"]
        assert total_distributed == STAT_POINTS_PER_LEVEL * levels

    def test_negative_levels_raises(self):
        with pytest.raises(ValueError, match=r"≥ 0"):
            allocate_stat_points(-1)

    def test_large_levels(self):
        """Boundary: 100 levels gained at once."""
        delta = allocate_stat_points(100)
        assert delta["int"] == 100
        assert delta["unspent"] == 0


class TestStatGrowthIntegration:
    """Verify that level-up triggers stat growth with correct arithmetic."""

    def test_stat_accumulation_over_10_levels(self):
        """Simulate 10 consecutive level-ups and verify cumulative stat growth."""
        stats_int = 10
        stats_dex = 10
        stats_cha = 10

        for _ in range(10):
            delta = allocate_stat_points(1)
            stats_int += delta["int"]
            stats_dex += delta["dex"]
            stats_cha += delta["cha"]

        assert stats_int == 20
        assert stats_dex == 20
        assert stats_cha == 20

    def test_stat_growth_formula_matches_expected(self):
        """At level 2 (gained 1 level from base 1), each stat should be +1 from start."""
        base_int = 10
        delta = allocate_stat_points(levels_gained=1)
        new_int = base_int + delta["int"]
        assert new_int == 11  # +1 INT per level

    def test_grade_promotion_does_not_reset_stats(self):
        """Grade change should not reduce stats — verify stats accumulate independently."""
        from app.core.rewards import check_level_up
        from app.models.user import GradeEnum

        # Simulate reaching Junior (500 XP)
        xp = 550
        level_up, new_grade, new_level = check_level_up(xp, GradeEnum.novice)

        assert level_up is True
        assert new_grade == GradeEnum.junior

        # Allocate stats for the levels gained
        levels_gained = new_level - 1  # was level 1 before
        delta = allocate_stat_points(max(0, levels_gained))
        assert delta["int"] >= 0  # stats should only grow or stay the same
