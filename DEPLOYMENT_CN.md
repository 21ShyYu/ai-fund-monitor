# AI基金系统部署手册（新手保姆级）

适用仓库：`https://github.com/21ShyYu/ai-fund-monitor.git`

目标：
1. 阿里云 Ubuntu 负责自动任务（抓数据、推理、风控、飞书推送、导出结果）
2. Vercel 负责公开前端展示
3. 管理员通过 GitHub OAuth 登录后修改配置
4. 系统严格模式：不允许模拟数据，不允许回退分析。任一环节失败必须给出错误提示

---

## 0. 你要先准备好什么

1. 一个 GitHub 账号（你已有）
2. 一个 Vercel 账号（可直接绑定 GitHub 登录）
3. 一台 Ubuntu 服务器（你已有阿里云）
4. 飞书群机器人 Webhook
5. LLM API Key（DeepSeek 或 Qwen）

---

## 1. 本地初始化并推送到 GitHub

在项目目录执行（Windows PowerShell）：

```powershell
cd "C:\Users\SHY\Desktop\Coding\AI基金预测系统"
git init
git branch -M main
git remote add origin https://github.com/21ShyYu/ai-fund-monitor.git
git add .
git commit -m "feat: initial ai fund monitor scaffold"
git push -u origin main
```

如果 `git push` 要求登录：
1. 浏览器会弹 GitHub 授权，按提示登录
2. 或使用 PAT 作为密码（见下文第 2 节）

---

## 2. 生成 GitHub PAT（超详细）

用途：给前端管理员 API 写配置文件用（服务端使用，不会暴露给前端用户）。

步骤：
1. 打开 GitHub 网页，右上角头像 -> `Settings`
2. 左侧到底部：`Developer settings`
3. 进入 `Personal access tokens`
4. 推荐选 `Tokens (classic)`（简单直接）
5. 点击 `Generate new token (classic)`
6. Note 填：`ai-fund-monitor-vercel`
7. Expiration 选：`90 days` 或更长（建议先 90 天）
8. 勾选权限：`repo`（至少要有）
9. 点击底部 `Generate token`
10. 复制 token（只显示一次），保存到密码管理器

测试这个 PAT（可选）：
```bash
curl -H "Authorization: Bearer <你的PAT>" https://api.github.com/user
```
返回你的用户信息即成功。

---

## 3. 创建 GitHub OAuth App（用于管理员登录）

步骤：
1. GitHub -> `Settings` -> `Developer settings` -> `OAuth Apps`
2. 点击 `New OAuth App`
3. 填写：
- Application name: `ai-fund-monitor-admin`
- Homepage URL: `https://你的vercel域名`
- Authorization callback URL: `https://你的vercel域名/api/auth/callback/github`
4. 创建后得到：
- `Client ID`
- `Client Secret`（点 Generate）

这两个值后面填到 Vercel 环境变量里。

---

## 4. 部署前端到 Vercel（公开网站）

1. 登录 Vercel
2. 点击 `Add New Project`
3. 导入仓库：`21ShyYu/ai-fund-monitor`
4. 在设置中指定 `Root Directory` 为 `frontend`
5. Build 命令默认即可（`next build`）
6. 在 Environment Variables 填以下变量：

`NEXTAUTH_URL=https://你的vercel域名`

`NEXTAUTH_SECRET=你自己生成的长随机字符串`

`GITHUB_ID=第3节的Client ID`

`GITHUB_SECRET=第3节的Client Secret`

`ADMIN_GITHUB_LOGIN=你的GitHub用户名(例如 21ShyYu)`

`GITHUB_PAT=第2节生成的PAT`

`GITHUB_OWNER=21ShyYu`

`GITHUB_REPO=ai-fund-monitor`

`GITHUB_CONFIG_BRANCH=main`

`DATA_BASE_URL=https://raw.githubusercontent.com/21ShyYu/ai-fund-monitor/main/data_exports`

7. 点击 Deploy
8. 访问：
- `/` 公开看板
- `/login` 登录
- `/admin` 管理员配置页（仅 ADMIN_GITHUB_LOGIN 对应账户可用）

