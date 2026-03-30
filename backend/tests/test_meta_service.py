"""Tests for world-meta pure-function helpers.

Covers:
  - _faction_status: trend → region status mapping
  - _build_season_extras: stage transitions (muster / ascent / finale)
  - _build_regions: region progress fields, dominant factions, activity labels
  - _build_lore_beats: headline generation, warning beats, low-activity fallback
"""

import pytest

from app.services.meta_service import (
    _build_lore_beats,
    _build_regions,
    _build_season_extras,
    _faction_status,
    apply_alignment_bonuses,
    compute_alignment_contribution,
)


# ─────────────────────────────────────────────────────────────
# Helpers / fixtures
# ─────────────────────────────────────────────────────────────

def _make_metrics(**overrides) -> dict:
    base = {
        "total_users": 0,
        "freelancer_count": 0,
        "client_count": 0,
        "open_quests": 0,
        "in_progress_quests": 0,
        "revision_requested_quests": 0,
        "urgent_quests": 0,
        "confirmed_quests_week": 0,
        "unread_notifications": 0,
        "total_reviews": 0,
        "avg_rating": None,
        "earned_badges": 0,
    }
    base.update(overrides)
    return base


def _make_faction_rows(
    vanguard_score: int = 10,
    keepers_score: int = 10,
    artisans_score: int = 10,
    vanguard_trend: str = "holding",
    keepers_trend: str = "holding",
    artisans_trend: str = "holding",
) -> list[dict]:
    return [
        {"id": "vanguard", "name": "Фракция Авангарда", "score": vanguard_score, "trend": vanguard_trend, "focus": ""},
        {"id": "keepers",  "name": "Хранители Потока",   "score": keepers_score,  "trend": keepers_trend,  "focus": ""},
        {"id": "artisans", "name": "Дом Ремесленников",  "score": artisans_score, "trend": artisans_trend, "focus": ""},
    ]


def _make_leader(faction_id: str = "vanguard", name: str = "Фракция Авангарда") -> dict:
    return {"id": faction_id, "name": name, "score": 30, "trend": "surging", "focus": ""}


# ─────────────────────────────────────────────────────────────
# _faction_status
# ─────────────────────────────────────────────────────────────

class TestFactionStatus:
    def test_surging_is_active(self):
        assert _faction_status("surging") == "active"

    def test_holding_is_contested(self):
        assert _faction_status("holding") == "contested"

    def test_recovering_is_dormant(self):
        assert _faction_status("recovering") == "dormant"

    def test_unknown_trend_defaults_to_active(self):
        assert _faction_status("legendary") == "active"
        assert _faction_status("") == "active"

    def test_stable_trend_defaults_to_active(self):
        # "stable" is not a defined key → falls back to "active"
        assert _faction_status("stable") == "active"


# ─────────────────────────────────────────────────────────────
# _build_season_extras — stage transitions
# ─────────────────────────────────────────────────────────────

class TestBuildSeasonExtras:
    def test_muster_stage_chapter(self):
        result = _build_season_extras("muster", 10)
        assert "I" in result["chapter"]

    def test_ascent_stage_chapter(self):
        result = _build_season_extras("ascent", 50)
        assert "II" in result["chapter"]

    def test_finale_stage_chapter(self):
        result = _build_season_extras("finale", 90)
        assert "III" in result["chapter"]

    def test_muster_next_unlock_mentions_35pct(self):
        result = _build_season_extras("muster", 10)
        assert "35" in result["next_unlock"]

    def test_ascent_next_unlock_mentions_75pct(self):
        result = _build_season_extras("ascent", 50)
        assert "75" in result["next_unlock"]

    def test_finale_next_unlock_nonempty(self):
        result = _build_season_extras("finale", 90)
        assert len(result["next_unlock"]) > 0

    def test_all_fields_present(self):
        for stage in ("muster", "ascent", "finale"):
            result = _build_season_extras(stage, 30)
            assert "chapter" in result
            assert "stage_description" in result
            assert "next_unlock" in result

    def test_stage_description_nonempty_for_all_stages(self):
        for stage in ("muster", "ascent", "finale"):
            result = _build_season_extras(stage, 0)
            assert len(result["stage_description"]) > 5

    def test_unknown_stage_falls_back_to_muster(self):
        # anything that isn't "ascent"/"finale" hits the default return
        result = _build_season_extras("nonexistent", 0)
        assert "I" in result["chapter"]


