import React, { useState, useEffect } from 'react';
import { X, Send, CheckCircle2, Globe, Zap, Clock } from 'lucide-react';
import api from '../api/axios';

interface TransferModalProps {
    isOpen: boolean;
    onClose: () => void;
    accounts: any[];
    onSuccess: () => void;
    prefilled?: { recipientName: string; recipientAccount: string; routingMethod: string } | null;
    disableAccountTypeFilter?: boolean;
    juniorTheme?: boolean;
}

/* ── theme tokens ────────────────────────────────────────────────────── */
const dark = {
    overlay: 'bg-black/60',
    modal: 'bg-[var(--bg-surface)] border-[var(--border)]',
    header: 'bg-[var(--bg-elevated)] border-[var(--border)]',
    headerTitle: 'text-[var(--text-primary)]',
    closeBtn: 'text-gray-500 hover:text-white',
    tabBar: 'bg-[var(--bg-base)] border-[var(--border)]',
    tabActive: 'bg-[var(--bg-surface)] text-[#00FF85] shadow-lg',
    tabInactive: 'text-gray-500 hover:text-gray-300',
    accentIcon: 'text-[#00FF85]',
    label: 'text-[var(--text-muted)]',
    input: 'bg-[var(--bg-base)] border-[var(--border)] text-[var(--text-primary)] focus:border-[#00FF85]',
    inputMono: 'bg-[var(--bg-base)] border-[var(--border)] text-[var(--text-primary)] font-mono',
    inputIntl: 'bg-[var(--bg-base)] border-blue-500/50 focus:border-blue-500 text-[var(--text-primary)] font-mono',
    inputSwift: 'bg-[var(--bg-base)] border-blue-500/50 focus:border-blue-500 text-[var(--text-primary)] font-mono uppercase',
    prefixSymbol: 'text-[var(--text-muted)]',
    errorBox: 'bg-red-500/10 border-red-500/20 text-red-400',
    successIcon: 'bg-[#00FF85]/10 border-[#00FF85]/20',
    successCheck: 'text-[#00FF85]',
    successTitle: 'text-[var(--text-primary)]',
    successSub: 'text-gray-500',
    submitBtn: 'bg-[#00FF85] hover:bg-[#00e074] text-black shadow-[0_8px_20px_rgba(0,255,133,0.15)] disabled:hover:bg-[#00FF85]',
    loadMore: '',
};

const currencyFromBic = (bic: string) => {
    const country = bic.trim().toUpperCase().slice(4, 6);
    if (country === 'US') return 'USD';
    if (country === 'PL') return 'PLN';
    if (country === 'DE' || country === 'FR') return 'EUR';
    if (country === 'GB') return 'GBP';
    return 'USD';
};

const swiftFeeLabel = (chargeBearer: string) => {
    if (chargeBearer === 'OUR') return 'Sender pays known transfer costs';
    if (chargeBearer === 'BEN') return 'Receiver pays costs';
    return 'Costs are shared';
};

const swiftRateFromGbp = (currency: string) => {
    if (currency === 'USD') return 1.25;
    if (currency === 'EUR') return 1.15;
    if (currency === 'PLN') return 5.00;
    return 1;
};

const swiftFeeGbp = (chargeBearer: string) => {
    if (chargeBearer === 'OUR') return 15;
    if (chargeBearer === 'BEN') return 0;
    return 5;
};

const junior = {
    overlay: 'bg-purple-900/40',
    modal: 'bg-white border-purple-200',
    header: 'bg-gradient-to-r from-purple-500 to-pink-500 border-transparent',
    headerTitle: 'text-white',
    closeBtn: 'text-white/70 hover:text-white',
    tabBar: 'bg-purple-50 border-purple-200',
    tabActive: 'bg-white text-purple-600 shadow-md',
    tabInactive: 'text-purple-300 hover:text-purple-500',
    accentIcon: 'text-white',
    label: 'text-purple-400',
    input: 'bg-purple-50 border-purple-200 text-gray-800 focus:border-purple-400',
    inputMono: 'bg-purple-50 border-purple-200 text-gray-800 font-mono focus:border-purple-400',
    inputIntl: 'bg-purple-50 border-blue-300 focus:border-blue-500 text-gray-800 font-mono',
    inputSwift: 'bg-purple-50 border-blue-300 focus:border-blue-500 text-gray-800 font-mono uppercase',
    prefixSymbol: 'text-purple-400',
    errorBox: 'bg-red-50 border-red-200 text-red-500',
    successIcon: 'bg-purple-100 border-purple-200',
    successCheck: 'text-purple-500',
    successTitle: 'text-gray-800',
    successSub: 'text-gray-400',
    submitBtn: 'bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white shadow-[0_8px_20px_rgba(168,85,247,0.3)] disabled:hover:from-purple-500 disabled:hover:to-pink-500',
    loadMore: '',
};