---

## 5. Ubuntu 部署 worker（自动任务）

以下在服务器执行：

### 5.1 安装基础环境

```bash
sudo apt update
sudo apt install -y git python3-venv python3-pip
```

### 5.2 拉代码

```bash
cd ~
git clone https://github.com/21ShyYu/ai-fund-monitor.git
cd ai-fund-monitor
```

### 5.3 配置 .env

```bash
cp worker/.env.example worker/.env
nano worker/.env
```

最少要改：
1. `FEISHU_WEBHOOK=...`
2. `LLM_API_KEY=...`
3. `LLM_BASE_URL=...`（DeepSeek/Qwen OpenAI兼容地址）
4. `LLM_MODEL=...`
5. `GIT_AUTO_PUSH=true`
6. `GITHUB_BRANCH=main`

### 5.4 创建虚拟环境并安装依赖

```bash
cd worker
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 5.5 初始化数据库并手动跑一次

```bash
python scripts/init_db.py
python scripts/run_once.py
```

### 5.6 检查结果

1. 看日志文件（若已配置 cron）：`worker/runtime/cron.log`
2. 看数据库里是否有数据（可选安装 sqlite3）：
```bash
sqlite3 worker/runtime/fund.db "select count(*) from predictions;"
sqlite3 worker/runtime/fund.db "select * from job_logs order by id desc limit 20;"
```
3. 看 GitHub 仓库 `data_exports/dashboard.json` 是否更新
4. 看飞书是否收到日报

---

## 6. 配置定时任务 cron（14:00/22:00）

```bash
crontab -e
```

粘贴（把路径替换成你服务器真实路径）：

```cron
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
CRON_TZ=Asia/Shanghai

0 14 * * * cd /home/ubuntu/ai-fund-monitor/worker && . .venv/bin/activate && python scripts/run_once.py >> /home/ubuntu/ai-fund-monitor/worker/runtime/cron.log 2>&1
0 22 * * * cd /home/ubuntu/ai-fund-monitor/worker && . .venv/bin/activate && python scripts/run_once.py >> /home/ubuntu/ai-fund-monitor/worker/runtime/cron.log 2>&1
```

保存退出后验证：
```bash
crontab -l
```

---

## 7. 模型文件放置规则（严格）

系统不会使用模拟预测。没有模型文件就会报错并记录。

你必须上传：

1. `worker/runtime/models/<fund_code>/xgboost.joblib`
2. `worker/runtime/models/<fund_code>/vol.joblib`

示例：
```bash
worker/runtime/models/161725/xgboost.joblib
worker/runtime/models/161725/vol.joblib
```

---

## 8. 严格模式说明（你要求的）

已实现规则：
1. 行情抓取失败：记录 `job_logs`，飞书提示错误
2. 新闻源空数据/解析异常：记录警告/失败，不造数据
3. 模型文件缺失或加载失败：该基金不生成预测并报错
4. LLM失败或未配置：明确提示“未生成”，不输出伪总结
5. 当轮没有有效预测：飞书显示“无有效预测”并附异常清单

---

## 9. 常见问题排查

1. 飞书没有消息
- 检查 `FEISHU_WEBHOOK`
- 检查 `job_logs` 表
- 检查 `cron.log`

2. 前端没有数据
- worker 是否 push 了 `data_exports/dashboard.json`
- `DATA_BASE_URL` 是否正确
- Vercel 是否重新部署

3. 管理页 401
- `ADMIN_GITHUB_LOGIN` 是否填成你的 GitHub login（不是昵称）
- OAuth 回调 URL 是否精确匹配

4. 全部基金都预测失败
- 检查模型路径是否与 `funds.json` 基金代码一致
- 检查模型文件名是否严格是 `xgboost.joblib` 和 `vol.joblib`

---

## 10. 上线后每周例行

1. 看 `job_logs` 错误率
2. 检查新闻源可用性（公开源可能调整）
3. 按 T+1 口径复盘准确率与回撤
4. 必要时调整 `shared/config/strategy.json` 阈值
