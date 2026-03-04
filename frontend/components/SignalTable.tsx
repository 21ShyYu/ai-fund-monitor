import type { SignalRow } from "../lib/types";

const signalLabel: Record<string, string> = {
  ADD: "加仓",
  REDUCE: "减仓",
  CLEAR: "清仓",
  HOLD: "观望"
};

export function SignalTable({ rows }: { rows: SignalRow[] }) {
  return (
    <div className="card">
      <h3>今日建议</h3>
      <table>
        <thead>
          <tr>
            <th>基金</th>
            <th>建议</th>
            <th>置信度</th>
            <th>预测收益(%)</th>
            <th>风险提示</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((x) => (
            <tr key={`${x.fund_code}-${x.created_at}`}>
              <td>{x.fund_code}</td>
              <td>
                <span className={`badge ${x.signal}`}>{signalLabel[x.signal] || x.signal}</span>
              </td>
              <td>{x.confidence}</td>
              <td>{(x.pred_return * 100).toFixed(2)}</td>
              <td>{x.risk_hint}</td>
            </tr>
          ))}
          {rows.length === 0 ? (
            <tr>
              <td colSpan={5} className="muted">
                暂无数据
              </td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </div>
  );
}

