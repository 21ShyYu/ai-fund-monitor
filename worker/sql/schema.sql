CREATE TABLE IF NOT EXISTS fund_prices (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  fund_code TEXT NOT NULL,
  fund_name TEXT NOT NULL,
  nav REAL NOT NULL,
  daily_change_pct REAL NOT NULL,
  observed_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fund_prices_code_time
ON fund_prices (fund_code, observed_at);

CREATE TABLE IF NOT EXISTS news_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  summary TEXT NOT NULL,
  source TEXT NOT NULL,
  published_at TEXT NOT NULL,
  category TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_news_items_time
ON news_items (published_at);

CREATE TABLE IF NOT EXISTS predictions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  fund_code TEXT NOT NULL,
  pred_return REAL NOT NULL,
  pred_vol REAL NOT NULL,
  confidence REAL NOT NULL,
  signal TEXT NOT NULL,
  reason TEXT NOT NULL,
  risk_hint TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_predictions_code_time
ON predictions (fund_code, created_at);

CREATE TABLE IF NOT EXISTS job_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_name TEXT NOT NULL,
  status TEXT NOT NULL,
  detail TEXT NOT NULL,
  created_at TEXT NOT NULL
);