const TransferModal: React.FC<TransferModalProps> = ({
    isOpen,
    onClose,
    accounts,
    onSuccess,
    prefilled,
    disableAccountTypeFilter = false,
    juniorTheme = false,
}) => {
    const t = juniorTheme ? junior : dark;

    const [activeTab, setActiveTab] = useState<'EXTERNAL' | 'OWN'>('EXTERNAL');
    const [loading, setLoading] = useState(false);
    const [success, setSuccess] = useState(false);
    const [pendingApproval, setPendingApproval] = useState(false);
    const [error, setError] = useState('');

    const [fromAccountId, setFromAccountId] = useState('');
    const [amount, setAmount] = useState('');
    const [recipientName, setRecipientName] = useState('');
    const [recipientAccount, setRecipientAccount] = useState('');
    const [swiftCode, setSwiftCode] = useState('');
    const [title, setTitle] = useState('');
    const [routingMethod, setRoutingMethod] = useState('FPS');
    const [transferCurrency, setTransferCurrency] = useState('USD');
    const [chargeBearer, setChargeBearer] = useState<'OUR' | 'SHA' | 'BEN'>('SHA');
    const [toAccountId, setToAccountId] = useState('');

    const formatBalance = (val: string) =>
        parseFloat(val).toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

    const availableFromAccounts = (activeTab === 'EXTERNAL' && !disableAccountTypeFilter)
        ? accounts.filter(acc => acc.account_type === 'CURRENT')
        : accounts;

    const cleanIban = recipientAccount.replace(/\s+/g, '').toUpperCase();
    const isInternational = cleanIban.length >= 2 && !cleanIban.startsWith('GB');
    // A GB IBAN that is not one of our own (LYOB) accounts is a transfer to
    // another UK bank — it routes out via FPS/CHAPS/BACS and needs the
    // recipient bank's BIC, just like an international SWIFT payment does.
    const isLyoIban = cleanIban.startsWith('GB') && cleanIban.substring(4, 8) === 'LYOB';
    const isExternalUk = cleanIban.startsWith('GB') && !isLyoIban && cleanIban.length >= 8;
    const needsBic = isInternational || isExternalUk;
    const isSwiftTransfer = routingMethod === 'SWIFT' || isInternational;

    const parsedAmountForPreview = parseFloat(amount);
    const swiftPreview = isSwiftTransfer && !isNaN(parsedAmountForPreview) && parsedAmountForPreview > 0
        ? (() => {
            const rate = swiftRateFromGbp(transferCurrency);
            const converted = parsedAmountForPreview / rate;
            const fee = swiftFeeGbp(chargeBearer);
            const total = converted + fee;

            return {
                rate,
                converted,
                fee,
                total,
            };
        })()
        : null;

    // The accounts list includes a parent's own accounts AND their juniors'
    // accounts (the API returns both). A junior (child) user only ever has
    // junior account(s), whereas a parent always keeps their own CURRENT
    // account — so "every" correctly detects a junior, while "some" wrongly hid
    // the Own-transfer tab from any parent who created a junior account.
    const isJuniorUser = accounts.length > 0 && accounts.every(acc => acc.account_type === 'JUNIOR');
    const availableTabs = isJuniorUser ? ['EXTERNAL'] as const : ['EXTERNAL', 'OWN'] as const;

    useEffect(() => {
        if (isInternational) {
            setRoutingMethod('SWIFT');

            if (swiftCode.trim().length >= 6) {
                setTransferCurrency(currencyFromBic(swiftCode));
            } else {
                const country = cleanIban.slice(0, 2);
                if (country === 'US') setTransferCurrency('USD');
                else if (country === 'PL') setTransferCurrency('PLN');
                else if (country === 'DE' || country === 'FR') setTransferCurrency('EUR');
                else setTransferCurrency('USD');
            }
        } else if (routingMethod === 'SWIFT') {
            setRoutingMethod('FPS');
        }
    }, [isInternational, swiftCode, cleanIban]);

    useEffect(() => {
        if (isOpen) {
            setSuccess(false);
            setPendingApproval(false);
            setError('');
            setAmount('');
            setSwiftCode('');
            setTransferCurrency('USD');
            setChargeBearer('SHA');
            setTitle('');
            if (prefilled) {
                if (isJuniorUser) {
                    setActiveTab('EXTERNAL');
                }
                setRecipientName(prefilled.recipientName);
                setRecipientAccount(prefilled.recipientAccount);
                setRoutingMethod(prefilled.routingMethod);
            } else {
                setRecipientName('');
                setRecipientAccount('');
                setRoutingMethod('FPS');
            }
            if (availableFromAccounts.length > 0) {
                setFromAccountId(availableFromAccounts[0].id);
            } else {
                setFromAccountId('');
            }
        }
    }, [isOpen, activeTab, accounts]);

    if (!isOpen) return null;

    const handleTransfer = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        if (!fromAccountId) return;

        const parsedAmount = parseFloat(amount);
        if (isNaN(parsedAmount) || parsedAmount <= 0) {
            setError('Amount must be greater than zero.');
            return;
        }
        const sourceAccount = availableFromAccounts.find(acc => acc.id === fromAccountId);
        if (sourceAccount && !isSwiftTransfer && parsedAmount > parseFloat(sourceAccount.available_balance)) {
            setError("Insufficient funds. You don't have enough money.");
            return;
        }
        if (activeTab === 'EXTERNAL') {
            if (recipientName.trim().length < 2) {
                setError('Recipient name must be at least 2 characters long.');
                return;
            }
            const ibanRegex = /^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$/;
            if (!ibanRegex.test(cleanIban)) {
                setError('Invalid IBAN format. Check country code and check digits.');
                return;
            }
        }
        if (needsBic && swiftCode.trim().length < 8) {
            setError('Recipient BIC/SWIFT code is required.');
            return;
        }

        if (isSwiftTransfer && !transferCurrency) {
            setError('Transfer currency is required for SWIFT.');
            return;
        }
        if (activeTab === 'OWN' && !toAccountId) {
            setError('Please select a target account.');
            return;
        }

        setLoading(true);
        try {
            const endpoint = activeTab === 'OWN' ? 'transfers/own/' : 'transfers/national/';
            const payload = activeTab === 'OWN'
                ? { from_account: fromAccountId, to_account: toAccountId, amount: parsedAmount }
                : {
                    from_account: fromAccountId,
                    recipient_name: recipientName,
                    recipient_account: cleanIban,
                    routing_method: routingMethod,
                    swift_bic: needsBic ? swiftCode.trim() : null,
                    transfer_currency: isSwiftTransfer ? transferCurrency : null,
                    charge_bearer: isSwiftTransfer ? chargeBearer : null,
                    amount: parsedAmount,
                    title,
                };
            const res = await api.post(endpoint, payload);
            if (res.data?.status === 'pending_approval') {
                setPendingApproval(true);
                setTimeout(() => { onSuccess(); onClose(); }, 3000);
            } else {
                setSuccess(true);
                setTimeout(() => { onSuccess(); onClose(); }, 2000);
            }
        } catch (err: any) {
            setError(err.response?.data?.error || 'Transfer failed. Please check your details and try again.');
        } finally {
            setLoading(false);
        }
    };

    /* ── shared input class helper ── */
    const inputCls = (extra = '') =>
        `w-full border rounded-xl px-4 py-3 outline-none transition-colors ${t.input} ${extra}`;

    const labelCls = `text-[10px] font-bold uppercase tracking-widest mb-1.5 block px-1 ${t.label}`;

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
            <div className={`absolute inset-0 ${t.overlay} backdrop-blur-sm`} onClick={onClose} />

            <div className={`relative ${t.modal} border w-full max-w-lg rounded-3xl shadow-2xl overflow-hidden animate-fadeIn flex flex-col max-h-[90vh]`}>

                {/* Header */}
                <div className={`p-6 border-b ${t.header} flex justify-between items-center shrink-0`}>
                    <h2 className={`text-xl font-bold flex items-center gap-3 ${t.headerTitle}`}>
                        <Send className={t.accentIcon} size={22} />
                        New Transfer
                    </h2>
                    <button onClick={onClose} className={`transition-colors ${t.closeBtn}`}>
                        <X size={22} />
                    </button>
                </div>

                {/* Tabs */}
                <div className={`flex p-1.5 ${t.tabBar} mx-6 mt-6 rounded-2xl border shrink-0`}>
                    {availableTabs.map(tab => (
                        <button
                            key={tab}
                            onClick={() => { setActiveTab(tab); setError(''); }}
                            className={`flex-1 py-2.5 rounded-xl text-xs font-bold uppercase tracking-wider transition-all ${activeTab === tab ? t.tabActive : t.tabInactive}`}
                        >
                            {tab === 'EXTERNAL' ? 'External Transfer' : 'Own Transfer'}
                        </button>
                    ))}
                </div>

                {/* Error */}
                {error && (
                    <div className={`mx-6 mt-4 p-3 rounded-xl border text-xs text-center ${t.errorBox}`}>
                        {error}
                    </div>
                )}

                {/* Pending approval screen */}
                {pendingApproval ? (
                    <div className="p-12 flex flex-col items-center justify-center text-center space-y-4 flex-1">
                        <div className="w-20 h-20 rounded-full flex items-center justify-center border bg-amber-50 border-amber-200">
                            <Clock size={40} className="text-amber-500" />
                        </div>
                        <h3 className={`text-2xl font-bold ${t.successTitle}`}>Awaiting Approval</h3>
                        <p className={`font-medium ${t.successSub}`}>
                            Your transfer has been sent to your parent for approval.
                        </p>
                    </div>
                ) : success ? (
                    <div className="p-12 flex flex-col items-center justify-center text-center space-y-4 flex-1">
                        <div className={`w-20 h-20 rounded-full flex items-center justify-center border ${t.successIcon}`}>
                            <CheckCircle2 size={40} className={t.successCheck} />
                        </div>
                        <h3 className={`text-2xl font-bold ${t.successTitle}`}>Transfer Sent!</h3>
                        <p className={`font-medium ${t.successSub}`}>Your request is being processed.</p>
                    </div>
                ) : (
                    <form onSubmit={handleTransfer} className="p-6 space-y-4 overflow-y-auto no-scrollbar flex-1" noValidate>

                        {/* From account */}
                        <div>
                            <label className={labelCls}>From Account</label>
                            <select
                                value={fromAccountId}
                                onChange={e => setFromAccountId(e.target.value)}
                                className={inputCls('font-bold appearance-none')}
                                required
                            >
                                {availableFromAccounts.length > 0 ? (
                                    availableFromAccounts.map(acc => (
                                        <option key={acc.id} value={acc.id}>
                                            {acc.account_type} ({acc.owner_first_name || 'Main'}) · £{formatBalance(acc.available_balance)}
                                        </option>
                                    ))
                                ) : (
                                    <option value="">No eligible accounts available</option>
                                )}
                            </select>
                        </div>

                        {activeTab === 'EXTERNAL' ? (
                            <div className="space-y-4 animate-fadeIn">
                                {/* Recipient name */}
                                <div>
                                    <label className={labelCls}>Recipient Name</label>
                                    <input
                                        type="text"
                                        placeholder="Enter the recipient's name"
                                        value={recipientName}
                                        onChange={e => setRecipientName(e.target.value)}
                                        className={inputCls()}
                                        required
                                    />
                                </div>

                                {/* IBAN */}
                                <div>
                                    <label className={`${labelCls} flex justify-between`}>
                                        <span>Account Number (IBAN)</span>
                                        {cleanIban.length >= 2 && (
                                            isInternational
                                                ? <span className="text-blue-400 font-bold flex items-center gap-1"><Globe size={12} /> International</span>
                                                : <span className="text-emerald-500 font-bold flex items-center gap-1"><Zap size={12} /> UK Domestic</span>
                                        )}
                                    </label>
                                    <input
                                        type="text"
                                        placeholder="Enter the recipient's account number"
                                        value={recipientAccount}
                                        onChange={e => setRecipientAccount(e.target.value)}
                                        className={`w-full border rounded-xl px-4 py-3 outline-none transition-colors ${isInternational ? t.inputIntl : t.inputMono}`}
                                        required
                                    />
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    {/* Routing method */}
                                    <div>
                                        <label className={labelCls}>Transfer Network</label>
                                        <select
                                            value={routingMethod}
                                            onChange={e => setRoutingMethod(e.target.value)}
                                            disabled={isInternational}
                                            className={inputCls('font-bold appearance-none disabled:opacity-70 disabled:cursor-not-allowed')}
                                        >
                                            {isInternational ? (
                                                <option value="SWIFT">SWIFT Network</option>
                                            ) : (
                                                <>
                                                    <option value="FPS">Faster Payments (Instant)</option>
                                                    <option value="BACS">BACS (2-3 days)</option>
                                                    <option value="CHAPS">CHAPS (Same day - £20)</option>
                                                </>
                                            )}
                                        </select>
                                    </div>

                                    {/* BIC / SWIFT code */}
                                    {needsBic && (
                                        <div className="animate-fadeIn">
                                            <label className={labelCls}>BIC / SWIFT Code</label>
                                            <input
                                                type="text"
                                                placeholder={isInternational ? 'e.g. USBKUS01XXX' : 'e.g. BARCGB2L'}
                                                value={swiftCode}
                                                onChange={e => {
                                                    const value = e.target.value.toUpperCase();
                                                    setSwiftCode(value);
                                                    if (value.length >= 6) {
                                                        setTransferCurrency(currencyFromBic(value));
                                                    }
                                                }}
                                                className={`w-full border rounded-xl px-4 py-3 outline-none transition-colors ${t.inputSwift}`}
                                                required={needsBic}
                                            />
                                        </div>
                                    )}

                                    {/* SWIFT currency */}
                                    {isSwiftTransfer && (
                                        <div className="animate-fadeIn">
                                            <label className={labelCls}>SWIFT Currency</label>
                                            <select
                                                value={transferCurrency}
                                                onChange={e => setTransferCurrency(e.target.value)}
                                                className={inputCls('font-bold appearance-none')}
                                            >
                                                <option value="USD">USD</option>
                                                <option value="EUR">EUR</option>
                                                <option value="PLN">PLN</option>
                                                <option value="GBP">GBP</option>
                                            </select>
                                        </div>
                                    )}

                                    {/* SWIFT charges */}
                                    {isSwiftTransfer && (
                                        <div className="animate-fadeIn">
                                            <label className={labelCls}>Charges</label>
                                            <select
                                                value={chargeBearer}
                                                onChange={e => setChargeBearer(e.target.value as 'OUR' | 'SHA' | 'BEN')}
                                                className={inputCls('font-bold appearance-none')}
                                            >
                                                <option value="OUR">OUR - sender pays</option>
                                                <option value="SHA">SHA - shared</option>
                                                <option value="BEN">BEN - receiver pays</option>
                                            </select>
                                        </div>
                                    )}

                                    {/* Amount */}
                                    <div className={isSwiftTransfer ? 'col-span-1 md:col-span-2' : (!needsBic ? 'col-span-1' : 'col-span-1 md:col-span-2')}>
                                        <label className={labelCls}>
                                            {isSwiftTransfer ? `Amount to send (${transferCurrency})` : 'Amount'}
                                        </label>

                                        <div className="relative">
                                            <span className={`absolute left-4 top-1/2 -translate-y-1/2 font-bold ${t.prefixSymbol}`}>
                                                {isSwiftTransfer ? transferCurrency : '£'}
                                            </span>

                                            <input
                                                type="number"
                                                step="0.01"
                                                value={amount}
                                                onChange={e => setAmount(e.target.value)}
                                                placeholder="0.00"
                                                className={inputCls(isSwiftTransfer ? 'pl-16 font-bold' : 'pl-8 font-bold')}
                                                required
                                            />
                                        </div>

                                        {isSwiftTransfer && (
                                            <p className={`text-[11px] mt-2 px-1 ${t.label}`}>
                                                Your GBP account will be debited after fixed FX conversion plus local fee. {swiftFeeLabel(chargeBearer)}.
                                            </p>
                                        )}
                                        {swiftPreview && (
                                            <div className="mt-3 rounded-2xl border p-3 text-xs space-y-1"
                                                style={{
                                                    backgroundColor: 'var(--bg-base)',
                                                    borderColor: 'var(--border)',
                                                    color: 'var(--text-secondary)',
                                                }}
                                            >
                                                <div className="flex justify-between">
                                                    <span>FX rate</span>
                                                    <span className="font-bold">1 GBP = {swiftPreview.rate.toFixed(2)} {transferCurrency}</span>
                                                </div>

                                                <div className="flex justify-between">
                                                    <span>Converted amount</span>
                                                    <span className="font-bold">£{swiftPreview.converted.toFixed(2)}</span>
                                                </div>

                                                <div className="flex justify-between">
                                                    <span>Fee ({chargeBearer})</span>
                                                    <span className="font-bold">£{swiftPreview.fee.toFixed(2)}</span>
                                                </div>

                                                <div className="flex justify-between pt-2 mt-2 border-t"
                                                    style={{ borderColor: 'var(--border)' }}
                                                >
                                                    <span className="font-black">Total debit</span>
                                                    <span className="font-black">£{swiftPreview.total.toFixed(2)}</span>
                                                </div>

                                                <p className="pt-1 text-[11px]" style={{ color: 'var(--text-muted)' }}>
                                                    {swiftFeeLabel(chargeBearer)}.
                                                </p>
                                            </div>
                                        )}
                                    </div>

                                    {/* Title */}
                                    <div className="col-span-1 md:col-span-2">
                                        <label className={labelCls}>Title</label>
                                        <input
                                            type="text"
                                            placeholder="Transfer title"
                                            value={title}
                                            onChange={e => setTitle(e.target.value)}
                                            className={inputCls()}
                                            required
                                        />
                                    </div>
                                </div>
                            </div>
                        ) : (
                            <div className="space-y-4 animate-fadeIn">
                                <div>
                                    <label className={labelCls}>To Account</label>
                                    <select
                                        value={toAccountId}
                                        onChange={e => setToAccountId(e.target.value)}
                                        className={inputCls('font-bold appearance-none')}
                                        required
                                    >
                                        <option value="">Select target account</option>
                                        {accounts.filter(acc => acc.id !== fromAccountId).map(acc => (
                                            <option key={acc.id} value={acc.id}>
                                                {acc.account_type} ({acc.owner_first_name || 'Main'}) · £{formatBalance(acc.available_balance)}
                                            </option>
                                        ))}
                                    </select>
                                </div>

                                <div>
                                    <label className={labelCls}>Amount</label>
                                    <div className="relative">
                                        <span className={`absolute left-4 top-1/2 -translate-y-1/2 font-bold ${t.prefixSymbol}`}>£</span>
                                        <input
                                            type="number"
                                            step="0.01"
                                            value={amount}
                                            onChange={e => setAmount(e.target.value)}
                                            placeholder="0.00"
                                            className={inputCls('pl-8 font-bold')}
                                            required
                                        />
                                    </div>
                                </div>
                            </div>
                        )}

                        <button
                            type="submit"
                            disabled={loading || !amount || !fromAccountId}
                            className={`w-full py-4 rounded-2xl transition-all mt-4 uppercase tracking-widest text-xs font-black shrink-0 disabled:opacity-50 ${t.submitBtn}`}
                        >
                            {loading ? 'Processing...' : 'Confirm Transfer'}
                        </button>

                    </form>
                )}
            </div>
        </div>
    );
};

export default TransferModal;
