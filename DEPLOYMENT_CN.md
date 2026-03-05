# AI基金系统部署指南（新手保姆级）

仓库地址：`https://github.com/21ShyYu/ai-fund-monitor.git`

本文目标：你按步骤执行后，可以得到一个完整可用系统：
1. 阿里云 Ubuntu：自动抓数据 + 模型推理 + 风控 + 飞书推送 + 导出前端数据
2. Vercel：公开可视化页面
3. GitHub OAuth：管理员登录
4. 管理页：在线编辑基金配置/策略配置/新闻源配置
5. 严格模式：不允许模拟数据；失败时必须给出明确错误

---

## 1. 系统结构（先看懂）

1. `worker/` 在 Ubuntu 上运行（定时任务）
2. `frontend/` 部署到 Vercel（公开访问）
3. `shared/config/` 存放配置（基金池、策略、新闻源）
4. `data_exports/dashboard.json` 给前端展示

数据流：
1. worker 读取 `shared/config/*.json`
2. 拉取基金与新闻真实数据
3. 加载你训练好的模型进行预测
4. 根据风险规则生成信号（加仓/减仓/清仓/观望）
5. 调 LLM 生成总结
6. 发飞书
7. 更新 `data_exports/dashboard.json`
8. 前端每30分钟读取最新 `dashboard.json`

---

## 2. 第一步：本地推送代码到 GitHub

在你电脑 PowerShell 里执行（逐条执行）：

```powershell
cd "C:\Users\SHY\Desktop\Coding\AI基金预测系统"
git init
git branch -M main
git remote remove origin
git remote add origin https://github.com/21ShyYu/ai-fund-monitor.git
git add .
git commit -m "feat: initial deployable version"
git push -u origin main
```

说明：
1. 如果提示 `nothing to commit`，跳过 commit 即可。
2. 如果 push 要求登录，按浏览器登录 GitHub 或使用 PAT（见第3节）。

---

## 3. 第二步：生成 GitHub PAT（非常详细）

用途：
1. 前端管理员 API 需要写回 GitHub 配置文件
2. PAT 只在服务端环境变量中使用，不暴露给前端用户

操作步骤：
1. 打开 GitHub 网站，右上角头像 -> `Settings`
2. 左侧最下方 -> `Developer settings`
3. 点击 `Personal access tokens`
4. 点击 `Tokens (classic)`（新手建议）
5. 点击 `Generate new token` -> `Generate new token (classic)`
6. `Note` 填：`ai-fund-monitor-admin`
7. `Expiration` 建议先选 `90 days`
8. 勾选权限：`repo`（必须）
9. 点击底部 `Generate token`
10. 复制 token（只显示一次），先记到安全位置

你后面会把这个 token 填到：
1. `frontend` 的 `GITHUB_PAT`

---

## 4. 第三步：创建 GitHub OAuth（管理员登录）

用途：
1. `/login` 和 `/admin` 使用 GitHub 登录
2. 只有你自己的 GitHub 账号能进入管理页

操作步骤：
1. GitHub -> `Settings` -> `Developer settings` -> `OAuth Apps`
2. 点击 `New OAuth App`
3. 填写：
- `Application name`: `ai-fund-monitor-admin`
- `Homepage URL`: `https://iyushy.site`
- `Authorization callback URL`: `https://iyushy.site/api/auth/callback/github`
4. 点击 `Register application`
5. 复制 `Client ID`
6. 点击 `Generate a new client secret`，复制 `Client Secret`

这两个值稍后用于 Vercel 环境变量：
1. `GITHUB_ID`
2. `GITHUB_SECRET`

---

## 5. 第四步：部署前端到 Vercel（公开页面）

### 5.1 导入仓库
1. 登录 Vercel
2. `Add New...` -> `Project`
3. 选择仓库 `21ShyYu/ai-fund-monitor`
4. 设置 `Root Directory` 为 `frontend`
5. 其余保持默认

### 5.2 配置环境变量（最关键）

在 Vercel 项目 -> `Settings` -> `Environment Variables` 添加：

```env
NEXTAUTH_URL=https://iyushy.site
NEXTAUTH_SECRET=你生成的一串随机长字符串
GITHUB_ID=GitHub OAuth Client ID
GITHUB_SECRET=GitHub OAuth Client Secret
ADMIN_GITHUB_LOGIN=21ShyYu
GITHUB_PAT=你第3节生成的PAT
GITHUB_OWNER=21ShyYu
GITHUB_REPO=ai-fund-monitor
GITHUB_CONFIG_BRANCH=main
DATA_BASE_URL=https://raw.githubusercontent.com/21ShyYu/ai-fund-monitor/main/data_exports
```