# ─────────────────────────────────────────────────────────────
# _build_regions — region progress fields
# ─────────────────────────────────────────────────────────────

class TestBuildRegions:
    def _default_regions(self, **metric_overrides):
        metrics = _make_metrics(**metric_overrides)
        faction_rows = _make_faction_rows()
        leader = _make_leader()
        return _build_regions(metrics, faction_rows, leader, 40)

    def test_returns_4_regions(self):
        assert len(self._default_regions()) == 4

    def test_region_ids_are_expected(self):
        ids = {r["id"] for r in self._default_regions()}
        assert ids == {"frontier", "archive", "signals", "nexus"}

    def test_progress_percent_is_0_to_100(self):
        for region in self._default_regions():
            assert 0 <= region["progress_percent"] <= 100

    def test_nexus_uses_season_progress(self):
        metrics = _make_metrics()
        faction_rows = _make_faction_rows()
        leader = _make_leader()
        regions = _build_regions(metrics, faction_rows, leader, season_progress=67)
        nexus = next(r for r in regions if r["id"] == "nexus")
        assert nexus["progress_percent"] == 67

    def test_nexus_dominant_faction_is_leader(self):
        metrics = _make_metrics()
        faction_rows = _make_faction_rows()
        leader = _make_leader(faction_id="artisans")
        regions = _build_regions(metrics, faction_rows, leader, season_progress=50)
        nexus = next(r for r in regions if r["id"] == "nexus")
        assert nexus["dominant_faction_id"] == "artisans"

    def test_frontier_dominant_faction_is_vanguard(self):
        regions = self._default_regions()
        frontier = next(r for r in regions if r["id"] == "frontier")
        assert frontier["dominant_faction_id"] == "vanguard"

    def test_equal_scores_produce_valid_percentages(self):
        # All equal → each faction ~33%
        regions = self._default_regions()
        for region in regions:
            if region["id"] != "nexus":
                assert region["progress_percent"] > 0

    def test_surging_faction_is_active_region(self):
        metrics = _make_metrics()
        faction_rows = _make_faction_rows(vanguard_trend="surging")
        leader = _make_leader()
        regions = _build_regions(metrics, faction_rows, leader, 20)
        frontier = next(r for r in regions if r["id"] == "frontier")
        assert frontier["status"] == "active"

    def test_recovering_faction_is_dormant_region(self):
        metrics = _make_metrics()
        faction_rows = _make_faction_rows(artisans_trend="recovering")
        leader = _make_leader()
        regions = _build_regions(metrics, faction_rows, leader, 20)
        archive = next(r for r in regions if r["id"] == "archive")
        assert archive["status"] == "dormant"

    def test_all_zero_scores_clamped_to_0(self):
        metrics = _make_metrics()
        faction_rows = _make_faction_rows(vanguard_score=0, keepers_score=0, artisans_score=0)
        leader = _make_leader()
        regions = _build_regions(metrics, faction_rows, leader, 0)
        for r in regions:
            assert r["progress_percent"] == 0

    def test_activity_labels_are_strings(self):
        for region in self._default_regions():
            assert isinstance(region["activity_label"], str)
            assert len(region["activity_label"]) > 0


# ─────────────────────────────────────────────────────────────
# _build_lore_beats — headline and narrative generation
# ─────────────────────────────────────────────────────────────

