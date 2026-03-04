"use client";

import { useEffect, useState } from "react";
import { signIn, useSession } from "next-auth/react";

type ConfigMap = Record<string, string>;

const emptyConfig: ConfigMap = {
  "shared/config/funds.json": "[]",
  "shared/config/strategy.json": "{}",
  "shared/config/news_sources.json": "{}"
};

export default function AdminPage() {
  const { data: session, status } = useSession();
  const [cfg, setCfg] = useState<ConfigMap>(emptyConfig);
  const [msg, setMsg] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(true);

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
      setLoading(false);
    })();
  }, [status]);

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
    for (const key of Object.keys(cfg)) {
      try {
        JSON.parse(cfg[key]);
      } catch {
        setMsg(`${key} 不是有效JSON`);
        return;
      }
    }
    const resp = await fetch("/api/admin/config", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cfg)
    });
    setMsg(resp.ok ? "保存成功。" : "保存失败，请检查权限和环境变量。");
  }

  return (
    <main className="card">
      <h2>管理员配置中心</h2>
      <p className="muted">当前登录: {(session as any).githubLogin || session.user?.name}</p>
      {Object.keys(cfg).map((key) => (
        <div key={key} style={{ marginBottom: 16 }}>
          <h4>{key}</h4>
          <textarea value={cfg[key]} onChange={(e) => setCfg({ ...cfg, [key]: e.target.value })} />
        </div>
      ))}
      <button onClick={save}>保存到 GitHub</button>
      <p>{msg}</p>
    </main>
  );
}

