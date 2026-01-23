import React from 'react';
import { PhoneIncoming, Users, Clock, CheckCircle2, TrendingUp, BarChart3 } from 'lucide-react';
import StatsCard from './StatsCard';
import { CallLog } from '../types';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';

const mockChartData = [
  { time: '9am', calls: 45 },
  { time: '10am', calls: 72 },
  { time: '11am', calls: 108 },
  { time: '12pm', calls: 95 },
  { time: '1pm', calls: 85 },
  { time: '2pm', calls: 120 },
  { time: '3pm', calls: 110 },
];

const mockRecentCalls: CallLog[] = [
  { id: '1', time: '10:42 AM', duration: '5m 23s', customer: 'Acme Corp', topic: 'Billing', status: 'Resolved' },
  { id: '2', time: '10:35 AM', duration: '12m 10s', customer: 'John Doe', topic: 'Tech Support', status: 'Escalated' },
  { id: '3', time: '10:15 AM', duration: '3m 45s', customer: 'Jane Smith', topic: 'Inquiry', status: 'Resolved' },
];

const Dashboard: React.FC = () => {
  return (
    <div className="space-y-6 h-full overflow-y-auto custom-scrollbar pr-2">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-slate-800">Real-time Overview</h2>
        <div className="flex items-center gap-2 text-sm text-emerald-700 bg-white px-3 py-1.5 rounded-lg border border-emerald-100 shadow-sm">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
          System Operational
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard 
          title="Calls Waiting" 
          value="12" 
          change="+3" 
          trend="up" 
          icon={PhoneIncoming} 
          color="bg-emerald-600" 
        />
        <StatsCard 
          title="Avg Handle Time" 
          value="4m 12s" 
          change="-20s" 
          trend="down" 
          icon={Clock} 
          color="bg-blue-500" 
        />
        <StatsCard 
          title="Active Agents" 
          value="48/55" 
          icon={Users} 
          color="bg-emerald-500" 
        />
        <StatsCard 
          title="CSAT Score" 
          value="4.8" 
          change="+0.2" 
          trend="up" 
          icon={CheckCircle2} 
          color="bg-amber-500" 
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Chart */}
        <div className="lg:col-span-2 bg-white p-6 rounded-xl shadow-sm border border-slate-100">
          <div className="flex items-center justify-between mb-6">
            <h3 className="font-bold text-slate-800 flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-slate-400" />
              Call Volume
            </h3>
            <select className="text-sm border-slate-200 rounded-lg text-slate-600 focus:ring-emerald-500">
              <option>Today</option>
              <option>Yesterday</option>
            </select>
          </div>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={mockChartData}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                <XAxis dataKey="time" axisLine={false} tickLine={false} tick={{fill: '#64748b', fontSize: 12}} dy={10} />
                <YAxis axisLine={false} tickLine={false} tick={{fill: '#64748b', fontSize: 12}} />
                <Tooltip 
                  cursor={{fill: '#f8fafc'}}
                  contentStyle={{borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)'}}
                />
                <Bar dataKey="calls" fill="#059669" radius={[4, 4, 0, 0]} barSize={40} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Recent Activity */}
        <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-100">
          <h3 className="font-bold text-slate-800 mb-4 flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-slate-400" />
            Recent Calls
          </h3>
          <div className="space-y-4">
            {mockRecentCalls.map((call) => (
              <div key={call.id} className="flex items-center justify-between p-3 rounded-lg hover:bg-slate-50 transition-colors border border-transparent hover:border-slate-100">
                <div>
                  <p className="font-medium text-slate-800">{call.customer}</p>
                  <p className="text-xs text-slate-500">{call.topic} • {call.duration}</p>
                </div>
                <div className="text-right">
                  <span className={`inline-block px-2 py-1 rounded-full text-[10px] font-semibold ${
                    call.status === 'Resolved' ? 'bg-emerald-100 text-emerald-700' :
                    call.status === 'Escalated' ? 'bg-rose-100 text-rose-700' :
                    'bg-slate-100 text-slate-700'
                  }`}>
                    {call.status}
                  </span>
                  <p className="text-[10px] text-slate-400 mt-1">{call.time}</p>
                </div>
              </div>
            ))}
          </div>
          <button className="w-full mt-4 text-sm text-emerald-600 font-medium hover:text-emerald-800 py-2">
            View All Logs
          </button>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;