### 5.3 触发部署
1. 回到 `Deployments`
2. 点 `Redeploy`
3. 成功后访问：
- `https://iyushy.site/`（公开看板）
- `https://iyushy.site/login`
- `https://iyushy.site/admin`

---

## 6. 第五步：阿里云 Ubuntu 部署 worker

### 6.1 登录服务器并安装依赖

```bash
sudo apt update
sudo apt install -y git python3-venv python3-pip
```

### 6.2 拉取仓库

```bash
cd ~
git clone https://github.com/21ShyYu/ai-fund-monitor.git
cd ai-fund-monitor
```

### 6.3 创建并编辑 worker 环境变量

```bash
cp worker/.env.example worker/.env
nano worker/.env
```

按你自己的真实信息填写：

```env
DB_PATH=./worker/runtime/fund.db
MODEL_DIR=./worker/runtime/models
EXPORT_DIR=./data_exports
CONFIG_DIR=./shared/config

FEISHU_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxx

LLM_PROVIDER=deepseek
LLM_API_KEY=sk-xxxxxxxx
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
LLM_TIMEOUT_SEC=40

GIT_AUTO_PUSH=true
GITHUB_BRANCH=main
TZ=Asia/Shanghai
```

### 6.4 建虚拟环境并安装 Python 依赖

```bash
cd worker
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 6.5 初始化数据库 + 手工运行一次

```bash
python scripts/init_db.py
python scripts/run_once.py

cd /root/ai-fund-monitor/worker
python -m scripts.run_once
```

这一步必须观察输出：
1. 有无报错（模型缺失、新闻抓取失败、LLM失败都会提示）
2. 飞书是否收到消息
3. 仓库中 `data_exports/dashboard.json` 是否更新

---

## 7. 第六步：上传你的模型文件（严格必需）

系统不允许使用模拟预测。没有模型就会报错，不会生成预测。

每个基金需要两个文件：
1. `xgboost.joblib`
2. `vol.joblib`

目录格式必须是：

```text
worker/runtime/models/<fund_code>/xgboost.joblib
worker/runtime/models/<fund_code>/vol.joblib
```

例如：

```text
worker/runtime/models/161725/xgboost.joblib
worker/runtime/models/161725/vol.joblib
```

---

## 8. 第七步：设置定时任务（14:00 和 22:00）

### 8.1 打开 crontab

```bash
crontab -e
```

### 8.2 粘贴以下内容（把路径改成你的真实路径）

```cron
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
CRON_TZ=Asia/Shanghai

0 14 * * * cd /home/ubuntu/ai-fund-monitor/worker && . .venv/bin/activate && python scripts/run_once.py >> /home/ubuntu/ai-fund-monitor/worker/runtime/cron.log 2>&1
0 22 * * * cd /home/ubuntu/ai-fund-monitor/worker && . .venv/bin/activate && python scripts/run_once.py >> /home/ubuntu/ai-fund-monitor/worker/runtime/cron.log 2>&1
```

### 8.3 保存后检查

```bash
crontab -l
```

---

## 9. 第八步：管理页使用方法

1. 打开 `/login` 用 GitHub 登录
2. 打开 `/admin`
3. 页面会展示3份配置 JSON：
- `shared/config/funds.json`
- `shared/config/strategy.json`
- `shared/config/news_sources.json`
4. 改完后点“保存到 GitHub”
5. 下一次 worker 运行会读取新配置

---

## 10. 严格模式说明（你特别要求）

已实现：
1. 行情源异常：记录错误，不造行情
2. 新闻源异常：记录错误，不造新闻
3. 模型文件缺失：该基金直接失败并提示
4. LLM不可用：明确提示“LLM总结未生成”
5. 整轮无有效预测：飞书提示“本轮未生成有效预测”

错误位置：
1. 飞书消息里 `异常提示` 段
2. SQLite 的 `job_logs` 表
3. `worker/runtime/cron.log`

---

## 11. 常见报错和处理

1. `Missing return model file`
- 说明某基金缺 `xgboost.joblib`
- 检查路径和基金代码目录名是否一致

2. `Fund source returned unexpected payload`
- 行情源返回格式变化或临时不可用
- 先重试，必要时更换行情源接口实现

3. `LLM request failed`
- API Key错 / 余额不足 / 模型名错误 / 网络问题
- 检查 `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL`

4. `/admin` 返回 401
- `ADMIN_GITHUB_LOGIN` 填错
- OAuth 回调 URL 不匹配

5. 前端没数据
- worker 没跑成功
- `GIT_AUTO_PUSH` 不是 true
- `DATA_BASE_URL` 配错

---

## 12. 上线后每周维护清单

1. 检查 `job_logs` 失败率
2. 检查新闻源是否稳定
3. 复盘 T+1 准确率、最大回撤
4. 按复盘调整 `strategy.json` 阈值
5. 定期更换 GitHub PAT 和 LLM Key
