"use client";

import { signIn, signOut, useSession } from "next-auth/react";

export default function LoginPage() {
  const { data: session } = useSession();
  return (
    <main className="card">
      <h2>管理员登录</h2>
      <p className="muted">使用 GitHub OAuth 登录。</p>
      {session ? (
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <span>当前用户: {(session as any).githubLogin || session.user?.name}</span>
          <button onClick={() => signOut()}>退出</button>
        </div>
      ) : (
        <button onClick={() => signIn("github")}>GitHub 登录</button>
      )}
    </main>
  );
}

