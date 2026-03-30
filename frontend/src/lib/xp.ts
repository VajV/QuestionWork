export interface XpDisplay {
  isMax: boolean;
  label: string;
  percent: number;
}

export function getXpDisplay(xp: number, xpToNext: number): XpDisplay {
  if (xpToNext <= 0) {
    return {
      isMax: true,
      label: `${xp} XP • MAX`,
      percent: 100,
    };
  }

  return {
    isMax: false,
    label: `${xp} XP • ${xpToNext} до следующего грейда`,
    percent: Math.min(100, Math.max(0, (xp / xpToNext) * 100)),
  };
}