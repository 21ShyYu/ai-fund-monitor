# AI Fund Monitor

低预算、可自动化的基金监控与预测系统模板：
- `worker/`: Ubuntu 上的定时任务（抓数、推理、风控、LLM总结、飞书推送、导出JSON）
- `frontend/`: Vercel 公开展示站点 + GitHub OAuth 管理页
- `shared/config/`: 自选基金与策略参数配置
- `data_exports/`: 前端展示数据（由 worker 自动更新）

## 1. 核心能力

- 每天 `14:00` / `22:00` 自动执行
- 输出 `加仓/减仓/清仓/观望`
- 强制包含：置信度、风险提示、最大回撤控制
- 新闻只存：标题、摘要、来源、时间
- 模型可替换（本地训练 -> 服务器推理）
- LLM 可切换（DeepSeek/Qwen/OpenAI 兼容端点）

## 2. 快速开始

### 2.1 初始化配置

1. 复制配置模板并按实际填写：

```bash
cp worker/.env.example worker/.env
cp frontend/.env.example frontend/.env.local
```

2. 修改 `shared/config/`:
- `funds.json` 自选基金
- `strategy.json` 风控和触发阈值
- `news_sources.json` 新闻源

### 2.2 本地运行 worker

```bash
cd worker
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/init_db.py
python scripts/run_once.py
```

### 2.3 本地运行 frontend

```bash
cd frontend
npm install
npm run dev
```

## 3. Ubuntu 部署（worker）

参考 `worker/deploy/install_ubuntu.sh` 与 `worker/deploy/cron.example`。

高层步骤：
1. 安装 Python 3.11、venv、git
2. 拉取仓库并创建 `.env`
3. 初始化数据库 `python scripts/init_db.py`
4. 配置 `cron` 两个任务（14:00、22:00）
5. 验证日志与飞书通知

## 4. Vercel 部署（frontend）

1. 将 `frontend/` 关联 Vercel 项目
2. 在 Vercel 环境变量配置：
- `NEXTAUTH_URL`
- `NEXTAUTH_SECRET`
- `GITHUB_ID`
- `GITHUB_SECRET`
- `GITHUB_PAT`（仅服务端使用）
- `GITHUB_OWNER`
- `GITHUB_REPO`
- `GITHUB_CONFIG_BRANCH`
- `DATA_BASE_URL`

3. 管理页路径：`/admin`
4. GitHub OAuth 登录后可更新配置文件（`shared/config/*.json`）

## 5. 安全原则

- API Key 只放 `worker/.env` 与 Vercel 服务端环境变量
- 前端不暴露任何敏感密钥
- `data_exports/` 只放脱敏结果
- 管理接口做 GitHub OAuth 会话校验

## 6. 数据流

1. 拉取配置
2. 抓基金行情与新闻
3. 模型推理
4. 风控决策
5. LLM总结
6. 写库
7. 飞书推送
8. 导出 `data_exports/*.json`

## 7. 后续建议

1. 训练并上传完整模型文件到 `worker/runtime/models/<fund_code>/`
2. 将新闻抓取从 RSS 扩展到站点解析器
3. 增加回测模块（按 T+1 口径）
