"use client";

import React, { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { AnimatePresence, motion } from "@/lib/motion";

import ClassSelector from "@/components/rpg/ClassSelector";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import { useAuth } from "@/context/AuthContext";
import {
  completeOnboarding,
  getApiErrorMessage,
  getClasses,
  updateMyProfile,
  uploadMyAvatar,
} from "@/lib/api";
import type { CharacterClassInfo, UserBadgeEarned, UserProfile } from "@/lib/api";

type OnboardingStep = "class" | "skills" | "profile" | "badge";

const STEPS: { key: OnboardingStep; label: string }[] = [
  { key: "class", label: "Класс" },
  { key: "skills", label: "Навыки" },
  { key: "profile", label: "Профиль" },
  { key: "badge", label: "Готово!" },
];

const POPULAR_SKILLS = [
  "JavaScript", "TypeScript", "React", "Next.js", "Vue.js",
  "Python", "FastAPI", "Django", "Node.js", "Go",
  "PostgreSQL", "MongoDB", "Redis", "Docker", "Kubernetes",
  "HTML", "CSS", "Tailwind", "Figma", "UI/UX",
  "iOS", "Android", "Flutter", "React Native",
  "DevOps", "AWS", "Linux", "Git", "CI/CD",
  "Web Scraping", "aiogram", "Telegram Bot",
];

const AVAILABILITY_OPTIONS = [
  { value: "available", label: "Доступен", hint: "Готов брать квесты" },
  { value: "limited", label: "Частичная занятость", hint: "Могу взять 1–2 квеста" },
  { value: "busy", label: "Занят", hint: "Пока не беру новые квесты" },
];

function StepProgress({
  steps,
  currentIndex,
}: {
  steps: typeof STEPS;
  currentIndex: number;
}) {
  return (
    <div className="flex items-center justify-center gap-1 sm:gap-2 mb-8">
      {steps.map((step, index) => (
        <React.Fragment key={step.key}>
          <div className="flex flex-col items-center gap-1">
            <div
              className={`w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold transition-colors ${
                index < currentIndex
                  ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/50"
                  : index === currentIndex
                    ? "bg-amber-500/20 text-amber-400 border-2 border-amber-500"
                    : "bg-gray-800 text-gray-600 border border-gray-700"
              }`}
            >
              {index < currentIndex ? "✓" : index + 1}
            </div>
            <span
              className={`text-[10px] sm:text-xs whitespace-nowrap ${
                index === currentIndex ? "text-amber-400" : "text-gray-500"
              }`}
            >
              {step.label}
            </span>
          </div>
          {index < steps.length - 1 && (
            <div
              className={`w-8 sm:w-14 h-0.5 mt-[-18px] transition-colors ${
                index < currentIndex ? "bg-emerald-500/50" : "bg-gray-700"
              }`}
            />
          )}
        </React.Fragment>
      ))}
    </div>
  );
}

interface Props {
  user: UserProfile;
}

export default function OnboardingWizard({ user }: Props) {
  const router = useRouter();
  const { refreshUser } = useAuth();

  const [step, setStep] = useState<OnboardingStep>("class");
  const stepIndex = STEPS.findIndex((entry) => entry.key === step);

  const [skills, setSkills] = useState<string[]>(user.skills?.length ? user.skills : []);
  const [skillInput, setSkillInput] = useState("");
  const [bio, setBio] = useState(user.bio ?? "");
  const [availabilityStatus, setAvailabilityStatus] = useState(user.availability_status ?? "");
  const [avatarFile, setAvatarFile] = useState<File | null>(null);
  const [avatarUrl, setAvatarUrl] = useState<string | null>(user.avatar_url ?? null);
  const [avatarPreviewUrl, setAvatarPreviewUrl] = useState<string | null>(null);

  const [classModalOpen, setClassModalOpen] = useState(false);
  const [classes, setClasses] = useState<CharacterClassInfo[]>([]);
  const [classesLoaded, setClassesLoaded] = useState(false);
  const [earnedBadges, setEarnedBadges] = useState<UserBadgeEarned[]>([]);

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  React.useEffect(() => {
    if (!avatarFile) {
      setAvatarPreviewUrl(null);
      return undefined;
    }

    const objectUrl = URL.createObjectURL(avatarFile);
    setAvatarPreviewUrl(objectUrl);

    return () => {
      URL.revokeObjectURL(objectUrl);
    };
  }, [avatarFile]);

  const addSkill = useCallback(
    (skill: string) => {
      const trimmed = skill.trim();
      if (trimmed && !skills.includes(trimmed) && skills.length < 15) {
        setSkills((current) => [...current, trimmed]);
      }
      setSkillInput("");
    },
    [skills],
  );

  const removeSkill = (skill: string) => {
    setSkills((current) => current.filter((entry) => entry !== skill));
  };

  const handleSkillKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter" || event.key === ",") {
      event.preventDefault();
      addSkill(skillInput);
    }
    if (event.key === "Backspace" && !skillInput && skills.length) {
      setSkills((current) => current.slice(0, -1));
    }
  };

  const canAdvance = () => {
    if (step === "skills") return skills.length >= 2;
    if (step === "profile") return bio.trim().length >= 20;
    return true;
  };

  const persistProfileAndFinish = async () => {
    if (avatarFile) {
      const uploadResult = await uploadMyAvatar(avatarFile);
      setAvatarUrl(uploadResult.avatar_url);
      setAvatarFile(null);
    }

    await updateMyProfile({
      bio: bio.trim(),
      skills,
      availability_status: availabilityStatus || undefined,
    });

    const completionResult = await completeOnboarding();
    setEarnedBadges(completionResult.badges_earned ?? []);
    await refreshUser();
  };

  const goNext = async () => {
    setError(null);

    if (step === "profile") {
      setSaving(true);
      try {
        await persistProfileAndFinish();
      } catch (unknownError: unknown) {
        setError(getApiErrorMessage(unknownError, "Ошибка сохранения онбординга"));
        setSaving(false);
        return;
      }
      setSaving(false);
    }

    if (stepIndex < STEPS.length - 1) {
      setStep(STEPS[stepIndex + 1].key);
    }
  };

  const goPrev = () => {
    if (stepIndex > 0) {
      setError(null);
      setStep(STEPS[stepIndex - 1].key);
    }
  };

  const handleSkip = async () => {
    setSaving(true);
    try {
      if (avatarFile) {
        const uploadResult = await uploadMyAvatar(avatarFile);
        setAvatarUrl(uploadResult.avatar_url);
        setAvatarFile(null);
      }

      if (skills.length || bio.trim() || availabilityStatus) {
        await updateMyProfile({
          bio: bio.trim() || undefined,
          skills: skills.length ? skills : undefined,
          availability_status: availabilityStatus || undefined,
        });
      }

      await completeOnboarding();
      await refreshUser();
      router.push("/quests");
    } catch (e) {
      console.warn("Onboarding skip failed", e);
      router.push("/quests");
    }
  };

  const loadClasses = useCallback(async () => {
    if (classesLoaded) return;
    try {
      const response = await getClasses();
      setClasses(response.classes ?? []);
      setClassesLoaded(true);
    } catch {
      // Non-critical. The modal can retry later.
    }
  }, [classesLoaded]);

  React.useEffect(() => {
    if (step === "class") {
      loadClasses();
    }
  }, [loadClasses, step]);

  const displayedAvatar = avatarPreviewUrl || avatarUrl;

  return (
    <div className="min-h-screen bg-gray-950 text-white flex flex-col">
      <div className="flex-1 flex items-center justify-center px-4 py-8">
        <div className="w-full max-w-2xl">
          <div className="text-center mb-2">
            <h1 className="text-2xl sm:text-3xl font-cinzel text-amber-400">
              Настройка профиля
            </h1>
            <p className="text-gray-400 text-sm mt-1">
              {step === "badge" ? "Добро пожаловать в QuestionWork!" : `Шаг ${stepIndex + 1} из ${STEPS.length}`}
            </p>
          </div>

          <StepProgress steps={STEPS} currentIndex={stepIndex} />

          <AnimatePresence>
            {error && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm"
              >
                {error}
              </motion.div>
            )}
          </AnimatePresence>

          <AnimatePresence mode="wait">
            <motion.div
              key={step}
              initial={{ opacity: 0, x: 30 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -30 }}
              transition={{ duration: 0.25 }}
            >
              {step === "class" && (
                <Card variant="default" className="p-6 sm:p-8 text-center">
                  <h2 className="text-xl font-cinzel text-amber-300 mb-2">
                    Класс персонажа
                  </h2>
                  <p className="text-gray-400 text-sm mb-6">
                    Класс определяет ваши бонусы и стиль прокачки. На 1-м уровне все классы заблокированы,
                    но вы уже можете изучить их и выбрать позже в профиле.
                  </p>

                  {classes.length > 0 && (
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-6">
                      {classes.slice(0, 6).map((entry) => (
                        <div
                          key={entry.class_id}
                          className={`p-3 rounded-lg border text-center ${
                            entry.min_unlock_level > (user.level ?? 1)
                              ? "border-gray-700 bg-gray-800/30 opacity-60"
                              : "border-amber-500/30 bg-amber-500/5"
                          }`}
                        >
                          <div className="text-2xl mb-1">{entry.icon}</div>
                          <div className="text-sm font-medium text-white">{entry.name_ru}</div>
                          <div className="text-[10px] text-gray-500">
                            {entry.min_unlock_level > (user.level ?? 1)
                              ? `ур. ${entry.min_unlock_level}`
                              : "Доступен"}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  <Button variant="secondary" onClick={() => setClassModalOpen(true)}>
                    Подробнее о классах
                  </Button>

                  <p className="text-xs text-gray-500 mt-4">
                    Вы можете выбрать класс позже в разделе профиля
                  </p>

                  <ClassSelector
                    isOpen={classModalOpen}
                    onClose={() => setClassModalOpen(false)}
                    userLevel={user.level ?? 1}
                    currentClass={user.character_class ?? null}
                    onClassSelected={() => {
                      setClassModalOpen(false);
                      refreshUser();
                    }}
                  />
                </Card>
              )}

              {step === "skills" && (
                <Card variant="default" className="p-6 sm:p-8">
                  <h2 className="text-xl font-cinzel text-amber-300 mb-2">
                    Ваши навыки
                  </h2>
                  <p className="text-gray-400 text-sm mb-5">
                    Укажите минимум 2 навыка, чтобы мы могли подбирать подходящие квесты.
                  </p>

                  <div className="flex flex-wrap gap-2 p-3 rounded-lg bg-gray-800/50 border border-gray-700 mb-4 min-h-[48px]">
                    {skills.map((skill) => (
                      <span
                        key={skill}
                        className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-amber-500/15 text-amber-300 text-sm border border-amber-500/30"
                      >
                        {skill}
                        <button
                          type="button"
                          onClick={() => removeSkill(skill)}
                          className="ml-1 text-amber-400/60 hover:text-red-400 transition-colors"
                        >
                          ×
                        </button>
                      </span>
                    ))}
                    <input
                      type="text"
                      value={skillInput}
                      onChange={(event) => setSkillInput(event.target.value)}
                      onKeyDown={handleSkillKeyDown}
                      placeholder={skills.length ? "" : "Введите навык и нажмите Enter"}
                      className="flex-1 min-w-[120px] bg-transparent outline-none text-white text-sm placeholder-gray-500"
                    />
                  </div>

                  <p className="text-xs text-gray-500 mb-2">Популярные навыки:</p>
                  <div className="flex flex-wrap gap-1.5">
                    {POPULAR_SKILLS.filter((skill) => !skills.includes(skill)).map((skill) => (
                      <button
                        key={skill}
                        type="button"
                        onClick={() => addSkill(skill)}
                        className="px-2.5 py-1 rounded-full text-xs border border-gray-700 text-gray-400 hover:border-amber-500/50 hover:text-amber-300 transition-colors"
                      >
                        + {skill}
                      </button>
                    ))}
                  </div>

                  {skills.length > 0 && skills.length < 2 && (
                    <p className="text-xs text-amber-500/70 mt-3">
                      Добавьте ещё {2 - skills.length} навык
                    </p>
                  )}
                </Card>
              )}

              {step === "profile" && (
                <Card variant="default" className="p-6 sm:p-8">
                  <h2 className="text-xl font-cinzel text-amber-300 mb-2">
                    Профиль и аватар
                  </h2>
                  <p className="text-gray-400 text-sm mb-5">
                    Добавьте аватар и коротко расскажите клиентам о своём опыте и доступности.
                  </p>

                  <div className="mb-6 rounded-xl border border-gray-700 bg-gray-900/60 p-4">
                    <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-start">
                      <div className="h-24 w-24 overflow-hidden rounded-full border border-amber-500/30 bg-gray-800 flex items-center justify-center text-3xl text-gray-500">
                        {displayedAvatar ? (
                          <Image
                            src={displayedAvatar}
                            alt="Avatar preview"
                            width={96}
                            height={96}
                            className="h-full w-full object-cover"
                            unoptimized={displayedAvatar.startsWith("data:")}
                          />
                        ) : (
                          <span>🧙</span>
                        )}
                      </div>
                      <div className="w-full">
                        <label className="block text-sm font-medium text-gray-300 mb-2">
                          Аватар
                        </label>
                        <input
                          type="file"
                          accept="image/png,image/jpeg,image/webp"
                          onChange={(event) => setAvatarFile(event.target.files?.[0] ?? null)}
                          className="block w-full text-sm text-gray-300 file:mr-4 file:rounded-md file:border-0 file:bg-amber-500/20 file:px-4 file:py-2 file:text-sm file:font-medium file:text-amber-300 hover:file:bg-amber-500/30"
                        />
                        <p className="mt-2 text-xs text-gray-500">
                          PNG, JPG или WebP до 512 KB.
                        </p>
                      </div>
                    </div>
                  </div>

                  <textarea
                    value={bio}
                    onChange={(event) => setBio(event.target.value)}
                    placeholder="Я специализируюсь на..."
                    rows={4}
                    maxLength={500}
                    className="w-full p-3 rounded-lg bg-gray-800/50 border border-gray-700 text-white text-sm placeholder-gray-500 resize-none focus:outline-none focus:border-amber-500/50 transition-colors"
                  />
                  <div className="flex justify-between text-xs text-gray-500 mt-1 mb-6">
                    <span>
                      {bio.trim().length < 20
                        ? `Минимум 20 символов (ещё ${20 - bio.trim().length})`
                        : "Отлично!"}
                    </span>
                    <span>{bio.length}/500</span>
                  </div>

                  <h3 className="text-sm font-medium text-gray-300 mb-3">
                    Доступность
                  </h3>
                  <div className="grid gap-2">
                    {AVAILABILITY_OPTIONS.map((option) => (
                      <label
                        key={option.value}
                        className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                          availabilityStatus === option.value
                            ? "border-amber-500/50 bg-amber-500/10"
                            : "border-gray-700 bg-gray-800/30 hover:border-gray-600"
                        }`}
                      >
                        <input
                          type="radio"
                          name="availability"
                          value={option.value}
                          checked={availabilityStatus === option.value}
                          onChange={(event) => setAvailabilityStatus(event.target.value)}
                          className="accent-amber-500"
                        />
                        <div>
                          <div className="text-sm text-white">{option.label}</div>
                          <div className="text-xs text-gray-500">{option.hint}</div>
                        </div>
                      </label>
                    ))}
                  </div>
                </Card>
              )}

              {step === "badge" && (
                <div className="text-center py-8">
                  <motion.div
                    initial={{ scale: 0, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    transition={{
                      type: "spring",
                      stiffness: 200,
                      damping: 15,
                      delay: 0.2,
                    }}
                    className="mb-6"
                  >
                    <div className="w-28 h-28 mx-auto rounded-full bg-gradient-to-br from-amber-500/30 to-yellow-600/20 border-2 border-amber-500 flex items-center justify-center shadow-[0_0_40px_rgba(245,158,11,0.3)]">
                      {earnedBadges.length > 0 && earnedBadges[0].badge_icon ? (
                        <Image
                          src={earnedBadges[0].badge_icon}
                          alt={earnedBadges[0].badge_name}
                          width={64}
                          height={64}
                          className="w-16 h-16"
                          onError={(event) => {
                            (event.target as HTMLImageElement).style.display = "none";
                            (event.target as HTMLImageElement).parentElement
                              ?.querySelector(".fallback")
                              ?.classList.remove("hidden");
                          }}
                        />
                      ) : null}
                      <span className={`text-5xl ${earnedBadges.length > 0 && earnedBadges[0].badge_icon ? "fallback hidden" : ""}`}>
                        🛡️
                      </span>
                    </div>
                  </motion.div>

                  <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.5 }}
                  >
                    <h2 className="text-2xl font-cinzel text-amber-400 mb-2">
                      Добро пожаловать!
                    </h2>

                    {earnedBadges.length > 0 && (
                      <div className="mb-4">
                        <p className="text-gray-400 text-sm mb-1">
                          Вы получили бейдж:
                        </p>
                        <motion.div
                          initial={{ scale: 0.8, opacity: 0 }}
                          animate={{ scale: 1, opacity: 1 }}
                          transition={{ delay: 0.8 }}
                          className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-amber-500/10 border border-amber-500/30"
                        >
                          <span className="text-lg">🏅</span>
                          <span className="text-amber-300 font-medium">
                            {earnedBadges[0].badge_name}
                          </span>
                        </motion.div>
                      </div>
                    )}

                    <p className="text-gray-400 text-sm max-w-md mx-auto mb-8">
                      Ваш профиль настроен. Теперь самое время взять первый квест и начать зарабатывать XP!
                    </p>

                    <div className="flex flex-col sm:flex-row gap-3 justify-center">
                      <Button
                        variant="primary"
                        size="lg"
                        onClick={() => router.push("/quests")}
                      >
                        Взять первый квест
                      </Button>
                      <Button
                        variant="ghost"
                        onClick={() => router.push("/profile")}
                      >
                        Перейти в профиль
                      </Button>
                    </div>
                  </motion.div>
                </div>
              )}
            </motion.div>
          </AnimatePresence>

          {step !== "badge" && (
            <div className="flex items-center justify-between mt-6">
              <button
                type="button"
                onClick={handleSkip}
                disabled={saving}
                className="text-sm text-gray-500 hover:text-gray-300 transition-colors disabled:opacity-50"
              >
                Пропустить
              </button>

              <div className="flex gap-3">
                {stepIndex > 0 && (
                  <Button variant="ghost" onClick={goPrev} disabled={saving}>
                    Назад
                  </Button>
                )}
                <Button
                  variant="primary"
                  onClick={goNext}
                  disabled={!canAdvance() || saving}
                  loading={saving}
                  loadingLabel="Сохраняем..."
                >
                  {step === "profile" ? "Завершить" : "Далее"}
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
