# Section2-LLM 同步到 GitHub 操作手册

**本地项目根目录：** `/home/user/Section2-LLM`  
**目标仓库：** `https://github.com/zhiyuanl614-netizen/clone`  
**HTTPS remote：** `https://github.com/zhiyuanl614-netizen/clone.git`  
**目标布局：** 项目文件直接放在仓库根目录；不要在项目根目录内留下 `clone/`、`Section2-LLM/` 等多余外层目录。

## 0. 本次工作区实际状态

项目目录 `/home/user/Section2-LLM` 当前**没有 `.git/`，也没有 `.gitignore`**。本次已对目标仓库做只读预检，但**尚未提交或推送**：GitHub API 显示仓库为公开仓库，默认分支 `main`；远端当前 commit 为 `f6a26ca`，仓库根目录只有 `.gitignore` 和旧目录 `Section2-LLM_离线完整版/`。该旧目录有106个文件，与当前本地项目比较为：78个同路径同内容、7个同路径不同、89个本地独有、21个远端独有。远端的5篇原始 PDF 与本地 `01_文献库/` 对应文件 SHA-256 相同。对本地常见密钥格式做了路径/类型不泄露值的扫描，未发现匹配；这不替代人工审查。

**推送前需确认目录迁移和远端独有文档处理。** 若把当前项目提升到仓库根，远端旧目录将从最新 `main` 树中删除；21个远端独有文件包括18个 `.gitkeep` 占位文件、`README_API批量管线.md`、`P1_frozen_pipeline_config_v1_LOCKED.md` 和 `README_离线完整版说明.md`。普通 commit 会保留旧内容的 Git 历史，但这些文件将不再出现在最新树。为避免擅自删除未点名的远端文档，本次停在预检，没有执行 commit/push。

本次还从本地项目删除了两个根目录文档：`P1_frozen_pipeline_config_v1_LOCKED.md` 和 `v1.2代码审计_研究方向对齐_20261010.md`；`/home/user/uploads/` 在项目目录之外，不会作为项目内容上传。当前根目录 `README.md` 仍有对已删除 P1 文档的历史引用；发布前应决定是否改成历史说明，避免留下悬空链接。

## 1. 同步前保护规则

1. **先核对路径和仓库。** 只在 `/home/user/Section2-LLM` 操作，确认 remote 是 `zhiyuanl614-netizen/clone`。不要从 `/home/user` 执行 `git add -A`。
2. **绝不强推或抹除远端历史。** 不使用 `git push --force`、`git push --mirror`、`git reset --hard` 或带 `--delete` 的目录复制。发生分歧先停下检查。
3. **不提交凭证。** API Key、Personal Access Token、密码和含真实凭证的 `.env` 不得进 Git；不要把 token 填进 remote URL 或命令行。Key 若曾被提交，单纯删除文件不能清除 Git 历史，应立即撤销/轮换。
4. **逐项审查 PDF 与衍生产物。** 上传前确认仓库可见性、版权许可和数据授权。正式 PDF、分块、运行记录和图表不自动等于可公开。GitHub 普通 Git 文件有大小限制；超大文件先评估 Git LFS 或不纳入仓库。
5. **隔离用户上传。** `平台/platform/data/workflows/` 下的 PDF、run 和阶段产物是本机运行数据，默认不应同步。
6. **保持目录结构。** 同步后 `README.md` 应位于仓库根，`01_文献库/` 至 `07_图表与章节输出/`、`平台/` 直接位于仓库根，不要出现 `clone/Section2-LLM/...` 之类的嵌套副本。

## 2. 安装/检查 Git 与认证

以下命令以 Bash（Linux/macOS、Git Bash 或 WSL）为例：

```bash
PROJECT=/home/user/Section2-LLM
REMOTE=https://github.com/zhiyuanl614-netizen/clone.git

git --version
test -d "$PROJECT" && test -f "$PROJECT/README.md"
git ls-remote --symref "$REMOTE" HEAD
```

`git ls-remote` 若提示权限或认证失败，先用 GitHub CLI 登录，再重试：

```bash
gh auth login --hostname github.com --git-protocol https --web
gh auth status
```

若没有 `gh`，使用系统 Git Credential Manager 的交互登录。不要将密码、token 写进本文、脚本、环境文件或 remote URL。远端默认分支以 `git ls-remote --symref` / 克隆后的 `origin/HEAD` 为准；不要想当然假设一定是 `main`。

