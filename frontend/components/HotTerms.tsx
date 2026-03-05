export function HotTerms({ rows }: { rows: { term: string; count: number }[] }) {
  const top = rows.slice(0, 45);
  const max = top.length ? top[0].count : 1;

  return (
    <div className="card">
      <h3>?????</h3>
      <div className="hot-cloud">
        {top.map((x) => {
          const ratio = max <= 0 ? 0 : x.count / max;
          const fontSize = 12 + Math.round(18 * ratio);
          const hue = 178 + ((hashTerm(x.term) % 5) - 2) * 9;
          return (
            <span
              key={x.term}
              className="hot-pill"
              style={{
                fontSize: `${fontSize}px`,
                background: `linear-gradient(135deg, hsl(${hue} 82% 95%), hsl(${hue + 10} 78% 90%))`,
                borderColor: `hsl(${hue} 62% 78%)`,
                boxShadow: `0 2px 8px hsla(${hue}, 70%, 40%, 0.14)`
              }}
            >
              <b>{x.term}</b>
              <em>{x.count}</em>
            </span>
          );
        })}
        {rows.length === 0 ? <span className="muted">????</span> : null}
      </div>
    </div>
  );
}

function hashTerm(term: string): number {
  let hash = 0;
  for (let i = 0; i < term.length; i += 1) {
    hash = (hash * 31 + term.charCodeAt(i)) >>> 0;
  }
  return hash;
}
