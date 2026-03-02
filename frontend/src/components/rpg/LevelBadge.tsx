interface LevelBadgeProps {
  level: number;
  grade: string;
  size?: 'sm' | 'md' | 'lg';
}

const gradeColors = {
  novice: 'from-gray-500 to-gray-700',
  junior: 'from-green-500 to-green-700',
  middle: 'from-blue-500 to-blue-700',
  senior: 'from-purple-500 to-purple-700',
};

export default function LevelBadge({ level, grade, size = 'md' }: LevelBadgeProps) {
  const sizeStyles = {
    sm: 'text-xs px-2 py-0.5',
    md: 'text-sm px-3 py-1',
    lg: 'text-base px-4 py-1.5',
  };

  const gradient = gradeColors[grade as keyof typeof gradeColors] || gradeColors.Novice;

  return (
    <div className={`bg-gradient-to-r ${gradient} ${sizeStyles[size]} rounded-full font-bold shadow-lg`}>
      Lv.{level} {grade}
    </div>
  );
}
