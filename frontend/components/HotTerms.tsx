export function HotTerms({ rows }: { rows: { term: string; count: number }[] }) {
  return (
    <div className="card">
      <h3>新闻热点词云(简化版)</h3>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
        {rows.slice(0, 40).map((x) => (
          <span
            key={x.term}
            style={{
              fontSize: `${12 + Math.min(x.count, 20)}px`,
              color: "#0f766e",
              border: "1px solid #99f6e4",
              borderRadius: 999,
              padding: "2px 8px",
              background: "#f0fdfa"
            }}
          >
            {x.term}({x.count})
          </span>
        ))}
        {rows.length === 0 ? <span className="muted">暂无热点词</span> : null}
      </div>
    </div>
  );
}

