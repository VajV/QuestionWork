"use client";

import { useCallback, useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  X,
  Save,
  Ban,
  ShieldCheck,
  Trash2,
  Zap,
  Wallet,
  Swords,
  Award,
  AlertTriangle,
  Loader2,
  CheckCircle,
  XCircle,
} from "lucide-react";
import {
  adminGetUserDetail,
  adminUpdateUser,
  adminBanUser,
  adminUnbanUser,
  adminDeleteUser,
  adminGrantXP,
  adminAdjustWallet,
  adminGrantBadge,
  adminRevokeBadge,
  adminChangeUserClass,
} from "@/lib/api";
import type { AdminUserDetail } from "@/types";

type Tab = "profile" | "economy" | "class" | "badges" | "danger";

interface Props {
  userId: string;
  onClose: () => void;
  onUpdated: () => void;
}

function Toast({ msg, type }: { msg: string; type: "ok" | "err" }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      className={`fixed top-4 right-4 z-[200] flex items-center gap-2 rounded-lg px-4 py-3 text-sm shadow-lg ${
        type === "ok"
          ? "bg-green-600/90 text-white"
          : "bg-red-600/90 text-white"
      }`}
    >
      {type === "ok" ? <CheckCircle size={16} /> : <XCircle size={16} />}
      {msg}
    </motion.div>
  );
}

