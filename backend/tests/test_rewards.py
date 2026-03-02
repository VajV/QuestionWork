from app.core.rewards import (
    calculate_budget_from_xp,
    calculate_quest_rewards,
    calculate_xp_reward,
    calculate_xp_to_next,
    check_level_up,
    get_grade_xp_requirements,
)
from app.models.user import GradeEnum


def test_calculate_xp_reward_bounds_and_bonus():
    assert calculate_xp_reward(50, GradeEnum.novice, GradeEnum.novice) == 10
    assert calculate_xp_reward(100000, GradeEnum.novice, GradeEnum.novice) == 500
    assert calculate_xp_reward(1000, GradeEnum.junior, GradeEnum.novice) > calculate_xp_reward(
        1000, GradeEnum.novice, GradeEnum.novice
    )


def test_calculate_xp_reward_custom_xp():
    """Custom XP is clamped to [MIN_XP_REWARD, MAX_XP_REWARD]."""
    # Within range
    assert calculate_xp_reward(1000, GradeEnum.novice, GradeEnum.novice, custom_xp=200) == 200
    # Below minimum → clamped to MIN_XP_REWARD (10)
    assert calculate_xp_reward(1000, GradeEnum.novice, GradeEnum.novice, custom_xp=1) == 10
    # Above maximum → clamped to MAX_XP_REWARD (500)
    assert calculate_xp_reward(1000, GradeEnum.novice, GradeEnum.novice, custom_xp=9999) == 500


def test_calculate_quest_rewards_money_equals_budget():
    xp, money = calculate_quest_rewards(
        budget=2500,
        quest_grade=GradeEnum.novice,
        user_grade=GradeEnum.novice,
    )
    assert xp >= 10
    assert money == 2500


def test_check_level_up_thresholds():
    level_up, grade, level = check_level_up(499, GradeEnum.novice)
    assert level_up is False
    assert grade == GradeEnum.novice
    assert level >= 1

    level_up, grade, _ = check_level_up(500, GradeEnum.novice)
    assert level_up is True
    assert grade == GradeEnum.junior

    level_up, grade, _ = check_level_up(2000, GradeEnum.junior)
    assert level_up is True
    assert grade == GradeEnum.middle


def test_calculate_xp_to_next():
    assert calculate_xp_to_next(100, GradeEnum.novice) == 400
    assert calculate_xp_to_next(500, GradeEnum.novice) == 0
    assert calculate_xp_to_next(2100, GradeEnum.junior) == 0
    assert calculate_xp_to_next(99999, GradeEnum.senior) == 0


def test_calculate_budget_from_xp_has_minimum_budget():
    assert calculate_budget_from_xp(1, GradeEnum.novice, GradeEnum.novice) >= 100


def test_get_grade_xp_requirements_keys():
    """All grades are present; senior has xp_to_next == 0."""
    reqs = get_grade_xp_requirements()
    assert set(reqs.keys()) == {GradeEnum.novice, GradeEnum.junior, GradeEnum.middle, GradeEnum.senior}
    assert reqs[GradeEnum.senior]["xp_to_next"] == 0
    assert reqs[GradeEnum.novice]["xp_to_next"] > 0


def test_check_level_up_senior_stays():
    """Senior at max XP should not promote further."""
    level_up, grade, _ = check_level_up(99999, GradeEnum.senior)
    assert level_up is False
    assert grade == GradeEnum.senior


def test_calculate_quest_rewards_with_custom_xp():
    """Custom XP propagates through calculate_quest_rewards."""
    xp, money = calculate_quest_rewards(5000, GradeEnum.middle, GradeEnum.junior, custom_xp=42)
    assert xp == 42
    assert money == 5000