## 3. 准备忽略规则并检查待同步内容

当前项目根目录没有 `.gitignore`。首次同步前先创建一份，并与远端已有规则合并，不要覆盖远端已有内容。可从下面的**基础规则**开始：

```gitignore
# Secrets and local credentials
.env
.env.*
!.env.example
*.pem
*.key

# Python environments and caches
.venv/
venv/
**/__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/

# OS/editor and generated dependencies
.DS_Store
Thumbs.db
node_modules/

# Locally uploaded PDFs and isolated workflow outputs
/平台/platform/data/workflows/
```

这只是起点：逐个确认 `.env.example` 只有占位符；不要用 `*.pdf` 一刀切，因为是否同步正式 PDF 需要单独确认。`.gitignore` 不会自动取消已被 Git 跟踪的文件，若远端已跟踪敏感内容，应先停止同步并单独处理。

添加文件之前，在项目根目录检查体积、凭证和预期纳入范围：

```bash
cd "$PROJECT"
find . -type f -size +95M -not -path '*/.git/*' -print
# 仅当当前目录已经是 Git 工作树时运行：
git status --short --branch
git ls-files
```

`git add -n -A` 预演也要等到 `git init`（远端空）或克隆远端到临时目录（远端非空）之后，再在对应 Git 工作树中执行。重点查看 PDF、`.env*`、日志、用户上传目录、模型/向量缓存，以及本次明确删除的两份文档。确认没有 token、私人文件或未获授权的 PDF 后再真正暂存；发现任何疑似秘密时不要提交，先从工作树中排除，必要时撤销/轮换该凭证。

## 4. 依据远端状态选择首次同步方式

### A. 远端仓库为空

只有 `git ls-remote --symref "$REMOTE" HEAD` 确认远端没有分支/提交，且 GitHub 页面也确认该仓库为空时，才在现有项目目录初始化：

```bash
cd /home/user/Section2-LLM
git init -b main
git remote add origin https://github.com/zhiyuanl614-netizen/clone.git
# 设置为实际作者信息；只需为此仓库设置时不要加 --global
git config user.name "YOUR NAME"
git config user.email "YOUR VERIFIED EMAIL"

git add -n -A                 # 预览
# 核查 .gitignore、隐私/版权和文件清单后：
git add -A
git diff --cached --check
git diff --cached --stat
git diff --cached --name-status
git diff --cached             # 逐项审查变更内容
git commit -m "Sync Section2-LLM workspace"
git push -u origin main
```

若远端默认分支不是 `main`，先确认仓库策略，再将命令中的分支名改为目标分支；不要因此强推。

### B. 远端已有提交或文件（推荐保留远端历史）

不要在非空工作树上直接 `git clone`，也不要强行把本地历史覆盖远端。使用项目目录之外的临时克隆来保留远端历史；临时目录完成后删除，不在项目里留下 `clone/` 外层目录：

```bash
PROJECT=/home/user/Section2-LLM
REMOTE=https://github.com/zhiyuanl614-netizen/clone.git
TMP_ROOT="$(mktemp -d /tmp/Section2-LLM-sync.XXXXXX)"
CLONE="$TMP_ROOT/repo"

git clone "$REMOTE" "$CLONE"
git -C "$CLONE" remote -v
git -C "$CLONE" branch -a --no-color
BRANCH="$(git -C "$CLONE" symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's#^origin/##')"
if [ -z "$BRANCH" ]; then
  echo '远端默认分支无法自动判定；查看上方分支列表后手动设置 BRANCH，再继续。'
  exit 1
fi
# 确认仓库根布局、默认分支和现有文件；有意外嵌套目录或不明内容就停止。
```

远端已有提交时，先检查其文件和 `.gitignore`，再在克隆工作树上合入本地项目文件。`rsync` 不带 `--delete`，并排除 Git 元数据、缓存、密钥与隔离 run：

```bash
rsync -a \
  --exclude='/.git/' \
  --exclude='/.venv/' --exclude='/venv/' \
  --exclude='/**/__pycache__/' --exclude='/**/.pytest_cache/' \
  --exclude='/**/node_modules/' \
  --exclude='/**/.env' --exclude='/**/.env.*' \
  --exclude='/平台/platform/data/workflows/' \
  "$PROJECT/" "$CLONE/"
```

`.env.example` 如确需纳入，先确认它只有示例占位符，再单独复制/暂存。合入后先看差异，特别注意远端已有 README、配置文件以及删除项：

