import { getServerSession } from "next-auth";
import { authOptions } from "../../../../lib/auth";

export const runtime = "nodejs";

const files = [
  "shared/config/funds.json",
  "shared/config/strategy.json",
  "shared/config/news_sources.json"
];

export async function GET() {
  const auth = await ensureAdmin();
  if (!auth.ok) return auth.response;

  const result: Record<string, string> = {};
  for (const path of files) {
    result[path] = await getFileFromGitHub(path);
  }
  return Response.json(result);
}

export async function PUT(req: Request) {
  const auth = await ensureAdmin();
  if (!auth.ok) return auth.response;

  const body = (await req.json()) as Record<string, string>;
  for (const path of files) {
    if (!(path in body)) {
      return Response.json({ error: `missing ${path}` }, { status: 400 });
    }
    await putFileToGitHub(path, body[path]);
  }
  return Response.json({ ok: true });
}

async function ensureAdmin(): Promise<{ ok: true } | { ok: false; response: Response }> {
  const session = await getServerSession(authOptions);
  const login = (session as any)?.githubLogin;
  const admin = process.env.ADMIN_GITHUB_LOGIN;
  if (!session || !login || !admin || login !== admin) {
    return { ok: false, response: Response.json({ error: "unauthorized" }, { status: 401 }) };
  }
  return { ok: true };
}

async function getFileFromGitHub(path: string): Promise<string> {
  const owner = mustEnv("GITHUB_OWNER");
  const repo = mustEnv("GITHUB_REPO");
  const branch = process.env.GITHUB_CONFIG_BRANCH || "main";
  const token = mustEnv("GITHUB_PAT");
  const url = `https://api.github.com/repos/${owner}/${repo}/contents/${path}?ref=${branch}`;
  const resp = await fetch(url, {
    headers: { Authorization: `Bearer ${token}`, Accept: "application/vnd.github+json" },
    cache: "no-store"
  });
  if (!resp.ok) throw new Error(`get file failed: ${path}`);
  const data = (await resp.json()) as { content: string; encoding: string };
  const raw = data.encoding === "base64" ? Buffer.from(data.content, "base64").toString("utf8") : "";
  return raw;
}

async function putFileToGitHub(path: string, content: string): Promise<void> {
  const owner = mustEnv("GITHUB_OWNER");
  const repo = mustEnv("GITHUB_REPO");
  const branch = process.env.GITHUB_CONFIG_BRANCH || "main";
  const token = mustEnv("GITHUB_PAT");
  const getUrl = `https://api.github.com/repos/${owner}/${repo}/contents/${path}?ref=${branch}`;
  const getResp = await fetch(getUrl, {
    headers: { Authorization: `Bearer ${token}`, Accept: "application/vnd.github+json" },
    cache: "no-store"
  });
  if (!getResp.ok) throw new Error(`read before update failed: ${path}`);
  const old = (await getResp.json()) as { sha: string };

  const putUrl = `https://api.github.com/repos/${owner}/${repo}/contents/${path}`;
  const putResp = await fetch(putUrl, {
    method: "PUT",
    headers: { Authorization: `Bearer ${token}`, Accept: "application/vnd.github+json" },
    body: JSON.stringify({
      message: `chore: update ${path}`,
      branch,
      sha: old.sha,
      content: Buffer.from(content, "utf8").toString("base64")
    })
  });
  if (!putResp.ok) throw new Error(`update failed: ${path}`);
}

function mustEnv(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`missing env: ${name}`);
  return value;
}
