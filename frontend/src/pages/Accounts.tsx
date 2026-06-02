import React, { useState, useEffect, useCallback } from 'react';
import { useOutletContext, useLocation, useNavigate } from 'react-router-dom';
import { CreditCard } from 'lucide-react';
import api from '../api/axios';
import AddJuniorModal from '../components/AddJuniorModal';

interface ContextType {
    firstName: string;
    lastName: string;
}

const CopyButton: React.FC<{ value: string }> = ({ value }) => {
    const [copied, setCopied] = useState(false);

    const handleCopy = useCallback(() => {
        navigator.clipboard.writeText(value).then(() => {
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        });
    }, [value]);

    return (
        <button
            onClick={handleCopy}
            title={copied ? 'Copied!' : 'Copy'}
            className="ml-2 shrink-0 px-2 py-0.5 rounded-lg text-[10px] font-bold transition-all"
            style={copied
                ? { backgroundColor: '#00FF85', color: '#000' }
                : { backgroundColor: 'var(--bg-elevated)', color: 'var(--text-muted)', border: '1px solid var(--border)' }
            }
        >
            {copied ? 'Copied!' : 'Copy'}
        </button>
    );
};

const Accounts = () => {
    const context = useOutletContext<ContextType>();
    const firstName = context?.firstName || '';
    const lastName = context?.lastName || '';

    const location = useLocation();
    const navigate = useNavigate();

    const [accounts, setAccounts] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [selectedAccount, setSelectedAccount] = useState<any>(null);
    const [isAddJuniorOpen, setIsAddJuniorOpen] = useState(false);

    const refreshData = async () => {
        try {
            const res = await api.get('/accounts/');
            const fetched = res.data;
            setAccounts(fetched);
            if (selectedAccount) {
                const updated = fetched.find((a: any) => a.id === selectedAccount.id);
                if (updated) setSelectedAccount(updated);
            }
        } catch (err) {
            console.error('Refresh error:', err);
        }
    };

    useEffect(() => {
        const init = async () => {
            try {
                const res = await api.get('/accounts/');
                if (res.data.length > 0) setAccounts(res.data);
            } catch (err) {
                console.error('Load error:', err);
            } finally {
                setLoading(false);
            }
        };
        init();
    }, []);

    useEffect(() => {
        if (accounts.length > 0) {
            if (location.state?.selectedAccountId) {
                const pre = accounts.find(a => a.id === location.state.selectedAccountId);
                setSelectedAccount(pre || accounts[0]);
            } else if (!selectedAccount) {
                setSelectedAccount(accounts[0]);
            }
        }
    }, [accounts, location.state]);

    const formatCurrency = (amount: string, currency: string = 'GBP') =>
        new Intl.NumberFormat('en-GB', { style: 'currency', currency }).format(parseFloat(amount));

    if (loading) {
        return (
            <div className="flex-1 h-full flex items-center justify-center">
                <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-[#00FF85]" />
            </div>
        );
    }

    return (
        <>
            <div className="flex-1 p-4 sm:p-5 md:p-6 text-[var(--text-primary)] flex flex-col lg:flex-row gap-5 md:gap-6 w-full">

                {/* LEFT COLUMN: account list */}
                <div className="flex w-full lg:w-64 shrink-0 flex-col gap-2">
                    <h2 className="text-[10px] font-bold text-[var(--text-muted)] uppercase tracking-widest mb-1.5 px-1">My Accounts</h2>
                    <div className="flex flex-row lg:flex-col gap-2.5 overflow-x-auto no-scrollbar pb-2 lg:pb-0">
                        {accounts.map((acc) => {
                            const isJunior = acc.account_type === 'JUNIOR';
                            const isSelected = selectedAccount?.id === acc.id;
                            return (
                                <button
                                    key={acc.id}
                                    onClick={() => setSelectedAccount(acc)}
                                    className={`flex items-center gap-3 shrink-0 lg:shrink w-[220px] lg:w-full p-2.5 rounded-xl transition-all border
                                    ${isSelected
                                        ? (isJunior ? 'bg-purple-500/10 border-purple-500/50' : 'bg-emerald-500/10 border-emerald-500/30')
                                        : 'bg-[var(--bg-surface)] lg:bg-transparent hover:bg-[var(--bg-elevated)] border-[var(--border)] lg:border-transparent'}`}
                                >
                                    <div className={`w-8 h-8 shrink-0 rounded-lg flex items-center justify-center ${isSelected ? (isJunior ? 'bg-purple-500 text-white' : 'bg-[#00FF85] text-black') : 'bg-[var(--bg-elevated)] text-[var(--text-muted)]'}`}>
                                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            {isJunior
                                                ? <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                                                : <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />}
                                        </svg>
                                    </div>
                                    <div className="text-left flex-1 overflow-hidden flex items-center justify-between gap-2">
                                        <span className="text-sm font-bold truncate">
                                            {isJunior ? acc.owner_first_name : firstName}
                                        </span>
                                        <span className={`text-[8px] font-black uppercase px-1.5 py-0.5 rounded shrink-0 border ${
                                            isJunior
                                                ? 'bg-purple-500/20 text-purple-400 border-purple-500/30'
                                                : 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                                        }`}>
                                            {isJunior ? 'Junior' : 'Current'}
                                        </span>
                                    </div>
                                </button>
                            );
                        })}

                        {/* Add Junior */}
                        <button
                            onClick={() => setIsAddJuniorOpen(true)}
                            className="flex items-center gap-3 shrink-0 lg:shrink w-[220px] lg:w-full p-2.5 rounded-xl transition-all border border-dashed hover:border-[#00FF85]/50 hover:bg-[#00FF85]/5 group"
                            style={{ borderColor: 'var(--border)', color: 'var(--text-muted)' }}
                        >
                            <div className="w-8 h-8 shrink-0 rounded-lg flex items-center justify-center group-hover:bg-[#00FF85]/20 transition-colors" style={{ backgroundColor: 'var(--bg-elevated)' }}>
                                <svg className="w-4 h-4 group-hover:text-[#00FF85] transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                                </svg>
                            </div>
                            <span className="text-sm font-semibold group-hover:text-[#00FF85] transition-colors">Add Junior Account</span>
                        </button>
                    </div>
                </div>

                {/* RIGHT: account details */}
                <div className="flex-1 flex flex-col h-full pr-2 pb-6 w-full">
                    {selectedAccount ? (
                        <div className="flex flex-col gap-4 animate-fadeIn max-w-2xl w-full">

                            {/* Balance header */}
                            <div className="bg-[var(--bg-surface)] border border-[var(--border)] rounded-3xl p-5 sm:p-6 shadow-lg">
                                <h2 className="text-[10px] sm:text-xs font-bold text-[var(--text-muted)] uppercase tracking-widest mb-1.5">
                                    {selectedAccount.account_type === 'JUNIOR'
                                        ? `${selectedAccount.owner_first_name}'s Account`
                                        : `${firstName}'s Account`}
                                </h2>
                                <h1 className="text-4xl sm:text-5xl font-black tracking-tighter text-[var(--text-primary)]">
                                    {formatCurrency(selectedAccount.available_balance, selectedAccount.currency)}
                                </h1>
                            </div>

                            {/* Account details card */}
                            <div className="bg-[var(--bg-surface)] border border-[var(--border)] rounded-3xl p-4 sm:p-5 shadow-lg">
                                <h3 className="text-[10px] font-bold text-[var(--text-muted)] uppercase tracking-widest mb-4">Account Details</h3>
                                <div className="space-y-2.5">
                                    <div className="flex justify-between items-center gap-4 border-b border-[var(--border)]/50 pb-2.5">
                                        <span className="text-[var(--text-muted)] font-bold text-[9px] sm:text-[10px] uppercase tracking-widest whitespace-nowrap">Account Holder</span>
                                        <span className="font-bold text-[var(--text-secondary)] text-xs sm:text-sm text-right truncate">
                                            {selectedAccount.account_type === 'JUNIOR'
                                                ? `${selectedAccount.owner_first_name} ${selectedAccount.owner_last_name}`
                                                : `${firstName} ${lastName}`}
                                        </span>
                                    </div>
                                    <div className="flex justify-between items-center gap-4 border-b border-[var(--border)]/50 pb-2.5">
                                        <span className="text-[var(--text-muted)] font-bold text-[9px] sm:text-[10px] uppercase tracking-widest whitespace-nowrap">Sort Code</span>
                                        <span className="font-mono text-[var(--text-secondary)] text-xs sm:text-sm">
                                            {selectedAccount.sort_code?.match(/.{1,2}/g)?.join('-') || 'N/A'}
                                        </span>
                                    </div>
                                    <div className="flex justify-between items-center gap-4 border-b border-[var(--border)]/50 pb-2.5">
                                        <span className="text-[var(--text-muted)] font-bold text-[9px] sm:text-[10px] uppercase tracking-widest whitespace-nowrap">Account Number</span>
                                        <div className="flex items-center">
                                            <span className="font-mono text-[var(--text-secondary)] text-xs sm:text-sm">{selectedAccount.account_number || 'N/A'}</span>
                                            {selectedAccount.account_number && <CopyButton value={selectedAccount.account_number} />}
                                        </div>
                                    </div>
                                    <div className="flex flex-col sm:flex-row justify-between sm:items-center gap-1 sm:gap-4 pt-0.5">
                                        <span className="text-[var(--text-muted)] font-bold text-[9px] sm:text-[10px] uppercase tracking-widest whitespace-nowrap">IBAN</span>
                                        <div className="flex items-center">
                                            <span className="font-mono text-[9px] sm:text-[10px] text-[var(--text-muted)] break-all">
                                                {selectedAccount.iban?.match(/.{1,4}/g)?.join(' ') || 'N/A'}
                                            </span>
                                            {selectedAccount.iban && <CopyButton value={selectedAccount.iban} />}
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {/* Manage cards shortcut */}
                            <button
                                onClick={() => navigate('/cards')}
                                className="flex items-center justify-between gap-4 p-4 sm:p-5 rounded-3xl transition-all group"
                                style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border)' }}
                            >
                                <div className="flex items-center gap-3">
                                    <div className="w-10 h-10 rounded-2xl flex items-center justify-center bg-emerald-500/10 text-emerald-400 group-hover:bg-emerald-500/20 transition-colors">
                                        <CreditCard size={20} />
                                    </div>
                                    <div className="text-left">
                                        <p className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>Manage Cards</p>
                                        <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                                            {selectedAccount.cards?.length || 0} card{selectedAccount.cards?.length !== 1 ? 's' : ''} · Virtual, Physical, Prepaid
                                        </p>
                                    </div>
                                </div>
                                <svg className="w-5 h-5 group-hover:translate-x-1 transition-transform" style={{ color: 'var(--text-muted)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                                </svg>
                            </button>

                        </div>
                    ) : (
                        <div className="text-center p-20" style={{ color: 'var(--text-muted)' }}>No account selected.</div>
                    )}
                </div>
            </div>

            <AddJuniorModal
                isOpen={isAddJuniorOpen}
                onClose={() => setIsAddJuniorOpen(false)}
                onSuccess={() => { setIsAddJuniorOpen(false); refreshData(); }}
            />
        </>
    );
};

export default Accounts;