```bash
git -C "$CLONE" status --short --branch
git -C "$CLONE" diff --stat
git -C "$CLONE" diff --name-status
# 逐个打开并审查新增、修改、删除的文件；不要只看汇总。
```

确认范围无误后，在克隆工作树中暂存、审查、提交并推送到克隆当前跟踪的目标分支：

```bash
git -C "$CLONE" add -n -A
git -C "$CLONE" add -A
git -C "$CLONE" diff --cached --check
git -C "$CLONE" diff --cached --stat
git -C "$CLONE" diff --cached --name-status
git -C "$CLONE" diff --cached
# 可按需配置本地 user.name / user.email
git -C "$CLONE" commit -m "Sync Section2-LLM workspace"
git -C "$CLONE" fetch origin
# BRANCH 来自上方 origin/HEAD；如远端有新提交，先 rebase/合并并解决冲突。
git -C "$CLONE" pull --rebase origin "$BRANCH"
git -C "$CLONE" push origin "HEAD:$BRANCH"
```

若远端目录与本地结构明显不同、Git 报 unrelated histories、出现未理解的冲突，或暂存清单包含意外删除，**停止**；不要加 `--force` 或 `--allow-unrelated-histories` 试图绕过。先备份并确认哪一边是权威版本。

推送成功后，如要让原来的 `/home/user/Section2-LLM` 成为后续日常使用的 Git 工作树（当前它没有 `.git/`），先确认原目录仍没有 `.git/`，再把已推送的工作树同步回来并复制 `.git` 元数据：

```bash
test ! -e "$PROJECT/.git" || { echo '项目已有 .git；停止，不覆盖'; exit 1; }
rsync -a --exclude='/.git/' "$CLONE/" "$PROJECT/"
cp -a "$CLONE/.git" "$PROJECT/.git"
git -C "$PROJECT" status --short --branch
git -C "$PROJECT" log -1 --oneline
```

确认原路径的 `git status` 和提交记录正常后，再删除临时目录：

```bash
rm -rf -- "$TMP_ROOT"
```

注意：这最后一步只允许删除本次由 `mktemp` 创建、且变量指向的临时目录；不要手动把路径替换成项目根目录。

## 5. 后续日常同步

原项目目录已成为 Git 工作树后，每次在项目根目录按以下顺序操作：

```bash
cd /home/user/Section2-LLM
git status --short --branch
git fetch origin
BRANCH="$(git symbolic-ref --short refs/remotes/origin/HEAD | sed 's#^origin/##')"
# 确认工作树干净且 BRANCH 是实际默认分支后，拉取更新：
git pull --rebase origin "$BRANCH"

# 只暂存预期文件；较安全的方式是逐块选择：
git add -p
# 或确认完整清单后再 git add -A

git diff --cached --check
git diff --cached --stat
git diff --cached --name-status
git diff --cached
git commit -m "Describe the actual change"
git push origin "$BRANCH"
```

如有未提交改动，先检查并提交或有意识地暂存；不要直接 pull 覆盖工作树。冲突时按文件逐项解决、运行相关测试，再提交/推送。推送后确认：

```bash
git status --short --branch
git log -1 --oneline
git ls-remote --heads origin "$BRANCH"
```

最终还要在 GitHub 网页核实仓库、分支和文件路径，确认 README 位于仓库根且没有嵌套外层目录。

## 6. 本项目同步前的检查清单

- [ ] 当前目录确为 `/home/user/Section2-LLM`，目标仓库确为 `zhiyuanl614-netizen/clone`。
- [ ] 已核实远端是否为空、默认分支和可见性；未假设远端无内容。
- [ ] `.gitignore` 已建立/合并；`平台/platform/data/workflows/`、凭证和缓存不会被暂存。
- [ ] 已审查正式 PDF、evidence blocks、模型/运行日志、图表、Office 文件的版权、隐私、体积和同步授权。
- [ ] 已检查 `git diff --cached --name-status`；删除项只包含明确授权的内容。
- [ ] 已检查差异中没有 API Key、token、`.env` 或其他秘密。
- [ ] 没有用 force push、mirror、reset hard 或 `rsync --delete`。
- [ ] push 后项目路径和 GitHub 仓库根目录均没有 `clone/Section2-LLM/` 之类外层副本。
- [ ] 推送成功后 `git status` 干净，GitHub 网页的目标分支已核验。
