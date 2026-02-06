
import React, { useState, useEffect, useRef } from 'react';
/* Added missing icon imports from lucide-react */
import { Phone, User, ShieldCheck, X, Check, Wallet, Sparkles, AlertCircle, Save, MicOff, Pause, PhoneForwarded, ChevronDown, Mail, MapPin, Calendar, Building2, History, ExternalLink, TrendingUp, Info, Clock, MousePointer2, ListChecks, CalendarClock, UserCheck, CreditCard, ArrowRightLeft, Search, ArrowLeft, ChevronRight } from 'lucide-react';
import { Customer, CallStep, Interaction } from '../types';

const mockCustomer: Customer = {
  id: 'CUST-8492',
  name: 'Sarah Jenkins',
  email: 'sarah.jenkins@example.com',
  phone: '+1 (555) 012-3456',
  address: '123 Emerald Way, Toronto, ON M5H 2N2',
  dob: 'May 14, 1982',
  accountLevel: 'Premium',
  lastInteraction: '2 days ago',
  sentiment: 'Negative',
  issue: 'Recurring billing discrepancy on Enterprise Plan upgrade',
  jointHolders: ['Mark Jenkins'],
  activePromotions: ['Loyalty Credit Active', 'Platinum Savings Qualified'],
  interactions: [
    { 
      date: 'Oct 22, 2024', 
      type: 'Bank Visit', 
      reason: 'Mortgage Inquiry', 
      agentAction: 'Collected physical ID and pay stubs. Initiated preliminary credit check.', 
      outcome: 'Pending Documents' 
    },
    { 
      date: 'Oct 20, 2024', 
      type: 'Call', 
      reason: 'Technical Support', 
      agentAction: 'Walked customer through 2FA reset process and app cache clearance.', 
      outcome: 'Resolved' 
    },
    { 
      date: 'Oct 15, 2024', 
      type: 'Call', 
      reason: 'Billing Dispute', 
      agentAction: 'Verified October billing statement. Noted $35 surcharge mismatch.', 
      outcome: 'Escalated' 
    }
  ]
};

const mockTransactions = [
  { id: 1, date: 'Oct 24, 2024', desc: 'Starbucks Coffee #283', amount: '-$6.45', account: 'Chequing (...8849)' },
  { id: 2, date: 'Oct 23, 2024', desc: 'Shell Oil Co.', amount: '-$52.10', account: 'Chequing (...8849)' },
  { id: 3, date: 'Oct 22, 2024', desc: 'TFSA Contribution', amount: '+$5,000.00', account: 'TFSA (...0021)' },
  { id: 4, date: 'Oct 21, 2024', desc: 'Amazon Prime', amount: '-$14.99', account: 'Visa (...4411)' },
  { id: 5, date: 'Oct 20, 2024', desc: 'Walmart Supercentre', amount: '-$142.30', account: 'Chequing (...8849)' },
  { id: 6, date: 'Oct 19, 2024', desc: 'Dividend Payment', amount: '+$240.15', account: 'Mutual Fund (...4411)' },
];

const promotionsList = [
  {
    id: 1,
    title: "Platinum Savings Upgrade",
    description: "Upgrade to Platinum Savings to earn 4.5% APY. Customer qualifies based on current balance > $10k.",
    code: "SAVE-PLAT-24",
    eligibility: "Minimum balance of $10,000 across all liquid accounts. Active checking account for 12+ months.",
    steps: [
      "Confirm current total balance is verified.",
      "Inform client about the 4.5% APY variable rate.",
      "Verify 'Paperless Billing' is enabled.",
      "Execute the 'Tier Upgrade' tool in the Account Management console."
    ],
    expiry: "December 31, 2024"
  },
  {
    id: 2,
    title: "Travel Rewards Visa",
    description: "Pre-approved for 50k bonus points. No annual fee for the first year.",
    code: "VISA-TRV-50",
    eligibility: "Credit score > 740. No late payments on current Visa Signature in the last 24 months.",
    steps: [
      "Disclose the 22.99% variable APR.",
      "Confirm primary mailing address is current.",
      "Select 'Apply Pre-Approved Code' in the Credit Portal.",
      "Read mandatory credit disclosure script to the client."
    ],
    expiry: "November 15, 2024"
  }
];

