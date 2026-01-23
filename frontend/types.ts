
export enum CallStatus {
  IDLE = 'IDLE',
  RINGING = 'RINGING',
  ACTIVE = 'ACTIVE',
  HOLD = 'HOLD',
  ENDED = 'ENDED'
}

export interface Interaction {
  date: string;
  type: 'Call' | 'Bank Visit';
  reason: string;
  outcome: string;
}

export interface Customer {
  id: string;
  name: string;
  email: string;
  phone: string;
  address: string;
  dob: string;
  accountLevel: 'Standard' | 'Premium' | 'Enterprise';
  lastInteraction: string;
  sentiment: 'Positive' | 'Neutral' | 'Negative';
  issue: string;
  jointHolders?: string[];
  activePromotions?: string[];
  interactions?: Interaction[];
}

export interface Message {
  id: string;
  role: 'user' | 'model' | 'system';
  content: string;
  timestamp: Date;
  isThinking?: boolean;
}

export interface CallLog {
  id: string;
  time: string;
  duration: string;
  customer: string;
  topic: string;
  status: 'Resolved' | 'Escalated' | 'Pending';
}

export type ViewState = 'DASHBOARD' | 'ACTIVE_CALL';

export type ScenarioType = 'PROMOTION' | 'CLIENT_SUMMARY' | 'END_CALL';
