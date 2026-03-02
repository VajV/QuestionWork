/**
 * Shared TypeScript types for the QuestionWork frontend.
 *
 * Interfaces that are used across multiple pages/components live here
 * to avoid copy-paste duplication.
 */

import type { UserGrade, QuestStatus } from "@/lib/api";

/**
 * Filter state for the quest marketplace list.
 * Shared by QuestsPage and QuestFilters component.
 */
export interface QuestFilterState {
  grade?: UserGrade;
  status?: QuestStatus;
  skill?: string;
  minBudget?: number;
  maxBudget?: number;
}
