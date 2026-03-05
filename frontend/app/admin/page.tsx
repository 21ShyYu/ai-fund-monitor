"use client";

import { useEffect, useMemo, useState } from "react";
import { signIn, useSession } from "next-auth/react";

type ConfigMap = Record<string, string>;

type FundItem = {
  code: string;
  name: string;
  enabled: boolean;
};

const FILE_FUNDS = "shared/config/funds.json";
const FILE_STRATEGY = "shared/config/strategy.json";
const FILE_NEWS = "shared/config/news_sources.json";

const emptyConfig: ConfigMap = {
  [FILE_FUNDS]: "[]",
  [FILE_STRATEGY]: "{}",
  [FILE_NEWS]: "{ \"sources\": [] }"
};

const emptyFund: FundItem = { code: "", name: "", enabled: true };

export default function AdminPage() {
  const { data: session, status } = useSession();
  const [cfg, setCfg] = useState<ConfigMap>(emptyConfig);
  const [funds, setFunds] = useState<FundItem[]>([]);
  const [draftFund, setDraftFund] = useState<FundItem>(emptyFund);
  const [msg, setMsg] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(true);
  const [advancedMode, setAdvancedMode] = useState<boolean>(false);

  useEffect(() => {
    if (status !== "authenticated") return;
    (async () => {
      const resp = await fetch("/api/admin/config", { cache: "no-store" });
      if (!resp.ok) {
        setMsg("无权限或读取失败。");
        setLoading(false);
        return;
      }
      const data = (await resp.json()) as ConfigMap;
      setCfg(data);
      setFunds(parseFunds(data[FILE_FUNDS]));
      setLoading(false);
    })();
  }, [status]);

  const strategyText = useMemo(() => cfg[FILE_STRATEGY] ?? "{}", [cfg]);
  const newsText = useMemo(() => cfg[FILE_NEWS] ?? '{ "sources": [] }', [cfg]);

  if (status === "loading") return <main className="card">加载中...</main>;
  if (!session) {
    return (
      <main className="card">
        <h2>管理员配置</h2>
        <p>请先登录 GitHub。</p>
        <button onClick={() => signIn("github")}>登录</button>
      </main>
    );
  }

  if (loading) return <main className="card">正在读取配置...</main>;

  async function save() {
    setMsg("保存中...");

    const nextCfg = { ...cfg };
    nextCfg[FILE_FUNDS] = JSON.stringify(funds, null, 2);
    nextCfg[FILE_STRATEGY] = strategyText;
    nextCfg[FILE_NEWS] = newsText;

    for (const key of Object.keys(nextCfg)) {
      try {
        JSON.parse(nextCfg[key]);
      } catch {
        setMsg(`${key} 不是有效JSON`);
        return;
      }
    }

    const resp = await fetch("/api/admin/config", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(nextCfg)
    });
    if (resp.ok) {
      setCfg(nextCfg);
      setMsg("保存成功，worker 下一次运行会自动生效。");
    } else {
      setMsg("保存失败，请检查 Vercel 环境变量和 GitHub PAT 权限。");
    }
  }

  function addFund() {
    const code = draftFund.code.trim();
    const name = draftFund.name.trim();
    if (!/^\d{6}$/.test(code)) {
      setMsg("基金代码需为6位数字。");
      return;
    }
    if (!name) {
      setMsg("基金名称不能为空。");
      return;
    }
    if (funds.some((x) => x.code === code)) {
      setMsg(`基金代码 ${code} 已存在。`);
      return;
    }
    setFunds([...funds, { code, name, enabled: draftFund.enabled }]);
    setDraftFund(emptyFund);
    setMsg("");
  }

  function updateFund(index: number, patch: Partial<FundItem>) {
    setFunds(funds.map((x, i) => (i === index ? { ...x, ...patch } : x)));
  }

  function removeFund(index: number) {
    setFunds(funds.filter((_, i) => i !== index));
  }

  return (
    <main className="card">
      <h2>管理员配置中心</h2>
      <p className="muted">当前登录: {(session as any).githubLogin || session.user?.name}</p>

      <div style={{ margin: "12px 0 18px 0", display: "flex", gap: 8 }}>
        <button onClick={() => setAdvancedMode(!advancedMode)}>
          {advancedMode ? "隐藏高级JSON编辑" : "显示高级JSON编辑"}
        </button>
        <button onClick={save}>保存到 GitHub</button>
      </div>

      <section style={{ marginBottom: 18 }}>
        <h3>自选基金（可视化编辑）</h3>
        <p className="muted">直接在这里增删改，不需要手改 funds.json。</p>

        <table>
          <thead>
            <tr>
              <th>基金代码</th>
              <th>基金名称</th>
              <th>启用</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {funds.map((f, idx) => (
              <tr key={`${f.code}-${idx}`}>
                <td>
                  <input
                    value={f.code}
                    onChange={(e) => updateFund(idx, { code: e.target.value.trim() })}
                    style={{ width: 120 }}
                  />
                </td>
                <td>
                  <input
                    value={f.name}
                    onChange={(e) => updateFund(idx, { name: e.target.value })}
                    style={{ width: "100%" }}
                  />
                </td>
                <td>
                  <input
                    type="checkbox"
                    checked={f.enabled}
                    onChange={(e) => updateFund(idx, { enabled: e.target.checked })}
                  />
                </td>
                <td>
                  <button onClick={() => removeFund(idx)}>删除</button>
                </td>
              </tr>
            ))}
            {funds.length === 0 ? (
              <tr>
                <td colSpan={4} className="muted">
                  当前没有基金，请先添加。
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>

        <div style={{ marginTop: 12, display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <input
            placeholder="基金代码(6位)"
            value={draftFund.code}
            onChange={(e) => setDraftFund({ ...draftFund, code: e.target.value })}
            style={{ width: 140 }}
          />
          <input
            placeholder="基金名称"
            value={draftFund.name}
            onChange={(e) => setDraftFund({ ...draftFund, name: e.target.value })}
            style={{ minWidth: 260 }}
          />
          <label style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            <input
              type="checkbox"
              checked={draftFund.enabled}
              onChange={(e) => setDraftFund({ ...draftFund, enabled: e.target.checked })}
            />
            启用
          </label>
          <button onClick={addFund}>新增基金</button>
        </div>
      </section>

      {advancedMode ? (
        <section>
          <h3>高级JSON编辑（可选）</h3>
          <p className="muted">仅在你需要调整策略和新闻源时使用。</p>
          <div style={{ marginBottom: 12 }}>
            <h4>{FILE_STRATEGY}</h4>
            <textarea
              value={strategyText}
              onChange={(e) => setCfg({ ...cfg, [FILE_STRATEGY]: e.target.value })}
            />
          </div>
          <div>
            <h4>{FILE_NEWS}</h4>
            <textarea
              value={newsText}
              onChange={(e) => setCfg({ ...cfg, [FILE_NEWS]: e.target.value })}
            />
          </div>
        </section>
      ) : null}

      <p style={{ marginTop: 14 }}>{msg}</p>
    </main>
  );
}

function parseFunds(raw: string | undefined): FundItem[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed
      .map((x) => {
        if (!x || typeof x !== "object") return null;
        const item = x as Record<string, unknown>;
        return {
          code: String(item.code ?? "").trim(),
          name: String(item.name ?? "").trim(),
          enabled: Boolean(item.enabled ?? true)
        };
      })
      .filter((x): x is FundItem => Boolean(x?.code));
  } catch {
    return [];
  }
}
