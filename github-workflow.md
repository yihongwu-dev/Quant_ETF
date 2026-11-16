# GitHub 工作流速查

> 适用仓库：`D:\Project\MachineLearning`
> 原则：先写 `.gitignore`，再 `git add`；提交前先看 `git status`。

## 一句话流程

```text
日常更新：git add -A → git commit -m "说明" → git push
```

首次绑定远程仓库时，最后一步需要 `git push -u origin main`。

## 一、提交前检查

```powershell
cd D:\Project\MachineLearning
git status --short
```

确认：

- 没有 `.ipynb_checkpoints/`、`__pycache__/`、`outputs/` 中不想提交的临时文件；
- 没有大文件、密钥文件（`.env`）；
- 删除和重命名的文件符合预期。

查看改动统计：

```powershell
git diff --stat
```

## 二、日常更新（最常用）

```powershell
cd D:\Project\MachineLearning
git add -A
git commit -m "补充 SVM 笔记"
git push
```

说明：

- `git add -A` 会同时记录**新增、修改、删除、重命名**；比 `git add .` 更明确，推荐统一使用。
- `git commit -m` 的说明写清“做了什么”，不要写 `update`、`fix` 这类无信息内容。
- 首次推送如果提示没有上游分支，执行一次：

```powershell
git push -u origin main
```

之后直接 `git push` 即可。

## 三、本次目录重构怎么提交

这次是把文件移到了新目录（手工移动，未使用 `git mv`），Git 会看到“旧文件删除 + 新文件新增”。一条 `git add -A` 就能全部记录，Git 会自动识别为 rename：

```powershell
cd D:\Project\MachineLearning
git status
git add -A
git status
git commit -m "重构目录结构：按基础库、算法、深度学习、小项目分层"
git push
```

提交前重点确认：

- `DataProcess/` 下的旧文件显示为 `deleted`；
- `01-python-libs/`、`02-supervised-learning/`、`03-unsupervised-learning/`、`04-deep-learning/`、`05-miniprojects/`、`docs/` 显示为 `new file`；
- 旧的根目录文档（`quickcheck.md`、两份 `PyLearn_*.md`）已删除。

## 四、仓库尚未绑定远程时

先检查：

```powershell
git remote -v
```

### 情况 A：已有输出（说明已绑定）

直接按第二节推送即可。

### 情况 B：没有任何输出（尚未绑定）

方式一，使用 GitHub CLI（需先 `gh auth login`）：

```powershell
gh repo create MachineLearning --private --source=. --remote=origin --push
```

