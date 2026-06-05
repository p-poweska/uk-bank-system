import React, { useState, useEffect } from 'react';
import { X, Plus, ChevronDown, Home, User, Loader2, CheckCircle2 } from 'lucide-react';
import api from '../api/axios';

interface Account {
    id: string;
    account_type: string;
    balance: string;
    currency: string;
    available_balance: string;
}

interface AddMoneyModalProps {
    isOpen: boolean;
    onClose: () => void;
    accounts: Account[];
    onSuccess: () => void;
}

const AddMoneyModal: React.FC<AddMoneyModalProps> = ({ isOpen, onClose, accounts, onSuccess }) => {
    const [selectedAccountId, setSelectedAccountId] = useState('');
    const [amount, setAmount] = useState<string>('');
    const [loading, setLoading] = useState(false);
    const [isSuccess, setIsSuccess] = useState(false);
    const [isDropdownOpen, setIsDropdownOpen] = useState(false);

    useEffect(() => {
        if (accounts.length > 0 && !selectedAccountId) {
            setSelectedAccountId(accounts[0].id);
        }
    }, [accounts, selectedAccountId]);

    const hideSpinnersCSS = `
        input::-webkit-outer-spin-button,
        input::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; }
        input[type=number] { -moz-appearance: textfield; }
    `;

    if (!isOpen) return null;

    const handleQuickAdd = (val: number) => {
        const current = parseFloat(amount) || 0;
        setAmount((current + val).toFixed(2));
    };

    const handleConfirm = async () => {
        if (!amount || parseFloat(amount) <= 0) return;
        setLoading(true);
        try {
            await api.post('/accounts/deposit/', {
                account_id: selectedAccountId,
                amount: parseFloat(amount)
            });
            setIsSuccess(true);
            setTimeout(() => {
                onSuccess();
                setIsSuccess(false);
                setAmount('');
                onClose();
            }, 2000);
        } catch (error) {
            console.error("Deposit failed", error);
            alert("Deposit failed. Please try again.");
        } finally {
            setLoading(false);
        }
    };

    const selectedAccount = accounts.find(a => a.id === selectedAccountId);

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
            <style>{hideSpinnersCSS}</style>

            <div className="bg-[var(--bg-surface)] border border-[var(--border)] w-full max-w-md rounded-[2.5rem] p-8 shadow-2xl relative overflow-hidden">

                {isSuccess && (
                    <div className="absolute inset-0 bg-[var(--bg-surface)] z-50 flex flex-col items-center justify-center animate-in fade-in duration-300">
                        <CheckCircle2 size={64} className="text-[#00FF85] mb-4 animate-bounce" />
                        <h3 className="text-xl font-bold text-[var(--text-primary)]">Deposit Successful!</h3>
                    </div>
                )}

                <div className="flex justify-between items-center mb-8">
                    <div>
                        <h2 className="text-xl font-bold text-[var(--text-primary)] tracking-tight">Add Money</h2>
                        <p className="text-gray-500 text-xs mt-0.5">Deposit funds into your account</p>
                    </div>
                    <button
                        onClick={onClose}
                        className="w-10 h-10 flex items-center justify-center rounded-xl bg-red-500/10 text-red-500 hover:bg-red-500 hover:text-white transition-all duration-300 shadow-sm"
                    >
                        <X size={20} />
                    </button>
                </div>

                <div className="mb-6 relative">
                    <label className="text-[10px] font-bold text-[var(--text-muted)] uppercase tracking-widest mb-3 block ml-1">Deposit To</label>

                    {isDropdownOpen && (
                        <div className="fixed inset-0 z-10" onClick={() => setIsDropdownOpen(false)} />
                    )}

                    <div className="relative z-20">
                        <div
                            onClick={() => setIsDropdownOpen(!isDropdownOpen)}
                            className={`w-full bg-[var(--bg-base)] border ${isDropdownOpen ? (selectedAccount?.account_type === 'JUNIOR' ? 'border-purple-500/50' : 'border-[#00FF85]/50') : 'border-[var(--border)]'} rounded-2xl p-4 pl-14 pr-4 text-white font-medium transition-all cursor-pointer flex items-center justify-between group`}
                        >
                            <div className={`absolute left-4 top-1/2 -translate-y-1/2 w-8 h-8 rounded-lg flex items-center justify-center pointer-events-none transition-colors duration-300 ${selectedAccount?.account_type === 'JUNIOR' ? 'bg-purple-500/10 text-purple-400' : 'bg-emerald-500/10 text-emerald-400'}`}>
                                {selectedAccount?.account_type === 'JUNIOR' ? <User size={16} /> : <Home size={16} />}
                            </div>

                            <span className="select-none">
                                {selectedAccount ? (selectedAccount.account_type === 'CURRENT' ? 'Current Account' : 'Junior Account') : 'Select Account'}
                            </span>

                            <ChevronDown size={18} className={`text-gray-500 transition-transform duration-300 ${isDropdownOpen ? `rotate-180 ${selectedAccount?.account_type === 'JUNIOR' ? 'text-purple-400' : 'text-[#00FF85]'}` : 'group-hover:text-white'}`} />
                        </div>

                        {isDropdownOpen && (
                            <div className="absolute top-full left-0 right-0 mt-2 bg-[var(--bg-base)] border border-[var(--border)] rounded-2xl overflow-hidden shadow-[0_15px_40px_-10px_rgba(0,0,0,0.5)] z-30 animate-in fade-in slide-in-from-top-2 duration-200">
                                {accounts.map(acc => {
                                    const isSelected = selectedAccountId === acc.id;
                                    return (
                                        <div
                                            key={acc.id}
                                            onClick={() => {
                                                setSelectedAccountId(acc.id);
                                                setIsDropdownOpen(false);
                                            }}
                                            className={`p-4 pl-14 cursor-pointer transition-colors relative flex items-center ${isSelected
                                                ? (acc.account_type === 'JUNIOR' ? 'bg-purple-500/10 text-purple-400' : 'bg-emerald-500/10 text-[#00FF85]')
                                                : 'text-gray-400 hover:bg-[var(--bg-surface)] hover:text-white'
                                                }`}
                                        >
                                            <span className="font-medium">
                                                {acc.account_type === 'CURRENT' ? 'Current Account' : 'Junior Account'}
                                            </span>
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </div>

                    {selectedAccount && (
                        <p className="text-xs text-gray-400 mt-3 ml-2">
                            Current Balance:  <span className="text-sm font-bold text-white tracking-wide">£{parseFloat(selectedAccount.available_balance).toFixed(2)}</span>
                        </p>
                    )}
                </div>

                <div className="mb-8">
                    <label className="text-[10px] font-bold text-[var(--text-muted)] uppercase tracking-widest mb-3 block ml-1">Amount</label>
                    <div className="relative group">
                        <span className="absolute left-6 top-1/2 -translate-y-1/2 text-4xl font-bold text-[#00FF85]">£</span>
                        <input
                            type="number"
                            value={amount}
                            onChange={(e) => setAmount(e.target.value)}
                            className="w-full bg-[var(--bg-base)] border border-[var(--border)] rounded-2xl p-6 pl-14 text-4xl font-bold text-[var(--text-primary)] focus:outline-none focus:border-[#00FF85]/50 transition-all placeholder:text-[var(--text-muted)]/50"
                            placeholder="0.00"
                        />
                    </div>
                </div>

                <div className="mb-8">
                    <label className="text-[10px] font-bold text-[var(--text-muted)] uppercase tracking-widest mb-3 block ml-1">Quick Add</label>
                    <div className="grid grid-cols-3 gap-3">
                        {[10, 50, 100].map(val => (
                            <button
                                key={val}
                                onClick={() => handleQuickAdd(val)}
                                className="bg-[var(--bg-elevated)] hover:bg-[#2a343f] text-white py-3 rounded-xl font-bold text-sm transition-all active:scale-95 border border-[var(--border)]"
                            >
                                +£{val}
                            </button>
                        ))}
                    </div>
                </div>

                <button
                    onClick={handleConfirm}
                    disabled={loading || !amount || parseFloat(amount) <= 0}
                    className={`
                        w-full py-5 rounded-2xl font-black text-base transition-all duration-300 flex items-center justify-center active:scale-[0.98]
                        ${(loading || !amount || parseFloat(amount) <= 0)
                            ? 'bg-gray-800 text-gray-500 cursor-not-allowed shadow-none'
                            : 'bg-[#00FF85] text-black shadow-[0_0_20px_rgba(0,255,133,0.2)] hover:shadow-[0_0_30px_rgba(0,255,133,0.4)] hover:bg-[#00e074]'}
                    `}
                >
                    {loading ? <Loader2 className="animate-spin" /> : 'Confirm Deposit'}
                </button>
            </div>
        </div>
    );
};

export default AddMoneyModal;