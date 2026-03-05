# 本地到GitHub到服务器通用发布流程（SOP）

适用场景：每次我在本地修改完代码后，你要把改动发布到 GitHub，并让阿里云服务器生效。

---

## 0. 约定

- 本地项目目录：`C:\Users\SHY\Desktop\Coding\AI基金预测系统`
- 服务器项目目录：`/root/ai-fund-monitor`
- 分支：`main`
- worker 入口：`python -m scripts.run_once`

---

## 1. 本地发布到 GitHub（Windows PowerShell）

```powershell
cd "C:\Users\SHY\Desktop\Coding\AI基金预测系统"

# 1) 看改动
git status

# 2) 暂存改动（推荐先 add 全部；如需精细可改成指定文件）
git add .

# 3) 提交
git commit -m "feat: update pipeline and frontend"

# 4) 同步远端，避免推送冲突
git pull --rebase origin main

# 5) 推送
git push origin main
```

说明：
- 如果 `git commit` 提示 `nothing to commit`，跳过 commit 即可。
- 如果 `git pull --rebase` 有冲突，解决后执行：
  - `git add <冲突文件>`
  - `git rebase --continue`

---

## 2. 服务器更新代码并执行（阿里云）

```bash
cd /root/ai-fund-monitor

# 1) 查看当前状态
git status

# 2) 如果有本地改动，先临时收起（强烈推荐）
git stash push -u -m "backup-before-update-$(date +%F-%H%M)"

# 3) 拉取最新
git pull --rebase origin main

# 4) 进入 worker 并运行
cd /root/ai-fund-monitor/worker
source .venv/bin/activate
python -m scripts.run_once
```

---

## 3. 发布后检查清单

### 3.1 检查 GitHub 数据导出是否更新

打开：

`https://raw.githubusercontent.com/21ShyYu/ai-fund-monitor/main/data_exports/dashboard.json`

确认不是空结构（不是全空数组）。

### 3.2 检查网站

- 访问：`https://www.iyushy.site`
- 如果页面还旧：去 Vercel 点一次 `Redeploy`（可立即刷新）

### 3.3 检查飞书

- 手工执行 `python -m scripts.run_once` 后看飞书是否收到。

---

## 4. 常见报错与处理

### 报错 A：`git push ... rejected (fetch first)`

原因：远端有新提交，本地落后。

处理：

```bash
git pull --rebase origin main
git push origin main
```

---

### 报错 B：`cannot pull with rebase: You have unstaged changes`

原因：当前目录有未提交修改。

处理：

```bash
git stash push -u -m "temp-before-pull"
git pull --rebase origin main
```

---

### 报错 C：`run_once` 里自动 push 失败

原因：服务器分支未先同步到最新。

处理顺序：

```bash
cd /root/ai-fund-monitor
git pull --rebase origin main
cd worker
source .venv/bin/activate
python -m scripts.run_once
```

---

## 5. 每次发布最短命令版（速用）

### 本地

```powershell
cd "C:\Users\SHY\Desktop\Coding\AI基金预测系统"; git add .; git commit -m "chore: update"; git pull --rebase origin main; git push origin main
```

### 服务器

```bash
cd /root/ai-fund-monitor && git stash push -u -m "temp" && git pull --rebase origin main && cd worker && source .venv/bin/activate && python -m scripts.run_once
```

---

## 6. 回滚（紧急）

### 本地回滚到上一个提交

```powershell
git log --oneline -n 5
git reset --hard HEAD~1
```

### 服务器回滚到远端 main 最新

```bash
cd /root/ai-fund-monitor
git fetch origin
git reset --hard origin/main
```

注意：`reset --hard` 会丢弃当前未保存改动，使用前先确认。

---

## 7. 建议固定动作

每次我改完后，你固定做这 4 步：
1. 本地 `git add/commit/pull --rebase/push`
2. 服务器 `git stash` + `git pull --rebase`
3. 服务器 `python -m scripts.run_once`
4. 检查 raw `dashboard.json` + 网站