方式二，先在网页 [github.com/new](https://github.com/new) 建一个空仓库（不要勾选 README），然后：

```powershell
git remote add origin https://github.com/<你的用户名>/MachineLearning.git
git push -u origin main
```

## 五、如何修改 GitHub 上的“记忆”

GitHub 上的“记忆”就是远程仓库的**提交历史**。按修改范围分四种情况。

### 情况 A：把最新状态同步上去（占 99%）

你的判断是对的，三条命令就够：

```powershell
git add -A
git commit -m "这次改了什么"
git push
```

执行后 GitHub 上会多一条新提交，旧历史完整保留。这是**追加记忆**，不是覆盖。

### 情况 B：修改最近一次提交

**尚未 push**，或者确认只有你一个人使用该仓库：

```powershell
git add -A
git commit --amend -m "修正后的提交说明"
```

如果这次提交已经 push 过，需要覆盖远程：

```powershell
git push --force-with-lease
```

`--force-with-lease` 比 `--force` 安全：如果远程在此期间被别人更新过，它会拒绝覆盖。

### 情况 C：修改更早的历史

```powershell
git rebase -i HEAD~3
```

在编辑器里把 `pick` 改成 `reword`（改说明）、`squash`（合并）或 `drop`（删除），保存退出后：

```powershell
git push --force-with-lease
```

**风险提示**：改写历史会改变提交哈希。多人协作、或别人已经基于该仓库工作时，不要这样做。个人学习仓库偶尔整理可以，但没必要频繁清理。

### 情况 D：修改 GitHub 页面上的说明性内容

| 想改什么 | 怎么改 |
| --- | --- |
| README 内容 | 本地编辑 `README.md`，走情况 A |
| 仓库简介 / About / Topics | GitHub 网页仓库页 → 右侧 `About` 旁的齿轮 |
| Issue / PR 的标题或正文 | 网页上直接编辑，属于 GitHub 自身数据，与 git 历史无关 |
| 仓库可见性（Public/Private） | 网页 `Settings` → `General` → `Danger Zone` |

### 提交后验证

```powershell
git status
git log --oneline -3
git remote -v
```

`git status` 显示 `nothing to commit, working tree clean` 即表示本地已全部记录；刷新 GitHub 仓库页，能看到最新提交和文件结构即可。

## 六、常用“体检”命令

| 命令 | 作用 |
| --- | --- |
| `git status` | 当前有哪些改动、是否已暂存 |
| `git diff` | 查看未暂存的具体改动 |
| `git diff --cached` | 查看已暂存、即将提交的改动 |
| `git log --oneline -10` | 最近 10 条提交 |
| `git remote -v` | 查看远程地址 |
| `git branch -vv` | 当前分支及上游跟踪关系 |
| `git config --global --get-regexp proxy` | 查看代理配置 |

## 七、常见问题

### 1. `fatal: not a git repository`

终端不在仓库目录。先 `cd D:\Project\MachineLearning`。

### 2. `LF will be replaced by CRLF`

Windows 与 Unix 换行符差异，属于提示而非错误，可以忽略。

### 3. `Failed to connect ... 127.0.0.1`

git 配置了本地代理，但代理软件未启动。先检查代理配置：

```powershell
git config --global --get-regexp proxy
```

若代理软件（如 Clash Verge）实际端口与配置不一致，更新为实际端口：

```powershell
git config --global http.proxy http://127.0.0.1:<端口>
git config --global https.proxy http://127.0.0.1:<端口>
```

不需要代理时，可以临时取消：

```powershell
git config --global --unset http.proxy
git config --global --unset https.proxy
```

### 4. `remote: error: GH007` 邮箱隐私保护

提交里带有真实邮箱，被 GitHub 拒绝。查询并设置 noreply 邮箱：

```powershell
gh api user --jq '"\(.id)+\(.login)@users.noreply.github.com"'
git config --global user.email "<查到的 noreply 邮箱>"
git commit --amend --reset-author --no-edit
git push --force-with-lease
```

### 5. `push rejected (non-fast-forward)`

远程有你本地没有的提交，先拉取再推：

```powershell
git pull --rebase origin main
git push
```

### 6. 文件已经被跟踪，后来才想忽略

`.gitignore` 只对**未跟踪**文件生效。已经入库的文件需要先从索引移除：

```powershell
git rm -r --cached "05-miniprojects/experiment-stretch/outputs"
git commit -m "停止跟踪生成图"
```

文件仍保留在磁盘上，只是不再被 Git 管理。

### 7. 误提交了大文件

在**尚未 push**时：

```powershell
git reset --soft HEAD~1
git rm --cached <大文件路径>
git commit -m "重新提交"
```

已经 push 且文件很大时，需要 `git filter-repo` 清理历史，属于高风险操作，先备份仓库再处理。

## 八、本机档案（按旧笔记整理，若已变更请修改）

| 项目 | 值 |
| --- | --- |
| GitHub 账号 | `yihongwu-dev` |
| git 邮箱 | 已设置为 GitHub noreply 邮箱，勿改回真实邮箱 |
| 代理 | 曾配置本地代理，具体端口以 `git config --global --get-regexp proxy` 为准 |
| 本仓库远程 | 运行 `git remote -v` 查看 |
