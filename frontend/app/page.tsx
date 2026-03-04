import Link from "next/link";
import { HotTerms } from "../components/HotTerms";
import { SignalTable } from "../components/SignalTable";
import type { DashboardData } from "../lib/types";

export const revalidate = 1800;

const defaultData: DashboardData = {
  latest_signals: [],
  prediction_history: [],
  news: [],
  hot_terms: []
};

async function fetchDashboard(): Promise<DashboardData> {
  const base =
    process.env.DATA_BASE_URL ||
    "https://raw.githubusercontent.com/OWNER/REPO/main/data_exports";
  const normalizedBase = base.endsWith("/") ? base.slice(0, -1) : base;
  const url = `${normalizedBase}/dashboard.json`;
  try {
    const resp = await fetch(url, { next: { revalidate: 1800 } });
    if (!resp.ok) return defaultData;
    return (await resp.json()) as DashboardData;
  } catch {
    return defaultData;
  }
}

export default async function Page() {
  const data = await fetchDashboard();
  return (
    <main>
      <div className="card" style={{ marginBottom: 16 }}>
        <h1>AI基金监控看板</h1>
        <p className="muted">30分钟刷新一次，建议仅供参考，不构成投资建议。</p>
        <div style={{ display: "flex", gap: 12 }}>
          <Link href="/admin">管理员</Link>
          <Link href="/login">登录</Link>
        </div>
      </div>

      <div className="row">
        <SignalTable rows={data.latest_signals} />
        <HotTerms rows={data.hot_terms} />
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <h3>新闻摘要</h3>
        <table>
          <thead>
            <tr>
              <th>时间</th>
              <th>来源</th>
              <th>标题</th>
              <th>摘要</th>
            </tr>
          </thead>
          <tbody>
            {data.news.slice(0, 80).map((x) => (
              <tr key={`${x.source}-${x.published_at}-${x.title.slice(0, 16)}`}>
                <td>{x.published_at}</td>
                <td>{x.source}</td>
                <td>{x.title}</td>
                <td>{x.summary.slice(0, 120)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
