import React, { useEffect, useState } from 'react';
import { Sun, Moon, User, Mail, Shield, Lock, ChevronDown, CheckCircle2, Eye, EyeOff } from 'lucide-react';
import { useTheme } from '../context/ThemeContext';
import api from '../api/axios';

/* ── helpers ─────────────────────────────────────────────────────────── */

const inputCls =
    'w-full px-4 py-3 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-[#00FF85]/50 transition-colors';

const inputStyle = {
    backgroundColor: 'var(--bg-base)',
    border: '1px solid var(--border)',
    color: 'var(--text-primary)',
};

/* ── PasswordInput ───────────────────────────────────────────────────── */
const PasswordInput: React.FC<{
    placeholder: string;
    value: string;
    onChange: (v: string) => void;
    autoComplete?: string;
}> = ({ placeholder, value, onChange, autoComplete }) => {
    const [show, setShow] = useState(false);
    return (
        <div className="relative">
            <input
                type={show ? 'text' : 'password'}
                autoComplete={autoComplete}
                placeholder={placeholder}
                value={value}
                onChange={e => onChange(e.target.value)}
                className={inputCls + ' pr-11'}
                style={inputStyle}
            />
            <button
                type="button"
                onClick={() => setShow(s => !s)}
                className="absolute right-3 top-1/2 -translate-y-1/2"
                style={{ color: 'var(--text-muted)' }}
                tabIndex={-1}
            >
                {show ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
        </div>
    );
};

/* ── CollapsibleSection ──────────────────────────────────────────────── */
const CollapsibleSection: React.FC<{
    icon: React.ReactNode;
    title: string;
    description: string;
    children: React.ReactNode;
    defaultOpen?: boolean;
}> = ({ icon, title, description, children, defaultOpen = false }) => {
    const [open, setOpen] = useState(defaultOpen);
    return (
        <div
            className="rounded-2xl overflow-hidden transition-colors"
            style={{ backgroundColor: 'var(--bg-elevated)', border: '1px solid var(--border)' }}
        >
            <button
                onClick={() => setOpen(o => !o)}
                className="w-full flex items-center gap-3 px-5 py-4 text-left"
            >
                <span style={{ color: 'var(--text-muted)' }}>{icon}</span>
                <div className="flex-1">
                    <p className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>{title}</p>
                    <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{description}</p>
                </div>
                <ChevronDown
                    size={16}
                    style={{ color: 'var(--text-muted)', transform: open ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.2s' }}
                />
            </button>
            {open && (
                <div className="px-5 pb-5 pt-1 border-t" style={{ borderColor: 'var(--border)' }}>
                    {children}
                </div>
            )}
        </div>
    );
};

/* ── SettingsRow ─────────────────────────────────────────────────────── */
interface SettingsRowProps {
    icon: React.ReactNode;
    label: string;
    value: string;
    disabled?: boolean;
}
const SettingsRow: React.FC<SettingsRowProps> = ({ icon, label, value, disabled }) => (
    <div
        className={`flex items-center justify-between px-4 py-3.5 rounded-2xl transition-colors ${disabled ? '' : 'cursor-default'}`}
        style={{ backgroundColor: 'var(--bg-elevated)' }}
    >
        <div className="flex items-center gap-3">
            <span style={{ color: 'var(--text-muted)' }}>{icon}</span>
            <span className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>{label}</span>
        </div>
        <span className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>{value}</span>
    </div>
);

/* ── SuccessBanner ───────────────────────────────────────────────────── */
const SuccessBanner: React.FC<{ message: string }> = ({ message }) => (
    <div className="flex items-center gap-2 p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-sm">
        <CheckCircle2 size={16} className="shrink-0" />
        {message}
    </div>
);

const ErrorBanner: React.FC<{ message: string }> = ({ message }) => (
    <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
        {message}
    </div>
);

/* ══════════════════════════════════════════════════════════════════════ */
const Settings = () => {
    const { theme, toggleTheme } = useTheme();
    const isDark = theme === 'dark';

    const [firstName, setFirstName] = useState('');
    const [lastName, setLastName] = useState('');
    const [email, setEmail] = useState('');

    useEffect(() => {
        api.get('/me/').then(res => {
            setFirstName(res.data.firstName || '');
            setLastName(res.data.lastName || '');
            setEmail(res.data.email || '');
        }).catch(() => {});
    }, []);

    /* ── change password state ── */
    const [oldPwd, setOldPwd] = useState('');
    const [newPwd, setNewPwd] = useState('');
    const [confirmPwd, setConfirmPwd] = useState('');
    const [pwdLoading, setPwdLoading] = useState(false);
    const [pwdError, setPwdError] = useState('');
    const [pwdSuccess, setPwdSuccess] = useState('');

    const handleChangePassword = async (e: React.FormEvent) => {
        e.preventDefault();
        setPwdError('');
        setPwdSuccess('');
        if (newPwd !== confirmPwd) { setPwdError('Passwords do not match.'); return; }
        if (newPwd.length < 8) { setPwdError('New password must be at least 8 characters.'); return; }
        setPwdLoading(true);
        try {
            await api.patch('/auth/change-password/', {
                old_password: oldPwd,
                new_password: newPwd,
                confirm_password: confirmPwd,
            });
            setPwdSuccess('Password changed successfully.');
            setOldPwd(''); setNewPwd(''); setConfirmPwd('');
        } catch (err: any) {
            setPwdError(err.response?.data?.error || 'Something went wrong.');
        } finally {
            setPwdLoading(false);
        }
    };

    /* ── change email state ── */
    const [newEmail, setNewEmail] = useState('');
    const [emailPwd, setEmailPwd] = useState('');
    const [emailLoading, setEmailLoading] = useState(false);
    const [emailError, setEmailError] = useState('');
    const [emailSuccess, setEmailSuccess] = useState('');

    const handleChangeEmail = async (e: React.FormEvent) => {
        e.preventDefault();
        setEmailError('');
        setEmailSuccess('');
        setPwdLoading(false);
        setEmailLoading(true);
        try {
            await api.patch('/auth/change-email/', {
                new_email: newEmail,
                password: emailPwd,
            });
            setEmailSuccess('Email changed successfully.');
            setEmail(newEmail);
            setNewEmail(''); setEmailPwd('');
        } catch (err: any) {
            setEmailError(err.response?.data?.error || 'Something went wrong.');
        } finally {
            setEmailLoading(false);
        }
    };

    const surface = { backgroundColor: 'var(--bg-surface)', borderColor: 'var(--border)' };

    return (
        <div className="p-4 sm:p-6 md:p-10 w-full animate-fadeIn">
            <div className="max-w-2xl mx-auto space-y-6">

                {/* Header */}
                <div className="mb-2">
                    <h1 className="text-3xl font-black tracking-tight" style={{ color: 'var(--text-primary)' }}>Settings</h1>
                    <p className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>
                        Manage your preferences and account credentials.
                    </p>
                </div>

                {/* ── Appearance ─────────────────────────────────── */}
                <section className="rounded-3xl border p-6 transition-colors duration-300" style={surface}>
                    <h2 className="text-[11px] font-black uppercase tracking-widest mb-5" style={{ color: 'var(--text-muted)' }}>
                        Appearance
                    </h2>
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-4">
                            <div className="w-11 h-11 rounded-2xl flex items-center justify-center"
                                style={{ backgroundColor: isDark ? '#1F2937' : '#f1f5f9' }}>
                                {isDark ? <Moon size={20} className="text-indigo-400" /> : <Sun size={20} className="text-amber-500" />}
                            </div>
                            <div>
                                <p className="font-bold" style={{ color: 'var(--text-primary)' }}>
                                    {isDark ? 'Dark mode' : 'Light mode'}
                                </p>
                                <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                                    {isDark ? 'Easy on the eyes at night' : 'Clean and bright interface'}
                                </p>
                            </div>
                        </div>
                        <button
                            onClick={toggleTheme}
                            className={`relative w-14 h-7 rounded-full transition-all duration-300 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 ${isDark ? 'bg-indigo-600' : 'bg-amber-400'}`}
                            aria-label="Toggle theme"
                        >
                            <span className={`absolute top-0.5 w-6 h-6 rounded-full bg-white shadow-md transition-transform duration-300 ${isDark ? 'translate-x-0.5' : '-translate-x-6.5'}`} />
                        </button>
                    </div>
                    <div className="mt-6 rounded-2xl p-4 flex items-center gap-3 border"
                        style={{ backgroundColor: isDark ? '#0B0E14' : '#f8fafc', borderColor: 'var(--border)' }}>
                        <div className="w-2 h-2 rounded-full bg-emerald-400" />
                        <p className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>
                            Theme applied · Saved automatically
                        </p>
                    </div>
                </section>

                {/* ── Account info ───────────────────────────────── */}
                <section className="rounded-3xl border p-6 transition-colors duration-300" style={surface}>
                    <h2 className="text-[11px] font-black uppercase tracking-widest mb-5" style={{ color: 'var(--text-muted)' }}>
                        Account
                    </h2>
                    <div className="space-y-1">
                        <SettingsRow icon={<User size={18} />} label="Full name"
                            value={firstName && lastName ? `${firstName} ${lastName}` : '—'} />
                        <SettingsRow icon={<Mail size={18} />} label="Email" value={email || '—'} />
                        <SettingsRow icon={<Shield size={18} />} label="Account type" value="Standard" />
                    </div>
                </section>

                {/* ── Security ───────────────────────────────────── */}
                <section className="rounded-3xl border p-6 transition-colors duration-300" style={surface}>
                    <h2 className="text-[11px] font-black uppercase tracking-widest mb-5" style={{ color: 'var(--text-muted)' }}>
                        Security
                    </h2>
                    <div className="space-y-3">

                        {/* Change password */}
                        <CollapsibleSection
                            icon={<Lock size={18} />}
                            title="Change Password"
                            description="Update your login password"
                        >
                            <form onSubmit={handleChangePassword} className="space-y-3 mt-3">
                                <PasswordInput
                                    placeholder="Current password"
                                    value={oldPwd}
                                    onChange={setOldPwd}
                                    autoComplete="current-password"
                                />
                                <PasswordInput
                                    placeholder="New password (min. 8 characters)"
                                    value={newPwd}
                                    onChange={setNewPwd}
                                    autoComplete="new-password"
                                />
                                <PasswordInput
                                    placeholder="Confirm new password"
                                    value={confirmPwd}
                                    onChange={setConfirmPwd}
                                    autoComplete="new-password"
                                />
                                {pwdError && <ErrorBanner message={pwdError} />}
                                {pwdSuccess && <SuccessBanner message={pwdSuccess} />}
                                <button
                                    type="submit"
                                    disabled={pwdLoading || !oldPwd || !newPwd || !confirmPwd}
                                    className="w-full py-3 rounded-xl text-sm font-bold transition-colors bg-[#00FF85] hover:bg-[#00e074] text-black disabled:opacity-40"
                                >
                                    {pwdLoading ? 'Saving…' : 'Update password'}
                                </button>
                            </form>
                        </CollapsibleSection>

                        {/* Change email */}
                        <CollapsibleSection
                            icon={<Mail size={18} />}
                            title="Change Email"
                            description="Update the email address tied to your account"
                        >
                            <form onSubmit={handleChangeEmail} className="space-y-3 mt-3">
                                <input
                                    type="email"
                                    placeholder="New email address"
                                    value={newEmail}
                                    onChange={e => setNewEmail(e.target.value)}
                                    className={inputCls}
                                    style={inputStyle}
                                    autoComplete="email"
                                />
                                <PasswordInput
                                    placeholder="Current password to confirm"
                                    value={emailPwd}
                                    onChange={setEmailPwd}
                                    autoComplete="current-password"
                                />
                                {emailError && <ErrorBanner message={emailError} />}
                                {emailSuccess && <SuccessBanner message={emailSuccess} />}
                                <button
                                    type="submit"
                                    disabled={emailLoading || !newEmail || !emailPwd}
                                    className="w-full py-3 rounded-xl text-sm font-bold transition-colors bg-[#00FF85] hover:bg-[#00e074] text-black disabled:opacity-40"
                                >
                                    {emailLoading ? 'Saving…' : 'Update email'}
                                </button>
                            </form>
                        </CollapsibleSection>

                    </div>
                </section>

            </div>
        </div>
    );
};

export default Settings;
