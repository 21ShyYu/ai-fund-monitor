# `.env` 模板

## 1) worker/.env

```env
# SQLite/目录
DB_PATH=./worker/runtime/fund.db
MODEL_DIR=./worker/runtime/models
EXPORT_DIR=./data_exports
CONFIG_DIR=./shared/config

# 飞书
FEISHU_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxx

# LLM（DeepSeek/Qwen 二选一）
LLM_PROVIDER=deepseek
LLM_API_KEY=sk-xxxxxxxx
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
LLM_TIMEOUT_SEC=40

# 自动 push 到 GitHub（建议 true）
GIT_AUTO_PUSH=true
GITHUB_BRANCH=main
TZ=Asia/Shanghai
```

## 2) frontend/.env.local

```env
NEXTAUTH_URL=https://your-vercel-domain.vercel.app
NEXTAUTH_SECRET=replace_with_long_random_secret_64_chars
GITHUB_ID=Ov23xxxxxxxx
GITHUB_SECRET=xxxxxxxx
ADMIN_GITHUB_LOGIN=21ShyYu

# 管理端服务端写 GitHub 配置时使用
GITHUB_PAT=github_pat_xxxxxxxx
GITHUB_OWNER=21ShyYu
GITHUB_REPO=ai-fund-monitor
GITHUB_CONFIG_BRANCH=main

# 前端读取公开数据（raw github）
DATA_BASE_URL=https://raw.githubusercontent.com/21ShyYu/ai-fund-monitor/main/data_exports
```

## 3) 替换建议

1. `NEXTAUTH_SECRET` 可用以下命令生成：
```bash
openssl rand -base64 48
```
2. 不要把 `.env` 或 `.env.local` 提交到 GitHub。
3. 变量改完后，worker 重启任务，Vercel 点一次 Redeploy。
