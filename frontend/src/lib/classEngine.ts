/**
 * classEngine — фронтенд-порт логики calculate_class_xp_multiplier и should_block_quest.
 *
 * Использует active_bonuses / weaknesses из UserClassInfo (уже возвращённые API),
 * вместо хардкода числовых значений — фронтенд всегда синхронизирован с бэкендом.
 */

import type { Quest, UserClassInfo, ClassBonusInfo } from "@/lib/api";

// ────────────────────────────────────────────
// Helpers
// ────────────────────────────────────────────

/** Lookup a bonus/weakness by key in UserClassInfo. */
function findBonus(
  bonuses: ClassBonusInfo[],
  key: string,
): ClassBonusInfo | undefined {
  return bonuses.find((b) => b.key === key);
}

function numVal(bonuses: ClassBonusInfo[], key: string): number {
  const b = findBonus(bonuses, key);
  return typeof b?.value === "number" ? b.value : 0;
}

function boolVal(bonuses: ClassBonusInfo[], key: string): boolean {
  const b = findBonus(bonuses, key);
  return b?.value === true;
}

// ────────────────────────────────────────────
// Quest analysis — derive flags from Quest fields
// ────────────────────────────────────────────

/** Budget threshold to treat a quest as "high-budget" (matches backend heuristic). */
const HIGH_BUDGET_THRESHOLD = 50_000;
/** Age in ms for a quest to be considered "stale" (>7 days). */
const STALE_AGE_MS = 7 * 24 * 60 * 60 * 1000;

interface QuestFlags {
  is_urgent: boolean;
  is_highbudget: boolean;
  is_stale: boolean;
  required_portfolio: boolean;
}

export function deriveQuestFlags(quest: Quest): QuestFlags {
  const age = Date.now() - new Date(quest.created_at).getTime();
  return {
    is_urgent: quest.is_urgent,
    is_highbudget: quest.budget >= HIGH_BUDGET_THRESHOLD,
    is_stale: age >= STALE_AGE_MS,
    required_portfolio: quest.required_portfolio,
  };
}

// ────────────────────────────────────────────
// XP Multiplier (mirrors backend calculate_class_xp_multiplier)
// ────────────────────────────────────────────

/**
 * Calculate XP multiplier for a quest given the user's class.
 *
 * Only factors that can be determined from quest card data are used
 * (is_urgent, is_highbudget, is_stale). Factors like is_ontime, is_fivestar
 * are only known after quest completion; they are excluded here so
 * the card shows a conservative preview.
 *
 * Returns a float: 1.0 = no bonus, 1.3 = +30%.
 */
export function calcXpMultiplier(
  classInfo: UserClassInfo,
  quest: Quest,
): number {
  const flags = deriveQuestFlags(quest);
  const all = [...classInfo.active_bonuses, ...classInfo.weaknesses];

  let multiplier = 1.0;

  // ── Berserker: urgent bonus ──
  if (flags.is_urgent) {
    multiplier += numVal(all, "xp_urgent_bonus");
  }

  // ── Berserker: burnout penalty ──
  if (classInfo.is_burnout) {
    multiplier += numVal(all, "burnout_xp_penalty");
  }

  // ── Archmage: highbudget bonus / normal penalty ──
  if (flags.is_highbudget) {
    multiplier += numVal(all, "xp_highbudget_bonus");
  }
  if (!flags.is_highbudget && !flags.is_urgent) {
    multiplier += numVal(all, "xp_normal_penalty");
  }

  // ── Alchemist: stale quest bonus ──
  if (flags.is_stale) {
    multiplier += numVal(all, "xp_stale_quest_bonus");
  }

  // ── Alchemist / Oracle: urgent penalty ──
  if (flags.is_urgent) {
    multiplier += numVal(all, "urgent_xp_penalty");
  }

  // Note: xp_firstapply_bonus, xp_ontime_bonus, xp_fivestar_bonus, xp_analytics_quest_bonus,
  // xp_creative_penalty are not deterministic from quest card alone.
  // They would show after user takes action → handled at completion time.

  return Math.max(0.1, multiplier);
}

// ────────────────────────────────────────────
// Block check (mirrors backend should_block_quest)
// ────────────────────────────────────────────

/**
 * Returns a human-readable block reason, or null if quest is accessible.
 */
export function getBlockReason(
  classInfo: UserClassInfo,
  quest: Quest,
): string | null {
  const all = [...classInfo.active_bonuses, ...classInfo.weaknesses];
  const flags = deriveQuestFlags(quest);

  // Berserker: portfolio blocked
  if (flags.required_portfolio && boolVal(all, "portfolio_blocked")) {
    return "Ваш класс не может брать квесты, требующие портфолио";
  }

  // Archmage: urgent blocked
  if (flags.is_urgent && boolVal(all, "urgent_blocked")) {
    return "Ваш класс не может брать срочные квесты";
  }

  // Rogue: exclusive contract blocked
  // Note: is_exclusive_contract is not a Quest field currently,
  // so we skip this check (cannot determine from card data).

  // Paladin: anonymous client blocked
  // Note: is_anonymous_client is not a Quest field currently,
  // so we skip this check.

  return null;
}

// ────────────────────────────────────────────
// Display helpers
// ────────────────────────────────────────────

/**
 * Format the XP multiplier into a human-readable badge string.
 * Returns null if no meaningful bonus/penalty (multiplier ~1.0).
 */
export function formatXpBadge(multiplier: number): string | null {
  const pct = Math.round((multiplier - 1.0) * 100);
  if (pct === 0) return null;
  return pct > 0 ? `+${pct}% XP` : `${pct}% XP`;
}
