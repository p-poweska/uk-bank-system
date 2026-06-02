import React, { useEffect, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { Wallet, CreditCard, ArrowUpRight, Sparkles, PiggyBank } from 'lucide-react';
import api from '../api/axios';

interface ContextType {
    firstName: string;
    lastName: string;
}

const JuniorDashboard = () => {
    const { firstName } = useOutletContext<ContextType>();
    const [account, setAccount] = useState<any>(null);
    const [card, setCard] = useState<any>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const load = async () => {
            try {
                const res = await api.get('/accounts/');
                const acc = res.data[0];
                setAccount(acc);
                if (acc?.cards?.length > 0) setCard(acc.cards[0]);
            } catch {}
            finally { setLoading(false); }
        };
        load();
    }, []);

    const fmt = (amount: number) =>
        new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP' }).format(amount);

    if (loading) {
        return (
            <div className="flex items-center justify-center py-32">
                <div className="w-12 h-12 border-4 border-purple-300 border-t-purple-600 rounded-full animate-spin" />
            </div>
        );
    }

    return (
        <div className="space-y-6 animate-fadeIn">
            {/* Greeting */}
            <div className="text-center py-4">
                <div className="text-5xl mb-3">👋</div>
                <h1 className="text-3xl font-black text-purple-800 tracking-tight">
                    Hey, {firstName}!
                </h1>
                <p className="text-purple-500 mt-1 font-medium">Here's your money</p>
            </div>

            {/* Balance card */}
            <div className="bg-gradient-to-br from-purple-500 to-pink-500 rounded-[2rem] p-7 text-white shadow-xl shadow-purple-200 relative overflow-hidden">
                <div className="absolute -top-8 -right-8 w-32 h-32 bg-white/10 rounded-full" />
                <div className="absolute -bottom-6 -left-6 w-24 h-24 bg-white/10 rounded-full" />

                <div className="relative z-10">
                    <div className="flex items-center gap-2 mb-4">
                        <Wallet size={18} className="opacity-80" />
                        <span className="text-sm font-bold opacity-80 uppercase tracking-widest">My Balance</span>
                    </div>
                    <div className="text-5xl font-black tracking-tight mb-1">
                        {account ? fmt(parseFloat(account.available_balance)) : '£0.00'}
                    </div>
                    <p className="text-white/60 text-sm font-mono mt-3">
                        {account?.iban?.replace(/(.{4})/g, '$1 ').trim() || '—'}
                    </p>
                </div>
            </div>

            {/* Prepaid card balance */}
            {card && (
                <div className="bg-white rounded-[1.5rem] border-2 border-purple-100 p-6 shadow-sm">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <div className="w-11 h-11 bg-gradient-to-br from-pink-400 to-purple-500 rounded-2xl flex items-center justify-center shadow">
                                <CreditCard size={20} className="text-white" />
                            </div>
                            <div>
                                <p className="text-xs font-bold text-gray-400 uppercase tracking-widest">Prepaid Card</p>
                                <p className="text-lg font-black text-gray-800">
                                    {fmt(parseFloat(card.prepaid_balance ?? '0'))}
                                </p>
                            </div>
                        </div>
                        <div className="text-right">
                            <p className="text-[11px] text-gray-400 font-mono">{card.masked_number}</p>
                            <span className="mt-1 inline-block px-2 py-0.5 rounded-md text-[10px] font-black bg-purple-100 text-purple-600 uppercase">
                                {card.status}
                            </span>
                        </div>
                    </div>
                </div>
            )}

            {/* Info tiles */}
            <div className="grid grid-cols-2 gap-4">
                <div className="bg-white rounded-[1.5rem] border-2 border-blue-100 p-5 shadow-sm flex flex-col gap-3">
                    <div className="w-10 h-10 bg-blue-100 rounded-xl flex items-center justify-center">
                        <PiggyBank size={20} className="text-blue-500" />
                    </div>
                    <div>
                        <p className="text-[11px] font-bold text-gray-400 uppercase tracking-widest">Saved</p>
                        <p className="text-xl font-black text-gray-800">{account ? fmt(parseFloat(account.available_balance)) : '£0.00'}</p>
                    </div>
                </div>

                <div className="bg-white rounded-[1.5rem] border-2 border-emerald-100 p-5 shadow-sm flex flex-col gap-3">
                    <div className="w-10 h-10 bg-emerald-100 rounded-xl flex items-center justify-center">
                        <Sparkles size={20} className="text-emerald-500" />
                    </div>
                    <div>
                        <p className="text-[11px] font-bold text-gray-400 uppercase tracking-widest">Account</p>
                        <p className="text-xl font-black text-gray-800">Junior</p>
                    </div>
                </div>
            </div>

            {/* No transfers outside bank info */}
            <div className="bg-amber-50 border-2 border-amber-200 rounded-[1.5rem] p-5 flex gap-4 items-start">
                <div className="text-2xl">ℹ️</div>
                <div>
                    <p className="font-bold text-amber-800 text-sm">Transfers need parent approval</p>
                    <p className="text-amber-700 text-xs mt-1 leading-relaxed">
                        Any money you send needs to be approved by your parent first. Ask them to check their account!
                    </p>
                </div>
            </div>

            {/* Recent transactions placeholder */}
            <div className="bg-white rounded-[1.5rem] border-2 border-gray-100 p-6 shadow-sm">
                <div className="flex items-center gap-2 mb-4">
                    <ArrowUpRight size={18} className="text-purple-500" />
                    <h2 className="font-black text-gray-800">Recent Activity</h2>
                </div>
                <div className="text-center py-6 text-gray-400">
                    <div className="text-4xl mb-2">🎉</div>
                    <p className="text-sm font-medium">No transactions yet.<br />Your account is ready to use!</p>
                </div>
            </div>
        </div>
    );
};

export default JuniorDashboard;