class TestBuildLoreBeats:
    def _beats(self, **kwargs) -> list[dict]:
        defaults = dict(
            metrics=_make_metrics(),
            leader=_make_leader(),
            season_stage="muster",
            community_momentum="steady",
        )
        defaults.update(kwargs)
        return _build_lore_beats(**defaults)

    def test_low_activity_returns_at_least_1_beat(self):
        beats = self._beats()
        assert len(beats) >= 1

    def test_returns_at_most_4_beats(self):
        # Give conditions that would trigger many beats
        metrics = _make_metrics(
            revision_requested_quests=10,
            confirmed_quests_week=5,
            open_quests=10,
            urgent_quests=5,
            avg_rating=4.8,
        )
        beats = self._beats(metrics=metrics, season_stage="finale", community_momentum="under_pressure")
        assert len(beats) <= 4

    def test_finale_stage_gives_milestone_beat(self):
        beats = self._beats(season_stage="finale")
        assert beats[0]["beat_type"] == "milestone"

    def test_muster_stage_gives_narrative_beat(self):
        beats = self._beats(season_stage="muster")
        assert beats[0]["beat_type"] == "narrative"

    def test_ascent_stage_gives_narrative_beat(self):
        beats = self._beats(season_stage="ascent")
        assert beats[0]["beat_type"] == "narrative"

    def test_under_pressure_gives_warning_beat(self):
        beats = self._beats(community_momentum="under_pressure")
        beat_types = {b["beat_type"] for b in beats}
        assert "warning" in beat_types

    def test_high_rating_gives_quality_milestone(self):
        metrics = _make_metrics(avg_rating=4.9)
        beats = self._beats(metrics=metrics)
        beat_ids = {b["id"] for b in beats}
        assert "quality_milestone" in beat_ids

    def test_urgent_spike_gives_warning_beat(self):
        # urgent > 30% of open
        metrics = _make_metrics(open_quests=10, urgent_quests=4)
        beats = self._beats(metrics=metrics)
        beat_ids = {b["id"] for b in beats}
        assert "urgent_spike" in beat_ids

    def test_no_urgent_spike_when_few_urgent(self):
        metrics = _make_metrics(open_quests=10, urgent_quests=1)
        beats = self._beats(metrics=metrics)
        beat_ids = {b["id"] for b in beats}
        assert "urgent_spike" not in beat_ids

    def test_all_beats_have_required_fields(self):
        beats = self._beats()
        for beat in beats:
            assert "id" in beat
            assert "text" in beat
            assert "beat_type" in beat
            assert "faction_id" in beat

    def test_beat_text_nonempty(self):
        for beat in self._beats():
            assert len(beat["text"]) > 10

    def test_quiet_period_fallback_when_all_empty(self):
        # Create conditions that only generate a quiet_period beat
        # (no revisions, no avg_rating=high, no confirmed quests, no urgent spike)
        metrics = _make_metrics(
            confirmed_quests_week=0,
            revision_requested_quests=0,
            open_quests=0,
            urgent_quests=0,
        )
        beats = _build_lore_beats(
            metrics=metrics,
            leader=_make_leader(),
            season_stage="muster",
            community_momentum="steady",
        )
        # The muster first beat will fire anyway, so at most we check the list isn't empty
        assert len(beats) >= 1


# ─────────────────────────────────────────────────────────────
# compute_alignment_contribution
# ─────────────────────────────────────────────────────────────

