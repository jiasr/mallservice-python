# AGENTS.md

> 本文件是 AI 编码 Agent（CodeBuddy / Qoder / Cursor 等）在 **mallservice-python** 仓库工作时的**协作入口与纪律补充**。
> **开发规范的唯一载体是 `../doc/开发规范汇总.md`**（位于 `e:\aicode\doc\`，跨所有工具/仓库共享）。本文件不重复规范细节，只做索引与 Agent 协作纪律补充。开始任何任务前，**必须先阅读该汇总并遵守其全部条款**。

## 必读（开工前）
- 规范唯一载体：`../doc/开发规范汇总.md`（数据库/后端、飞鹅打印、前端交互、业务规则、源码管理五类约定）
- 源码管理铁律（第五章）：push 前必拉、原子提交、子模块联动、禁敏感信息、文档走正规流程、提交信息 `<type>: <中文描述>`
- 提交前必须运行 `e:\aicode\check-commit.ps1`，并确保通过父仓库 `.githooks/pre-push` 检查（禁止 `--no-verify` 绕过，除非确认合规）

## 本仓库定位
- 本仓库是 `e:\aicode` 父仓库（superproject）的**子模块**
- 后端技术栈：`Flask + Flask-RestX + MySQL`
- 跨仓库改动（前后端联调）请与 `mall-admin` 共用同一份接口/字段契约

## Agent 协作纪律（多 Agent / 多工作区并行）
1. **先读规范再动手**：每次新会话、重开工作区、切换任务时，先读 `../doc/开发规范汇总.md` 与本地记忆，再开始；规范以该汇总为准，不与对话中的临时约定冲突。
2. **分支隔离**：每个并行任务用独立分支（`feat/*`、`fix/*`）；**禁止在 detached HEAD 或 main 上直接开发**；push 前 `git pull --rebase`，禁止 `--force` push。
3. **契约先行**：跨仓库（前后端）改动先冻结接口/字段契约（OpenAPI、类型、SQL schema），再并行实现，避免各猜各的。
4. **勿碰临时/敏感文件**：`*_tmp*`、本地缓存、`token`/`密钥`/`.env`/`*.key`/`*.pem` 一律不纳入提交（遵循铁律 4 与 `.gitignore`）。
5. **改规范走正规流程**：新增/修正规范必须**同时更新 `doc/开发规范汇总.md`**（更新顶部日期 + 注明来源 `[CodeBuddy]`/`[Qoder]`/`[人工:姓名]` + 说明原因），随代码一起或单独提交（铁律 5）；不要只在对话里约定。
6. **原子提交 & 中文描述**：遵循铁律 2、6，一个 commit 只做一件事，信息 `<type>: <中文描述>`。
7. **子模块联动**：本仓库提交推送后，须在父仓库 `e:\aicode` 执行 `git add mallservice-python` 并提交推送指针更新（铁律 3），否则父仓库会显示子模块 M 变更。

## 禁止
- 禁止 `git push --force`
- 禁止把敏感信息（`gds_token`、`.env`、`*.key`、`*.pem`、`password`、`secret`）提交入库
- 禁止绕过 `check-commit.ps1` 与 pre-push hook（`--no-verify` 仅限确认合规时）

## 提交前自检（check-commit.ps1）
在 `e:\aicode` 根目录运行：
```powershell
cd e:\aicode
powershell -ExecutionPolicy Bypass -File .\check-commit.ps1
```
全部 PASS 再 push；任一 FAIL 先修复。
