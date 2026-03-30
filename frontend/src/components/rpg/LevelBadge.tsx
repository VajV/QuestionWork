interface LevelBadgeProps {
  level: number;
  grade: string;
  size?: 'sm' | 'md' | 'lg';
  showGradeText?: boolean;
}

export default function LevelBadge({ level, grade, size = 'md', showGradeText = true }: LevelBadgeProps) {
  const gradeClass = grade.toLowerCase();
  
  let scale = "scale-100";
  if (size === 'sm') scale = "scale-75";
  if (size === 'lg') scale = "scale-125";

  return (
    <div className={`flex flex-col items-center gap-2 ${scale}`}>
      <div className="relative inline-flex items-center justify-center w-16 h-16">
        <div 
          className="absolute inset-0 opacity-20 animate-rotate border rounded-lg"
          style={{ 
            backgroundColor: `var(--rarity-${gradeClass}, var(--rarity-novice))`,
            borderColor: `var(--rarity-${gradeClass}, var(--rarity-novice))` 
          }}
        ></div>
        
        <div 
          className="relative z-10 w-12 h-12 rounded-full border-2 bg-black flex items-center justify-center"
          style={{ 
            borderColor: `var(--rarity-${gradeClass}, var(--rarity-novice))`,
            boxShadow: `0 0 15px var(--rarity-${gradeClass}, var(--rarity-novice))`
          }}
        >
          <span 
            className="text-xl font-cinzel font-bold"
            style={{ color: `var(--rarity-${gradeClass}, var(--rarity-novice))` }}
          >
            {level}
          </span>
        </div>
      </div>
      {showGradeText && (
        <span 
          className={`text-sm font-cinzel tracking-widest uppercase grade-glow-${gradeClass}`}
          style={{ color: `var(--rarity-${gradeClass}, var(--rarity-novice))` }}
        >
          {grade}
        </span>
      )}
    </div>
  );
}
