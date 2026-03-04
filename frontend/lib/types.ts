export type SignalRow = {
  id: number;
  fund_code: string;
  pred_return: number;
  pred_vol: number;
  confidence: number;
  signal: "ADD" | "REDUCE" | "CLEAR" | "HOLD";
  reason: string;
  risk_hint: string;
  created_at: string;
};

export type NewsRow = {
  id: number;
  title: string;
  summary: string;
  source: string;
  published_at: string;
  category: string;
};

export type DashboardData = {
  latest_signals: SignalRow[];
  prediction_history: SignalRow[];
  news: NewsRow[];
  hot_terms: { term: string; count: number }[];
};