export default function EditUserModal({ userId, onClose, onUpdated }: Props) {
  const [user, setUser] = useState<AdminUserDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<Tab>("profile");
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<{ msg: string; type: "ok" | "err" } | null>(null);

  // Profile form
  const [role, setRole] = useState("");
  const [level, setLevel] = useState(1);
  const [grade, setGrade] = useState("novice");
  const [xp, setXp] = useState(0);
  const [statPoints, setStatPoints] = useState(0);
  const [statsInt, setStatsInt] = useState(10);
  const [statsDex, setStatsDex] = useState(10);
  const [statsCha, setStatsCha] = useState(10);
  const [bio, setBio] = useState("");
  const [characterClass, setCharacterClass] = useState<string>("");

  // Economy
  const [xpAmount, setXpAmount] = useState(0);
  const [xpReason, setXpReason] = useState("");
  const [walletAmount, setWalletAmount] = useState(0);
  const [walletCurrency, setWalletCurrency] = useState("RUB");
  const [walletReason, setWalletReason] = useState("");

  // Ban
  const [banReason, setBanReason] = useState("");
  const [deleteConfirm, setDeleteConfirm] = useState(false);

  // Badge
  const [badgeId, setBadgeId] = useState("");

  // Class
  const [newClassId, setNewClassId] = useState<string>("");

  const flash = useCallback((msg: string, type: "ok" | "err") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  }, []);

  const loadUser = useCallback(async () => {
    setLoading(true);
    try {
      const data = await adminGetUserDetail(userId);
      setUser(data);
      setRole(data.role);
      setLevel(data.level);
      setGrade(data.grade);
      setXp(data.xp);
      setStatPoints(data.stat_points);
      setStatsInt(data.stats_int);
      setStatsDex(data.stats_dex);
      setStatsCha(data.stats_cha);
      setBio(data.bio || "");
      setCharacterClass(data.character_class || "");
      setNewClassId(data.character_class || "");
    } catch {
      flash("Не удалось загрузить пользователя", "err");
    } finally {
      setLoading(false);
    }
  }, [userId, flash]);

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  const handleSaveProfile = async () => {
    if (!user) return;
    setSaving(true);
    try {
      const fields: Record<string, unknown> = {};
      if (role !== user.role) fields.role = role;
      if (level !== user.level) fields.level = level;
      if (grade !== user.grade) fields.grade = grade;
      if (xp !== user.xp) fields.xp = xp;
      if (statPoints !== user.stat_points) fields.stat_points = statPoints;
      if (statsInt !== user.stats_int) fields.stats_int = statsInt;
      if (statsDex !== user.stats_dex) fields.stats_dex = statsDex;
      if (statsCha !== user.stats_cha) fields.stats_cha = statsCha;
      if (bio !== (user.bio || "")) fields.bio = bio;
      if (characterClass !== (user.character_class || "")) fields.character_class = characterClass || null;
      if (Object.keys(fields).length === 0) {
        flash("Нет изменений", "err");
        return;
      }
      await adminUpdateUser(userId, fields);
      flash("Профиль обновлён", "ok");
      await loadUser();
      onUpdated();
    } catch (e: unknown) {
      const msg = e instanceof Response ? e.statusText : String(e);
      flash(msg || "Ошибка", "err");
    } finally {
      setSaving(false);
    }
  };

  const handleGrantXP = async () => {
    if (!xpAmount || !xpReason.trim()) { flash("Укажите количество и причину", "err"); return; }
    setSaving(true);
    try {
      const r = await adminGrantXP(userId, xpAmount, xpReason);
      flash(`XP: ${r.old_xp} → ${r.new_xp}${r.level_up ? " (Level Up!)" : ""}`, "ok");
      setXpAmount(0); setXpReason("");
      await loadUser();
      onUpdated();
    } catch (e: unknown) {
      const msg = e instanceof Response ? e.statusText : String(e);
      flash(msg || "Ошибка", "err");
    } finally {
      setSaving(false);
    }
  };

  const handleAdjustWallet = async () => {
    if (!walletAmount || !walletReason.trim()) { flash("Укажите сумму и причину", "err"); return; }
    setSaving(true);
    try {
      const r = await adminAdjustWallet(userId, walletAmount, walletCurrency, walletReason);
      flash(`Баланс: ${r.old_balance} → ${r.new_balance} ${r.currency}`, "ok");
      setWalletAmount(0); setWalletReason("");
      await loadUser();
      onUpdated();
    } catch (e: unknown) {
      const msg = e instanceof Response ? e.statusText : String(e);
      flash(msg || "Ошибка", "err");
    } finally {
      setSaving(false);
    }
  };

  const handleBan = async () => {
    if (banReason.length < 5) { flash("Причина мин. 5 символов", "err"); return; }
    setSaving(true);
    try {
      const r = await adminBanUser(userId, banReason);
      flash(`${r.username} забанен. Отменено квестов: ${r.quests_cancelled}`, "ok");
      setBanReason("");
      await loadUser();
      onUpdated();
    } catch (e: unknown) {
      const msg = e instanceof Response ? e.statusText : String(e);
      flash(msg || "Ошибка", "err");
    } finally {
      setSaving(false);
    }
  };

  const handleUnban = async () => {
    setSaving(true);
    try {
      await adminUnbanUser(userId);
      flash("Пользователь разбанен", "ok");
      await loadUser();
      onUpdated();
    } catch (e: unknown) {
      const msg = e instanceof Response ? e.statusText : String(e);
      flash(msg || "Ошибка", "err");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteConfirm) { setDeleteConfirm(true); return; }
    setSaving(true);
    try {
      await adminDeleteUser(userId);
      flash("Пользователь удалён", "ok");
      onUpdated();
      setTimeout(onClose, 1000);
    } catch (e: unknown) {
      const msg = e instanceof Response ? e.statusText : String(e);
      flash(msg || "Ошибка", "err");
    } finally {
      setSaving(false);
      setDeleteConfirm(false);
    }
  };

  const handleGrantBadge = async () => {
    if (!badgeId.trim()) { flash("Укажите ID бейджа", "err"); return; }
    setSaving(true);
    try {
      const r = await adminGrantBadge(userId, badgeId);
      flash(`Бейдж «${r.badge_name}» выдан`, "ok");
      setBadgeId("");
      await loadUser();
    } catch (e: unknown) {
      const msg = e instanceof Response ? e.statusText : String(e);
      flash(msg || "Ошибка", "err");
    } finally {
      setSaving(false);
    }
  };

  const handleRevokeBadge = async (bid: string) => {
    setSaving(true);
    try {
      await adminRevokeBadge(userId, bid);
      flash("Бейдж отозван", "ok");
      await loadUser();
    } catch (e: unknown) {
      const msg = e instanceof Response ? e.statusText : String(e);
      flash(msg || "Ошибка", "err");
    } finally {
      setSaving(false);
    }
  };

  const handleChangeClass = async () => {
    setSaving(true);
    try {
      const r = await adminChangeUserClass(userId, newClassId || null);
      flash(`Класс: ${r.old_class || "нет"} → ${r.new_class || "нет"}`, "ok");
      await loadUser();
      onUpdated();
    } catch (e: unknown) {
      const msg = e instanceof Response ? e.statusText : String(e);
      flash(msg || "Ошибка", "err");
    } finally {
      setSaving(false);
    }
  };

  const TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
    { id: "profile", label: "Профиль", icon: <ShieldCheck size={16} /> },
    { id: "economy", label: "Экономика", icon: <Wallet size={16} /> },
    { id: "class", label: "Класс", icon: <Swords size={16} /> },
    { id: "badges", label: "Бейджи", icon: <Award size={16} /> },
    { id: "danger", label: "Опасная зона", icon: <AlertTriangle size={16} /> },
  ];

  const inputCls = "w-full rounded-lg border border-gray-600 bg-gray-700 px-3 py-2 text-sm text-gray-100 focus:border-purple-500 focus:outline-none";
  const btnPrimary = "inline-flex items-center gap-2 rounded-lg bg-purple-600 px-4 py-2 text-sm font-medium text-white hover:bg-purple-700 disabled:opacity-50";
  const btnDanger = "inline-flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50";
  const btnSecondary = "inline-flex items-center gap-2 rounded-lg border border-gray-600 px-4 py-2 text-sm font-medium text-gray-300 hover:bg-gray-700 disabled:opacity-50";
  const labelCls = "block text-xs font-medium text-gray-400 mb-1";

  return (
    <>
      <AnimatePresence>{toast && <Toast msg={toast.msg} type={toast.type} />}</AnimatePresence>

      {/* Backdrop */}
      <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 p-4">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.95 }}
          className="relative max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl border border-gray-700 bg-gray-800 shadow-2xl"
        >
          {/* Header */}
          <div className="sticky top-0 z-10 flex items-center justify-between border-b border-gray-700 bg-gray-800/95 px-6 py-4 backdrop-blur">
            <div>
              <h2 className="text-lg font-bold text-white">
                {user ? `${user.username}` : "Загрузка…"}
                {user?.is_banned && (
                  <span className="ml-2 rounded bg-red-500/20 px-2 py-0.5 text-xs text-red-400">
                    BANNED
                  </span>
                )}
              </h2>
              {user && <p className="text-xs text-gray-400">ID: {user.id}</p>}
            </div>
            <button onClick={onClose} className="rounded-lg p-2 text-gray-400 hover:bg-gray-700 hover:text-white">
              <X size={20} />
            </button>
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="animate-spin text-purple-400" size={32} />
            </div>
          ) : user ? (
            <>
              {/* Tabs */}
              <div className="flex gap-1 border-b border-gray-700 px-6">
                {TABS.map((t) => (
                  <button
                    key={t.id}
                    onClick={() => setTab(t.id)}
                    className={`flex items-center gap-1.5 border-b-2 px-3 py-3 text-xs font-medium transition-colors ${
                      tab === t.id
                        ? "border-purple-500 text-purple-400"
                        : "border-transparent text-gray-400 hover:text-gray-200"
                    }`}
                  >
                    {t.icon} {t.label}
                  </button>
                ))}
              </div>

              <div className="p-6">
                {/* ── Profile tab ── */}
                {tab === "profile" && (
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className={labelCls}>Роль</label>
                        <select value={role} onChange={(e) => setRole(e.target.value)} className={inputCls}>
                          <option value="freelancer">Фрилансер</option>
                          <option value="client">Клиент</option>
                          <option value="admin">Админ</option>
                        </select>
                      </div>
                      <div>
                        <label className={labelCls}>Грейд</label>
                        <select value={grade} onChange={(e) => setGrade(e.target.value)} className={inputCls}>
                          <option value="novice">Novice</option>
                          <option value="junior">Junior</option>
                          <option value="middle">Middle</option>
                          <option value="senior">Senior</option>
                        </select>
                      </div>
                      <div>
                        <label className={labelCls}>Уровень</label>
                        <input type="number" min={1} max={100} value={level} onChange={(e) => setLevel(+e.target.value)} className={inputCls} />
                      </div>
                      <div>
                        <label className={labelCls}>XP</label>
                        <input type="number" min={0} value={xp} onChange={(e) => setXp(+e.target.value)} className={inputCls} />
                      </div>
                      <div>
                        <label className={labelCls}>Очки стат</label>
                        <input type="number" min={0} value={statPoints} onChange={(e) => setStatPoints(+e.target.value)} className={inputCls} />
                      </div>
                    </div>
                    <div className="grid grid-cols-3 gap-4">
                      <div>
                        <label className={labelCls}>INT</label>
                        <input type="number" min={1} max={100} value={statsInt} onChange={(e) => setStatsInt(+e.target.value)} className={inputCls} />
                      </div>
                      <div>
                        <label className={labelCls}>DEX</label>
                        <input type="number" min={1} max={100} value={statsDex} onChange={(e) => setStatsDex(+e.target.value)} className={inputCls} />
                      </div>
                      <div>
                        <label className={labelCls}>CHA</label>
                        <input type="number" min={1} max={100} value={statsCha} onChange={(e) => setStatsCha(+e.target.value)} className={inputCls} />
                      </div>
                    </div>
                    <div>
                      <label className={labelCls}>Био</label>
                      <textarea value={bio} onChange={(e) => setBio(e.target.value)} maxLength={500} rows={3} className={inputCls} />
                    </div>
                    <div>
                      <label className={labelCls}>Класс</label>
                      <input value={characterClass} onChange={(e) => setCharacterClass(e.target.value)} placeholder="berserk / scout / sage / ..." className={inputCls} />
                    </div>
                    <button onClick={handleSaveProfile} disabled={saving} className={btnPrimary}>
                      {saving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
                      Сохранить профиль
                    </button>
                  </div>
                )}

                {/* ── Economy tab ── */}
                {tab === "economy" && (
                  <div className="space-y-6">
                    {/* Wallets overview */}
                    <div>
                      <h3 className="mb-2 text-sm font-semibold text-gray-300">Кошельки</h3>
                      {user.wallets.length === 0 ? (
                        <p className="text-xs text-gray-500">Нет кошельков</p>
                      ) : (
                        <div className="grid grid-cols-2 gap-3">
                          {user.wallets.map((w) => (
                            <div key={w.id} className="rounded-lg border border-gray-700 bg-gray-700/50 p-3">
                              <div className="text-lg font-bold text-white">{Number(w.balance).toLocaleString()}</div>
                              <div className="text-xs text-gray-400">{w.currency}</div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Grant XP */}
                    <div className="rounded-lg border border-gray-700 p-4">
                      <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-yellow-400">
                        <Zap size={16} /> Начислить / Снять XP
                      </h3>
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <label className={labelCls}>Количество (- для снятия)</label>
                          <input type="number" value={xpAmount} onChange={(e) => setXpAmount(+e.target.value)} className={inputCls} />
                        </div>
                        <div>
                          <label className={labelCls}>Причина</label>
                          <input value={xpReason} onChange={(e) => setXpReason(e.target.value)} placeholder="Награда / штраф..." className={inputCls} />
                        </div>
                      </div>
                      <button onClick={handleGrantXP} disabled={saving} className={`mt-3 ${btnPrimary}`}>
                        {saving ? <Loader2 size={16} className="animate-spin" /> : <Zap size={16} />}
                        Применить
                      </button>
                    </div>

                    {/* Adjust Wallet */}
                    <div className="rounded-lg border border-gray-700 p-4">
                      <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-green-400">
                        <Wallet size={16} /> Начислить / Снять средства
                      </h3>
                      <div className="grid grid-cols-3 gap-3">
                        <div>
                          <label className={labelCls}>Сумма (- для снятия)</label>
                          <input type="number" value={walletAmount} onChange={(e) => setWalletAmount(+e.target.value)} className={inputCls} />
                        </div>
                        <div>
                          <label className={labelCls}>Валюта</label>
                          <select value={walletCurrency} onChange={(e) => setWalletCurrency(e.target.value)} className={inputCls}>
                            <option value="RUB">RUB</option>
                            <option value="USD">USD</option>
                            <option value="EUR">EUR</option>
                          </select>
                        </div>
                        <div>
                          <label className={labelCls}>Причина</label>
                          <input value={walletReason} onChange={(e) => setWalletReason(e.target.value)} placeholder="Компенсация / штраф..." className={inputCls} />
                        </div>
                      </div>
                      <button onClick={handleAdjustWallet} disabled={saving} className={`mt-3 ${btnPrimary}`}>
                        {saving ? <Loader2 size={16} className="animate-spin" /> : <Wallet size={16} />}
                        Применить
                      </button>
                    </div>
                  </div>
                )}

                {/* ── Class tab ── */}
                {tab === "class" && (
                  <div className="space-y-4">
                    <div className="rounded-lg border border-gray-700 bg-gray-700/50 p-4">
                      <h3 className="text-sm font-semibold text-gray-300">Текущий класс</h3>
                      <p className="mt-1 text-lg font-bold text-white">
                        {user.character_class || "Не выбран"}
                      </p>
                      {user.class_progress && (
                        <div className="mt-2 grid grid-cols-3 gap-3 text-xs text-gray-400">
                          <div>Class Level: <span className="text-white">{user.class_progress.class_level}</span></div>
                          <div>Class XP: <span className="text-white">{user.class_progress.class_xp}</span></div>
                          <div>Quests: <span className="text-white">{user.class_progress.quests_completed}</span></div>
                          <div>Perks spent: <span className="text-white">{user.class_progress.perk_points_spent}</span></div>
                          <div>Consecutive: <span className="text-white">{user.class_progress.consecutive_quests}</span></div>
                          {user.class_progress.burnout_until && (
                            <div>Burnout until: <span className="text-red-400">{new Date(user.class_progress.burnout_until).toLocaleString()}</span></div>
                          )}
                        </div>
                      )}
                    </div>

                    {/* Perks */}
                    {user.perks.length > 0 && (
                      <div>
                        <h3 className="mb-2 text-sm font-semibold text-gray-300">Перки ({user.perks.length})</h3>
                        <div className="flex flex-wrap gap-2">
                          {user.perks.map((p) => (
                            <span key={p.perk_id} className="rounded-full bg-purple-500/20 px-3 py-1 text-xs text-purple-300">
                              {p.perk_id}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Change class */}
                    <div className="rounded-lg border border-gray-700 p-4">
                      <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-blue-400">
                        <Swords size={16} /> Изменить класс
                      </h3>
                      <div>
                        <label className={labelCls}>Новый класс (пусто = сбросить)</label>
                        <select value={newClassId} onChange={(e) => setNewClassId(e.target.value)} className={inputCls}>
                          <option value="">Нет (сброс)</option>
                          <option value="berserk">Берсерк</option>
                          <option value="scout">Скаут</option>
                          <option value="sage">Мудрец</option>
                          <option value="trader">Торговец</option>
                        </select>
                      </div>
                      <button onClick={handleChangeClass} disabled={saving} className={`mt-3 ${btnPrimary}`}>
                        {saving ? <Loader2 size={16} className="animate-spin" /> : <Swords size={16} />}
                        Применить
                      </button>
                    </div>
                  </div>
                )}

                {/* ── Badges tab ── */}
                {tab === "badges" && (
                  <div className="space-y-4">
                    <div>
                      <h3 className="mb-2 text-sm font-semibold text-gray-300">
                        Бейджи ({user.badges_list.length})
                      </h3>
                      {user.badges_list.length === 0 ? (
                        <p className="text-xs text-gray-500">Нет бейджей</p>
                      ) : (
                        <div className="space-y-2">
                          {user.badges_list.map((b) => (
                            <div key={b.badge_id} className="flex items-center justify-between rounded-lg border border-gray-700 bg-gray-700/50 px-4 py-2">
                              <div className="flex items-center gap-3">
                                <span className="text-2xl">{b.icon}</span>
                                <div>
                                  <div className="text-sm font-medium text-white">{b.name}</div>
                                  <div className="text-xs text-gray-400">{b.description}</div>
                                </div>
                              </div>
                              <button
                                onClick={() => handleRevokeBadge(b.badge_id)}
                                disabled={saving}
                                className="rounded p-1.5 text-red-400 hover:bg-red-500/20"
                                title="Отозвать"
                              >
                                <XCircle size={16} />
                              </button>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                    <div className="rounded-lg border border-gray-700 p-4">
                      <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-yellow-400">
                        <Award size={16} /> Выдать бейдж
                      </h3>
                      <div>
                        <label className={labelCls}>Badge ID</label>
                        <input value={badgeId} onChange={(e) => setBadgeId(e.target.value)} placeholder="badge_..." className={inputCls} />
                      </div>
                      <button onClick={handleGrantBadge} disabled={saving} className={`mt-3 ${btnPrimary}`}>
                        {saving ? <Loader2 size={16} className="animate-spin" /> : <Award size={16} />}
                        Выдать
                      </button>
                    </div>
                  </div>
                )}

                {/* ── Danger tab ── */}
                {tab === "danger" && (
                  <div className="space-y-6">
                    {/* Ban / Unban */}
                    <div className="rounded-lg border border-red-800/50 bg-red-900/10 p-4">
                      <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-red-400">
                        <Ban size={16} /> {user.is_banned ? "Пользователь забанен" : "Бан пользователя"}
                      </h3>
                      {user.is_banned ? (
                        <div>
                          <p className="mb-2 text-xs text-gray-400">
                            Причина: <span className="text-red-300">{user.banned_reason}</span>
                          </p>
                          <button onClick={handleUnban} disabled={saving} className={btnSecondary}>
                            {saving ? <Loader2 size={16} className="animate-spin" /> : <ShieldCheck size={16} />}
                            Разбанить
                          </button>
                        </div>
                      ) : (
                        <div>
                          <label className={labelCls}>Причина бана (мин. 5 символов)</label>
                          <input value={banReason} onChange={(e) => setBanReason(e.target.value)} placeholder="Нарушение правил..." className={inputCls} />
                          <button onClick={handleBan} disabled={saving || banReason.length < 5} className={`mt-3 ${btnDanger}`}>
                            {saving ? <Loader2 size={16} className="animate-spin" /> : <Ban size={16} />}
                            Забанить
                          </button>
                        </div>
                      )}
                    </div>

                    {/* Delete */}
                    <div className="rounded-lg border border-red-800/50 bg-red-900/10 p-4">
                      <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-red-400">
                        <Trash2 size={16} /> Удаление аккаунта
                      </h3>
                      <p className="mb-3 text-xs text-gray-400">
                        Полное удаление пользователя и всех связанных данных. Действие необратимо.
                      </p>
                      <button
                        onClick={handleDelete}
                        disabled={saving}
                        className={btnDanger}
                      >
                        {saving ? <Loader2 size={16} className="animate-spin" /> : <Trash2 size={16} />}
                        {deleteConfirm ? "Подтвердить удаление" : "Удалить пользователя"}
                      </button>
                      {deleteConfirm && (
                        <button onClick={() => setDeleteConfirm(false)} className={`ml-2 ${btnSecondary}`}>
                          Отмена
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="flex items-center justify-center py-20 text-red-400">
              Пользователь не найден
            </div>
          )}
        </motion.div>
      </div>
    </>
  );
}