class TestComputeAlignmentContribution:
    def test_none_faction_returns_all_zeros(self):
        result = compute_alignment_contribution("none", 80)
        assert result == {"vanguard": 0, "keepers": 0, "artisans": 0}

    def test_unknown_faction_returns_all_zeros(self):
        result = compute_alignment_contribution("pirates", 50)
        assert result == {"vanguard": 0, "keepers": 0, "artisans": 0}

    def test_vanguard_gets_score(self):
        result = compute_alignment_contribution("vanguard", 40)
        assert result["vanguard"] == 40
        assert result["keepers"] == 0
        assert result["artisans"] == 0

    def test_keepers_gets_score(self):
        result = compute_alignment_contribution("keepers", 60)
        assert result["keepers"] == 60
        assert result["vanguard"] == 0
        assert result["artisans"] == 0

    def test_artisans_gets_score(self):
        result = compute_alignment_contribution("artisans", 55)
        assert result["artisans"] == 55

    def test_score_is_capped_at_100(self):
        result = compute_alignment_contribution("vanguard", 999)
        assert result["vanguard"] == 100

    def test_score_is_floored_at_0(self):
        result = compute_alignment_contribution("vanguard", -5)
        assert result["vanguard"] == 0

    def test_zero_contribution_score(self):
        result = compute_alignment_contribution("keepers", 0)
        assert result == {"vanguard": 0, "keepers": 0, "artisans": 0}


# ─────────────────────────────────────────────────────────────
# apply_alignment_bonuses — faction totals stable when sparse
# ─────────────────────────────────────────────────────────────

class TestApplyAlignmentBonuses:
    def test_none_bonuses_returns_same_scores(self):
        rows = _make_faction_rows(vanguard_score=10, keepers_score=8, artisans_score=6)
        result = apply_alignment_bonuses(rows, None)
        scores = {r["id"]: r["score"] for r in result}
        assert scores == {"vanguard": 10, "keepers": 8, "artisans": 6}

    def test_empty_bonuses_returns_same_scores(self):
        rows = _make_faction_rows(vanguard_score=10, keepers_score=8, artisans_score=6)
        result = apply_alignment_bonuses(rows, {})
        scores = {r["id"]: r["score"] for r in result}
        assert scores == {"vanguard": 10, "keepers": 8, "artisans": 6}

    def test_bonus_adds_to_correct_faction(self):
        rows = _make_faction_rows(vanguard_score=10, keepers_score=8, artisans_score=6)
        result = apply_alignment_bonuses(rows, {"vanguard": 5})
        scores = {r["id"]: r["score"] for r in result}
        assert scores["vanguard"] == 15
        assert scores["keepers"] == 8   # unchanged
        assert scores["artisans"] == 6  # unchanged

    def test_multiple_bonuses_applied_independently(self):
        rows = _make_faction_rows(vanguard_score=10, keepers_score=8, artisans_score=6)
        result = apply_alignment_bonuses(rows, {"vanguard": 3, "artisans": 7})
        scores = {r["id"]: r["score"] for r in result}
        assert scores["vanguard"] == 13
        assert scores["keepers"] == 8
        assert scores["artisans"] == 13

    def test_unknown_key_in_bonuses_ignored(self):
        rows = _make_faction_rows(vanguard_score=10, keepers_score=8, artisans_score=6)
        result = apply_alignment_bonuses(rows, {"pirates": 100})
        scores = {r["id"]: r["score"] for r in result}
        assert scores == {"vanguard": 10, "keepers": 8, "artisans": 6}

    def test_all_zeros_bonus_leaves_scores_unchanged(self):
        rows = _make_faction_rows(vanguard_score=5, keepers_score=5, artisans_score=5)
        result = apply_alignment_bonuses(rows, {"vanguard": 0, "keepers": 0, "artisans": 0})
        scores = {r["id"]: r["score"] for r in result}
        assert scores == {"vanguard": 5, "keepers": 5, "artisans": 5}

    def test_output_preserves_all_original_fields(self):
        rows = _make_faction_rows()
        result = apply_alignment_bonuses(rows, {"vanguard": 1})
        for row in result:
            assert "id" in row
            assert "name" in row
            assert "score" in row
            assert "trend" in row
            assert "focus" in row

    def test_input_rows_not_mutated(self):
        rows = _make_faction_rows(vanguard_score=10, keepers_score=8, artisans_score=6)
        original_score = rows[0]["score"]
        apply_alignment_bonuses(rows, {"vanguard": 50})
        assert rows[0]["score"] == original_score  # unchanged original