const ActiveCall: React.FC = () => {
  // Call Lifecycle State
  const [callStep, setCallStep] = useState<CallStep>('SUMMARY');
  const [showPromos, setShowPromos] = useState(false);
  
  // UI States
  const [activeTab, setActiveTab] = useState<'transactions' | 'transfer'>('transactions');
  const [selectedPromoId, setSelectedPromoId] = useState<number | null>(null);
  const [selectedAccount, setSelectedAccount] = useState<string | null>(null);
  const [dismissedPromoIds, setDismissedPromoIds] = useState<number[]>([]);
  const [callbackRequired, setCallbackRequired] = useState(false);

  // Summary Detailed View State
  const [selectedSummaryInteraction, setSelectedSummaryInteraction] = useState<number | null>(null);

  // Phone Controls
  const [isMuted, setIsMuted] = useState(false);
  const [isOnHold, setIsOnHold] = useState(false);
  const [agentStatus, setAgentStatus] = useState('On Call');
  const [showStatusMenu, setShowStatusMenu] = useState(false);
  const [callTimer, setCallTimer] = useState(0);

  // Draggable Popup State for Summary
  const [popupPos, setPopupPos] = useState({ x: 400, y: 150 });
  const [isDragging, setIsDragging] = useState(false);
  const dragRef = useRef<{ startX: number; startY: number; startPosX: number; startPosY: number } | null>(null);

  // Call Timer Effect
  useEffect(() => {
    let interval: any;
    if (callStep === 'ACTIVE' || callStep === 'SUMMARY') {
      interval = setInterval(() => {
        setCallTimer(prev => prev + 1);
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [callStep]);

  // Trigger Promotions after Acknowledging Summary (the "Condition")
  useEffect(() => {
    if (callStep === 'ACTIVE') {
      const timer = setTimeout(() => {
        setShowPromos(true);
      }, 3000); // 3 seconds after summary is closed
      return () => clearTimeout(timer);
    }
  }, [callStep]);

  const handleMouseDown = (e: React.MouseEvent) => {
    if (callStep !== 'SUMMARY') return;
    setIsDragging(true);
    dragRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      startPosX: popupPos.x,
      startPosY: popupPos.y,
    };
  };

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging || !dragRef.current) return;
      const dx = e.clientX - dragRef.current.startX;
      const dy = e.clientY - dragRef.current.startY;
      setPopupPos({
        x: dragRef.current.startPosX + dx,
        y: dragRef.current.startPosY + dy,
      });
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    }
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging]);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const selectedPromo = promotionsList.find(p => p.id === selectedPromoId);
  const visiblePromos = promotionsList.filter(p => !dismissedPromoIds.includes(p.id));

  return (
    <div className="flex flex-col h-full p-6 relative gap-6 overflow-hidden select-none">
      
      {/* HEADER & CONTROLS */}
      <div className="flex flex-col gap-4 flex-shrink-0">
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <div className="relative">
              <div className="w-16 h-16 bg-emerald-100 rounded-full flex items-center justify-center text-emerald-800 border-2 border-emerald-50 shadow-inner">
                <User className="w-8 h-8" />
              </div>
              <div className="absolute -bottom-1 -right-1 bg-emerald-500 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full border-2 border-white flex items-center gap-0.5 shadow-sm">
                <ShieldCheck className="w-3 h-3" />
                Verified
              </div>
            </div>
            
            <div className="flex items-center gap-10">
              <div className="min-w-[180px]">
                <h2 className="text-xl font-bold text-slate-900 flex items-center gap-2">
                  {mockCustomer.name}
                  <span className="bg-emerald-50 text-emerald-700 text-[10px] px-2 py-0.5 rounded-full border border-emerald-100 font-bold uppercase">{mockCustomer.accountLevel}</span>
                </h2>
                <div className="flex flex-col gap-1 mt-1">
                  <span className="text-sm text-slate-500 font-mono flex items-center gap-1.5"><Phone className="w-3 h-3 text-slate-400" /> {mockCustomer.phone}</span>
                  <span className="text-sm text-slate-500 flex items-center gap-1.5"><Mail className="w-3 h-3 text-slate-400" /> {mockCustomer.email}</span>
                </div>
              </div>

              <div className="h-10 w-px bg-slate-100"></div>

              <div className="grid grid-cols-2 gap-x-12 items-center">
                <div>
                  <span className="text-[10px] text-slate-400 font-bold uppercase block tracking-wider mb-1">Mailing Address</span>
                  <span className="text-sm text-slate-700 flex items-center gap-2 font-medium"><MapPin className="w-4 h-4 text-emerald-600" /> {mockCustomer.address}</span>
                </div>
                <div>
                  <span className="text-[10px] text-slate-400 font-bold uppercase block tracking-wider mb-1">Date of Birth</span>
                  <span className="text-sm text-slate-700 flex items-center gap-2 font-medium"><Calendar className="w-4 h-4 text-emerald-600" /> {mockCustomer.dob}</span>
                </div>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-6">
            <div className="relative">
              <button 
                onClick={() => setShowStatusMenu(!showStatusMenu)}
                className="flex items-center gap-2 px-3 py-1.5 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-lg transition-colors"
              >
                <span className={`w-2.5 h-2.5 rounded-full ${agentStatus === 'On Call' ? 'bg-rose-500 animate-pulse' : 'bg-emerald-500'}`}></span>
                <span className="text-sm font-semibold text-slate-700">{agentStatus}</span>
                <ChevronDown className="w-4 h-4 text-slate-400" />
              </button>
              {showStatusMenu && (
                <div className="absolute top-full right-0 mt-2 w-40 bg-white border border-slate-200 rounded-lg shadow-lg z-50 py-1">
                  <button onClick={() => { setAgentStatus('Ready'); setShowStatusMenu(false); }} className="w-full text-left px-4 py-2 text-sm hover:bg-emerald-50 text-slate-700 flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-emerald-500"></span> Ready
                  </button>
                  <button onClick={() => { setAgentStatus('On Call'); setShowStatusMenu(false); }} className="w-full text-left px-4 py-2 text-sm hover:bg-rose-50 text-slate-700 flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-rose-500"></span> On Call
                  </button>
                </div>
              )}
            </div>
            <div className="flex items-center gap-3">
              <div className="flex flex-col items-end mr-2">
                <span className="font-mono text-lg font-bold text-slate-800 leading-none">{formatTime(callTimer)}</span>
                <span className={`text-[10px] font-bold uppercase tracking-wider ${callStep === 'RECAP' ? 'text-slate-400' : 'text-emerald-600'}`}>
                  {callStep === 'RECAP' ? 'Disconnected' : 'Connected'}
                </span>
              </div>
              <button onClick={() => setIsMuted(!isMuted)} className={`p-3 rounded-full transition-colors ${isMuted ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}><MicOff className="w-5 h-5" /></button>
              <button onClick={() => setIsOnHold(!isOnHold)} className={`p-3 rounded-full transition-colors ${isOnHold ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}><Pause className="w-5 h-5" /></button>
              <button 
                disabled={callStep === 'RECAP'}
                onClick={() => setCallStep('RECAP')}
                className={`p-3 rounded-full shadow-md transform rotate-[135deg] transition-all ${callStep === 'RECAP' ? 'bg-slate-200 text-slate-400 cursor-not-allowed' : 'bg-rose-600 text-white hover:bg-rose-700'}`}
              >
                <Phone className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>

        {/* ACCOUNT STRIP */}
        <div className="flex items-center gap-4 overflow-x-auto pb-1 scrollbar-hide">
          {[
            { label: 'Chequing', num: '...8849', bal: '$12,450.00', icon: Wallet },
            { label: 'Savings', num: '...9921', bal: '$45,000.00', icon: TrendingUp },
            { label: 'TFSA', num: '...0021', bal: '$28,300.00', icon: ShieldCheck },
            { label: 'Mutual Fund', num: '...4411', bal: '$105,400.00', icon: CreditCard },
          ].map((acc) => (
            <div 
              key={acc.label}
              onClick={() => setSelectedAccount(acc.label)}
              className="bg-white border border-slate-200 rounded-xl p-3 min-w-[210px] flex items-center justify-between cursor-pointer hover:border-emerald-500 transition-all hover:shadow-md group shadow-sm"
            >
              <div className="flex items-center gap-3">
                <div className="bg-emerald-50 p-2 rounded-lg text-emerald-600 group-hover:bg-emerald-600 group-hover:text-white transition-colors">
                  <acc.icon className="w-4 h-4" />
                </div>
                <div>
                  <p className="text-[10px] text-slate-400 uppercase font-bold tracking-wider">{acc.label} ({acc.num})</p>
                  <p className="text-sm font-bold text-slate-800">{acc.bal}</p>
                </div>
              </div>
              <div className="p-1 rounded bg-slate-50 group-hover:bg-emerald-50">
                <ExternalLink className="w-3 h-3 text-slate-300 group-hover:text-emerald-500" />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* WORKSPACE AREA */}
      <div className="flex-1 bg-white rounded-xl shadow-sm border border-slate-200 flex flex-col overflow-hidden relative">
        <div className="flex items-center justify-between border-b border-slate-100 bg-slate-50/50 pr-4">
          <div className="flex">
            <button onClick={() => setActiveTab('transactions')} className={`px-8 py-4 text-sm font-bold border-b-2 transition-all flex items-center gap-2 ${activeTab === 'transactions' ? 'border-emerald-600 text-emerald-800 bg-white' : 'border-transparent text-slate-500 hover:bg-slate-50'}`}>
              <History className="w-4 h-4" /> Transaction History
            </button>
            <button onClick={() => setActiveTab('transfer')} className={`px-8 py-4 text-sm font-bold border-b-2 transition-all flex items-center gap-2 ${activeTab === 'transfer' ? 'border-emerald-600 text-emerald-800 bg-white' : 'border-transparent text-slate-500 hover:bg-slate-50'}`}>
              <ArrowRightLeft className="w-4 h-4" /> Transfer Call
            </button>
          </div>
          
          {callStep === 'ACTIVE' && (
             <div className="flex items-center gap-3">
                <button 
                  onClick={() => {
                    setSelectedSummaryInteraction(null);
                    setCallStep('SUMMARY');
                  }}
                  className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-600 text-[10px] font-bold rounded-lg transition-all flex items-center gap-1.5 border border-slate-200"
                >
                  <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></div>
                  Client Summary
                </button>
             </div>
          )}
        </div>

        <div className="flex-1 p-6 overflow-y-auto custom-scrollbar bg-white">
          {activeTab === 'transactions' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between mb-2">
                <div className="relative ml-auto">
                  <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                  <input type="text" placeholder="Filter transactions..." className="pl-9 pr-4 py-1.5 text-xs bg-slate-100 border-none rounded-lg focus:ring-1 focus:ring-emerald-500 w-64" />
                </div>
              </div>
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-slate-100">
                    <th className="pb-3 text-[10px] font-bold text-slate-400 uppercase tracking-widest">Date</th>
                    <th className="pb-3 text-[10px] font-bold text-slate-400 uppercase tracking-widest">Description</th>
                    <th className="pb-3 text-[10px] font-bold text-slate-400 uppercase tracking-widest">From / To Account</th>
                    <th className="pb-3 text-[10px] font-bold text-slate-400 uppercase tracking-widest text-right">Amount</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50">
                  {mockTransactions.map((tx) => (
                    <tr key={tx.id} className="hover:bg-slate-50 transition-colors group">
                      <td className="py-3.5 text-sm text-slate-600">{tx.date}</td>
                      <td className="py-3.5 text-sm font-bold text-slate-800">{tx.desc}</td>
                      <td className="py-3.5 text-xs font-medium text-slate-500">
                        <span className="bg-slate-100 px-2 py-1 rounded border border-slate-200">{tx.account}</span>
                      </td>
                      <td className={`py-3.5 text-sm font-bold text-right ${tx.amount.startsWith('+') ? 'text-emerald-600' : 'text-slate-800'}`}>{tx.amount}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {activeTab === 'transfer' && (
            <div className="max-w-2xl mx-auto space-y-8 py-10">
              <div className="bg-slate-50 border border-slate-200 rounded-xl p-8 text-center flex flex-col items-center">
                <Building2 className="w-12 h-12 text-slate-400 mb-4" />
                <h3 className="text-xl font-bold text-slate-800">Route Session</h3>
                <p className="text-sm text-slate-500 mt-2 max-w-sm">Select target department to initiate a transfer.</p>
              </div>
              
              <div className="grid grid-cols-2 gap-6">
                <div className="space-y-3">
                  <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Target Department</label>
                  <select className="w-full p-4 bg-white border border-slate-300 rounded-xl text-sm font-bold focus:ring-2 focus:ring-emerald-500 outline-none shadow-sm">
                    <option>Billing & Claims Escalations</option>
                    <option>Mortgage Solutions Team</option>
                    <option>Investment & Wealth Advisory</option>
                  </select>
                </div>
                <div className="space-y-3">
                  <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Urgency Level</label>
                  <div className="flex gap-3">
                    <button className="flex-1 py-4 bg-white text-slate-600 text-xs font-bold rounded-xl border border-slate-200 hover:bg-slate-50 transition-colors shadow-sm">Standard</button>
                    <button className="flex-1 py-4 bg-rose-50 text-rose-700 text-xs font-bold rounded-xl border border-rose-200 hover:bg-rose-100 transition-colors shadow-sm">High Priority</button>
                  </div>
                </div>
              </div>
              
              <button className="w-full py-5 bg-emerald-600 text-white font-bold rounded-xl hover:bg-emerald-700 transition-all shadow-xl flex items-center justify-center gap-3 text-lg group">
                <PhoneForwarded className="w-6 h-6 group-hover:translate-x-1 transition-transform" /> Initiate Transfer
              </button>
            </div>
          )}
        </div>

        {/* PROMOTIONS BANNERS (Conditional pop-up) */}
        {callStep === 'ACTIVE' && showPromos && (
          <div className="absolute bottom-6 left-6 right-6 flex flex-col gap-3 z-10 pointer-events-none">
            {visiblePromos.map((promo, index) => (
              <div 
                key={promo.id}
                className="bg-white rounded-xl shadow-[0_10px_40px_rgb(0,0,0,0.18)] border border-emerald-100 p-4 flex items-center justify-between transform transition-all hover:-translate-y-1 animate-in slide-in-from-bottom-6 duration-300 group pointer-events-auto"
                style={{ marginBottom: index * -8, zIndex: promotionsList.length - index }}
              >
                <div className="flex items-center gap-4 flex-1">
                  <div className="bg-emerald-100 p-2.5 rounded-lg text-emerald-700 group-hover:bg-emerald-600 group-hover:text-white transition-colors">
                    <Sparkles className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h4 className="font-bold text-slate-800">{promo.title}</h4>
                    </div>
                    <p className="text-sm text-slate-500 line-clamp-1">{promo.description}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <button 
                    onClick={() => setSelectedPromoId(promo.id)}
                    className="px-6 py-2 bg-emerald-600 text-white text-sm font-bold rounded-lg hover:bg-emerald-700 transition-colors shadow-sm"
                  >
                    View Details
                  </button>
                  <button 
                    onClick={(e) => {
                        e.stopPropagation();
                        setDismissedPromoIds(prev => [...prev, promo.id]);
                    }}
                    className="p-2 text-slate-300 hover:text-rose-500 transition-colors rounded-lg hover:bg-rose-50"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* CLIENT SUMMARY (Initial State Overlay) */}
        {callStep === 'SUMMARY' && (
           <div 
             className="absolute z-[100] bg-white rounded-2xl shadow-[0_20px_60px_-15px_rgba(0,0,0,0.3)] border border-slate-200 flex flex-col w-[540px] animate-in zoom-in-95 duration-200"
             style={{ top: popupPos.y, left: popupPos.x }}
           >
              <div 
                onMouseDown={handleMouseDown}
                className="bg-emerald-900 px-6 py-4 flex items-center justify-between rounded-t-2xl text-white cursor-move active:cursor-grabbing"
              >
                 <div className="flex items-center gap-3">
                   <div className="p-2 bg-white/10 rounded-lg"><User className="w-5 h-5 text-emerald-300" /></div>
                   <div>
                     <h3 className="text-sm font-bold leading-none">
                       {selectedSummaryInteraction !== null ? 'Interaction Details' : 'Client Summary'}
                     </h3>
                   </div>
                 </div>
                 <div className="flex items-center gap-2">
                    <MousePointer2 className="w-3.5 h-3.5 text-emerald-500" />
                 </div>
              </div>
              
              <div className="p-6 overflow-y-auto max-h-[500px] custom-scrollbar space-y-8 bg-white min-h-[300px]">
                 {selectedSummaryInteraction === null ? (
                   <>
                    <div>
                        <div className="flex items-center justify-between mb-4">
                        <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest flex items-center gap-2">
                            <Clock className="w-3.5 h-3.5" /> Recent Interactions
                        </h4>
                        </div>
                        <div className="space-y-4 relative before:absolute before:left-[11px] before:top-2 before:bottom-2 before:w-px before:bg-slate-100">
                        {mockCustomer.interactions?.map((it, idx) => (
                            <button 
                              key={idx} 
                              onClick={() => setSelectedSummaryInteraction(idx)}
                              className="w-full flex gap-4 relative group text-left outline-none"
                            >
                            <div className={`w-[23px] h-[23px] rounded-full flex items-center justify-center flex-shrink-0 z-10 transition-colors ${idx === 0 ? 'bg-emerald-500 text-white' : 'bg-white border border-slate-200 text-slate-400'} group-hover:bg-emerald-600 group-hover:text-white`}>
                                {it.type === 'Call' ? <Phone className="w-3 h-3" /> : <Building2 className="w-3 h-3" />}
                            </div>
                            <div className="flex-1 bg-slate-50/50 p-3 rounded-xl border border-transparent hover:border-slate-200 hover:bg-white transition-all flex items-center justify-between">
                                <div>
                                    <div className="flex justify-between items-center mb-1">
                                    <span className="text-xs font-bold text-slate-800">{it.type}: {it.reason}</span>
                                    </div>
                                    <span className="text-[10px] font-medium text-slate-400">{it.date}</span>
                                </div>
                                <ChevronRight className="w-4 h-4 text-slate-300 group-hover:text-emerald-500 transition-colors" />
                            </div>
                            </button>
                        ))}
                        </div>
                    </div>

                    <div className="bg-rose-50 border border-rose-100 rounded-xl p-4">
                        <div className="flex items-center gap-2 text-rose-700 mb-2">
                        <AlertCircle className="w-4 h-4" />
                        <span className="text-[10px] font-bold uppercase tracking-wider">Unresolved Billing Dispute</span>
                        </div>
                        <p className="text-xs text-rose-900 font-bold mb-1">Audit Required: Ticket #88392</p>
                        <p className="text-[11px] text-rose-800 leading-relaxed">System identified a failed 'Loyalty Credit' application. Customer likely calling about the $35.00 discrepancy.</p>
                    </div>
                   </>
                 ) : (
                   <div className="animate-in fade-in slide-in-from-right-4 duration-200 space-y-6">
                      <button 
                        onClick={() => setSelectedSummaryInteraction(null)}
                        className="flex items-center gap-2 text-xs font-bold text-emerald-600 hover:text-emerald-700 transition-colors group"
                      >
                         <ArrowLeft className="w-3.5 h-3.5 group-hover:-translate-x-0.5 transition-transform" /> Back to Interactions
                      </button>

                      <div className="space-y-5">
                         <div className="bg-slate-50 border border-slate-200 rounded-2xl p-4 shadow-sm">
                            <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block mb-2">Interaction Reason</label>
                            <p className="text-sm font-bold text-slate-800">{mockCustomer.interactions![selectedSummaryInteraction].reason}</p>
                         </div>
                         
                         <div className="bg-white border border-slate-200 rounded-2xl p-4 shadow-sm">
                            <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block mb-2">Agent Action</label>
                            <p className="text-sm text-slate-700 leading-relaxed font-medium">
                              {mockCustomer.interactions![selectedSummaryInteraction].agentAction}
                            </p>
                         </div>

                         <div className="bg-emerald-50 border border-emerald-100 rounded-2xl p-4 shadow-sm">
                            <label className="text-[10px] font-bold text-emerald-600 uppercase tracking-widest block mb-2">Interaction Outcome</label>
                            <p className="text-sm font-bold text-emerald-800">{mockCustomer.interactions![selectedSummaryInteraction].outcome}</p>
                         </div>
                      </div>
                   </div>
                 )}
              </div>
              
              <div className="p-4 border-t border-slate-100 flex justify-end bg-slate-50/50 rounded-b-2xl">
                 <button 
                  onClick={() => setCallStep('ACTIVE')}
                  className="px-6 py-2.5 bg-slate-900 text-white rounded-xl text-xs font-bold hover:bg-black transition-colors shadow-lg"
                 >
                    Dismiss
                 </button>
              </div>
           </div>
        )}
      </div>

      {/* PROMO DETAIL MODAL */}
      {selectedPromoId && selectedPromo && (
        <div className="fixed inset-0 z-[300] flex items-center justify-center bg-slate-900/60 backdrop-blur-md p-6">
           <div className="bg-white w-full max-w-3xl rounded-3xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200 border border-slate-200">
              <div className="bg-emerald-700 p-8 text-white relative">
                 <button onClick={() => setSelectedPromoId(null)} className="absolute top-6 right-6 text-emerald-100 hover:text-white transition-all bg-white/20 hover:bg-white/30 rounded-full p-2.5 border border-white/20 group">
                    <X className="w-5 h-5 group-hover:scale-110 transition-transform" />
                 </button>
                 <div className="flex items-center gap-6">
                    <div className="w-16 h-16 bg-white/10 rounded-2xl flex items-center justify-center backdrop-blur-md border border-white/20"><Sparkles className="w-10 h-10 text-emerald-100" /></div>
                    <div>
                        <h3 className="text-3xl font-extrabold tracking-tight">{selectedPromo.title}</h3>
                        <div className="flex items-center gap-3 mt-2">
                           <span className="text-emerald-100 text-xs font-mono bg-emerald-800/50 px-3 py-1 rounded border border-emerald-600 uppercase tracking-widest">{selectedPromo.code}</span>
                           <div className="flex items-center gap-1.5 text-emerald-200 text-xs font-bold bg-emerald-900/40 px-3 py-1 rounded-full">
                              <CalendarClock className="w-3.5 h-3.5" /> Expiry: {selectedPromo.expiry}
                           </div>
                        </div>
                    </div>
                 </div>
              </div>
              
              <div className="p-8 grid grid-cols-1 md:grid-cols-2 gap-10 bg-slate-50/30 overflow-y-auto max-h-[70vh] custom-scrollbar">
                 <div className="space-y-8">
                    <div>
                        <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-3 flex items-center gap-2">
                           <Info className="w-4 h-4 text-emerald-600" /> Promotion Details
                        </h4>
                        <p className="text-sm text-slate-700 leading-relaxed font-medium bg-white p-4 rounded-2xl border border-slate-100 shadow-sm">{selectedPromo.description}</p>
                    </div>
                    <div>
                        <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-3 flex items-center gap-2">
                           <UserCheck className="w-4 h-4 text-emerald-600" /> Eligibility Criteria
                        </h4>
                        <div className="bg-emerald-50/50 p-4 rounded-2xl border border-emerald-100 text-sm text-emerald-900 font-medium italic">"{selectedPromo.eligibility}"</div>
                    </div>
                 </div>

                 <div className="space-y-8">
                    <div>
                        <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-3 flex items-center gap-2">
                           <ListChecks className="w-4 h-4 text-emerald-600" /> Fulfillment Steps
                        </h4>
                        <div className="space-y-3">
                           {selectedPromo.steps.map((step, i) => (
                             <div key={i} className="flex gap-3 items-start bg-white p-3 rounded-xl border border-slate-100 shadow-sm">
                                <div className="w-5 h-5 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center text-[10px] font-bold flex-shrink-0 mt-0.5">{i+1}</div>
                                <span className="text-xs text-slate-700 font-medium leading-normal">{step}</span>
                             </div>
                           ))}
                        </div>
                    </div>
                 </div>
              </div>
              <div className="h-4 bg-slate-50 border-t border-slate-100"></div>
           </div>
        </div>
      )}

      {/* CALL RECAP MODAL (Displayed once hanging up) */}
      {callStep === 'RECAP' && (
         <div className="absolute inset-0 z-[400] flex items-center justify-center bg-slate-900/80 backdrop-blur-sm p-4">
            <div className="bg-white w-full max-w-5xl rounded-3xl shadow-2xl overflow-hidden animate-in slide-in-from-bottom-12 duration-500 flex flex-col border border-white/20">
               <div className="px-8 py-6 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-emerald-600 rounded-xl shadow-lg shadow-emerald-200"><Check className="w-6 h-6 text-white" /></div>
                    <h3 className="text-2xl font-extrabold text-slate-900 tracking-tight">Call Recap</h3>
                  </div>
                  <div className="text-xs font-bold text-slate-500 bg-slate-100 px-4 py-2 rounded-xl border border-slate-200 tracking-wider font-mono">ID: #CALL-99283</div>
               </div>
               
               <div className="p-10 grid grid-cols-1 md:grid-cols-2 gap-10 overflow-y-auto max-h-[70vh]">
                  <div className="space-y-8">
                     <div>
                        <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-3">Call Reason</label>
                        <textarea className="w-full h-28 p-4 bg-slate-50 border border-slate-200 rounded-2xl text-sm font-medium focus:ring-2 focus:ring-emerald-500 outline-none transition-all resize-none shadow-inner" defaultValue="Customer identified recurring overcharge in Enterprise Plan upgrade. Expressed frustration over billing complexity and requested immediate audit of October transactions." />
                     </div>
                     <div>
                        <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-3">Resolution Outcome</label>
                        <select className="w-full p-4 bg-white border border-slate-300 rounded-2xl text-sm font-bold text-slate-700 shadow-sm focus:ring-2 focus:ring-emerald-500">
                           <option>Resolved - Customer Satisfied</option>
                           <option>Escalated to Billing Support</option>
                           <option>Partial Resolution - Pending Action</option>
                        </select>
                     </div>
                  </div>

                  <div className="space-y-8">
                     <div>
                        <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-3">Actions Performed</label>
                        <textarea className="w-full h-28 p-4 bg-white border border-slate-300 rounded-2xl text-sm font-medium focus:ring-2 focus:ring-emerald-500 shadow-sm resize-none leading-relaxed" placeholder="Detailed resolution steps taken..." defaultValue="Reversed Oct 15th surcharge on Chequing (...8849). Manually updated account status to 'Verified Premium'. Sent confirmation email #CF-8829." />
                     </div>
                     <div className="bg-slate-50 border border-slate-200 p-6 rounded-2xl shadow-inner">
                        <div className="flex items-center justify-between mb-4">
                             <label className="flex items-center gap-3 cursor-pointer" onClick={() => setCallbackRequired(!callbackRequired)}>
                                <div className={`w-6 h-6 rounded-lg border flex items-center justify-center transition-all ${callbackRequired ? 'bg-emerald-600 border-emerald-600 shadow-md shadow-emerald-200' : 'bg-white border-slate-300'}`}>
                                    {callbackRequired && <Check className="w-4 h-4 text-white" />}
                                </div>
                                <span className="text-sm font-bold text-slate-800 tracking-tight">Schedule Follow-up Call</span>
                             </label>
                        </div>
                        {callbackRequired && (
                            <div className="flex gap-3 animate-in slide-in-from-top-3">
                                <input type="date" className="flex-1 p-3 bg-white border border-slate-300 rounded-xl text-sm shadow-sm font-medium" />
                                <input type="time" className="w-32 p-3 bg-white border border-slate-300 rounded-xl text-sm shadow-sm font-medium" />
                            </div>
                        )}
                     </div>
                  </div>
               </div>
               
               <div className="px-10 py-8 bg-slate-50 border-t border-slate-200 flex justify-end gap-5 flex-shrink-0">
                  <button onClick={() => window.location.reload()} className="px-14 py-3.5 bg-emerald-600 text-white font-bold rounded-2xl hover:bg-emerald-700 transition-all shadow-xl hover:shadow-emerald-200 flex items-center gap-3 text-sm">
                    <Save className="w-5 h-5" /> Complete Session
                  </button>
               </div>
            </div>
         </div>
      )}

      {/* ACCOUNT DETAILS POPUP */}
      {selectedAccount && (
        <div className="fixed inset-0 z-[500] flex items-center justify-center bg-slate-900/60 backdrop-blur-md">
          <div className="bg-white rounded-3xl shadow-2xl w-full max-w-lg overflow-hidden animate-in zoom-in-95 duration-200 border border-white/20">
            <div className="bg-emerald-800 p-8 text-white flex items-center justify-between relative overflow-hidden">
              <div className="absolute top-0 right-0 p-8 opacity-10"><Wallet className="w-32 h-32" /></div>
              <div className="flex items-center gap-4 relative z-10">
                <div className="bg-white/20 p-3 rounded-2xl backdrop-blur-md border border-white/30"><TrendingUp className="w-8 h-8" /></div>
                <div>
                  <h3 className="text-2xl font-bold">{selectedAccount}</h3>
                  <p className="text-emerald-300 text-xs font-mono uppercase tracking-widest mt-1">Full Service Access</p>
                </div>
              </div>
              <button onClick={() => setSelectedAccount(null)} className="p-2 hover:bg-white/10 rounded-xl transition-colors relative z-10"><X className="w-6 h-6" /></button>
            </div>
            <div className="p-10 space-y-8">
              <div className="grid grid-cols-2 gap-8">
                <div>
                   <p className="text-[10px] text-slate-400 uppercase font-bold tracking-widest mb-1.5">Account Status</p>
                   <p className="text-base font-bold text-emerald-600 flex items-center gap-2">Active <div className="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]"></div></p>
                </div>
                <div>
                   <p className="text-[10px] text-slate-400 uppercase font-bold tracking-widest mb-1.5">Current Rate</p>
                   <p className="text-base font-bold text-slate-800">4.50% APY</p>
                </div>
              </div>
              <button onClick={() => setSelectedAccount(null)} className="w-full py-4 bg-emerald-600 text-white font-bold rounded-2xl hover:bg-emerald-700 transition-all shadow-lg hover:shadow-emerald-200">Close Account View</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ActiveCall;
