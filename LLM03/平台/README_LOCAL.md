# Section2-LLM 本地证据与阶段工作流平台

**正式 Release：** `B001-v1.2-text-scope-preview-20261010`（只读先导预览）  
**新增能力：** loopback-only PDF 隔离上传、真实 Step 02 清洗/分块 runner、Step 03 BM25-only 索引、逐阶段结果画布、项目/方法架构图、版本标注图2-1至2-4、单次问答的可选 OpenAI-compatible / CSTCloud 模型目录。  
**Python：** 3.10+。默认监听 `127.0.0.1:8765`；不需要 Flask、CDN 或浏览器扩展。

## 1. 一键本机启动

### macOS / Linux

```bash
./平台/start.sh
```

### Windows

双击 `平台\\start.bat`，或在 PowerShell/CMD 执行：

```bat
平台\start.bat
```

启动器会检查本机服务 readiness，并在服务就绪后打开默认浏览器。终端窗口保持运行；按 `Ctrl+C` 停止。可用 `--no-browser` 只启动服务：

```bash
./平台/start.sh --no-browser
```

默认端口是 `8765`。自定义端口：

```bash
PLATFORM_PORT=8766 ./平台/start.sh
```

Windows 可在启动前设置 `PLATFORM_PORT` 环境变量。默认 loopback bind 才开放上传、模型目录和外部 API 设置。不要把单用户无认证服务暴露到公共网络；若设成 `PLATFORM_HOST=0.0.0.0`，写入型工作流和外部 API 会关闭。

### 首次安装本地 PDF 工作流依赖

`start.sh` 不会暗中安装或联网下载依赖。Step 02 需要 PyMuPDF、openpyxl、python-docx；若缺少，平台仍可启动只读检索，但会把 Step 02 如实标为“缺少依赖”，不会调用脚本处理 PDF。一次性在本机安装：

```bash
python -m pip install -r 平台/requirements-local.txt
```

如使用独立虚拟环境，先激活环境，再运行上面的安装命令和 `start.sh`/`start.bat`。

## 2. 新 PDF 隔离运行

1. 在侧栏打开 **阶段工作流**，点击 **新建隔离 run**。
2. 选择一个或多个 PDF，确认清单后点击 **上传到当前 run**。每个 run 最多 10 篇；单篇最多 50 MB、合计最多 120 MB。上传首先检查 PDF 文件头，登记文件名、大小、时间和 SHA-256。
3. 选择 **确认并运行 Step 02**。网页调用项目已有 `step1_run_versioned_batch_local.py` 和 `step2_run_versioned_local.py`，在隔离目录中调用现有 Step 1/2 脚本；默认不联网、不发给任何模型。
4. 在“阶段结果画布”查看日志、manifest、文本/JSON 预览与产物下载。输入、脚本和输出指纹由版本化 wrapper 记录；结果目录拒绝覆盖。失败时保留新 run 的部分文件用于审查，不自动删除或重用。
5. Step 02 完成后，可点击 **确认并运行 Step 03**。当前网页构建的是**本地 BM25-only**索引，并可在此 run 内进行本地 BM25 检索。它不是完整 Dense/BM25/图谱混合索引：Dense 新向量查询与新 run provenance graph 尚未接入。

隔离规则：新上传 PDF、Step 1/2/3 输出只保存在 `平台/platform/data/workflows/<run_id>/`，不并入正式 B001 五篇样本，不改变 release、QA 历史记录或其他研究产物。运行 manifest 明确记录 `formal_sample_extension_authorized=false`。目前 UI 不提供自动删除；需要清理时，请在本机确认 run 内容后自行删除对应的隔离 run 文件夹。

## 3. 当前工作流实现状态

| 阶段 | 当前状态 | 说明 |
|---|---|---|
| 01 PDF 上传与登记 | 已接入 | Loopback-only；新 run 隔离；SHA-256 登记 |
| 02 PDF 清洗与分块 | 已接入真实脚本 runner | 调用现有 Step 1/2 wrapper；依赖缺失时阻止运行 |
| 03 本地索引 | 部分就绪 | BM25-only 可运行；Dense 与新 run 图谱未构建 |
| 04 LLM 抽取与 Critic | 未接入网页工作流 | 现有 v1.2 外部 API 跑批代码不等于本网页 runner；本页不发送整批 evidence |
| 05 人工核验与指标 | 未就绪 | 需真实 Step 04 ledger 与人工核验；不使用 mock/dry-run 填充 |
| 06 跨文献综合与 FRDI | 未就绪 | 依赖完整审核 ledger；只挑战 Introduction 中已有三方向，不自动生成方向 |
| 07 新 run 图表/章节输出 | 未就绪 | 现存图表可在图库查看并标来源，但不是新 run 输出 |

图表图库目前提供 v1.2 text-scope static-pilot r2 的图2-1、图2-3，以及历史图2-1至图2-4。图2-2、图2-4 的 v1.2 对应图尚未生成。历史图2-1/2-2含旧版 D03 方程标签，页面会显著标为历史档案；不要把它们当作当前 v1.2 研究图。

## 4. 正式样本与研究范围

- 正式研究仍只分析 5 篇 PDF。上传至新 run 不表示用户批准扩充正式样本；D01–D10 标签缺失也不表示领域不存在。
- 三项候选方向由论文第一节 Introduction 通过领域文献对比提出；平台不在线搜索或自动生成研究方向。
- 公式转录、推导、变量/符号解释和方程类型分析不进入新版结论或质量指标；本机 BM25 检索也会拒绝公式分析类查询。原 PDF、evidence blocks 和公式风险 metadata 保留；风险标记不代表已解析。
- PDF-03 / D02 仍未获用户定稿。任何模型/Agent 提议都不视作批准。
- 正式 release 依旧是 hash-checked、provisional、read-only；新 run 不写入正式图谱、records 或 PDF 包。

## 5. 可选 API Key 与模型选择（只用于单次 QA）

1. 在本机 loopback 页面点击 **模型 / API Key**。
2. 选择 CSTCloud Uni-API（默认优先）或通用 OpenAI-compatible。CSTCloud Base URL 固定为 `https://uni-api.cstcloud.cn/v1`。
3. 可以点击 **获取可用模型目录**（由服务端按当次请求读取 `/models`），也可以手动填写服务商返回的精确模型 ID。账号的实时目录优先于文档静态示例。
4. 填写 API Key 后，必须再在“证据检索”显式勾选“本次问答使用外部 API”并提交一次问题，才会调用生成。未勾选时只做本地检索；无自动云端回退。

Key 只存在于浏览器当前页面内存和当次 HTTPS 请求中，不写入工作区、环境变量、浏览器存储或服务端日志；离开页面时清空。模型目录请求只发送 endpoint/provider 与 Key，不发送问题或语料。CSTCloud API 文档：<https://uni-api.cstcloud.cn/doc/llm/>。真实账号/Key 未在本工作区做连通性验证。

单次外部问答仍沿用原有硬边界：最多发送当前问题与最多 5 条检索证据块，每条最多 3500 字符；公式风险块排除；不发送整篇 PDF、批量 evidence blocks 或完整语料。服务商留存适用其条款。**API Key/模型选择目前没有接通新 run 的 Step 04/06 批量工作流**；未来如接入批量步骤，必须新增数据范围披露和每阶段显式确认，不能默认为已授权整批外传。

外部 endpoint 限公网 DNS、HTTPS `/v1`、443；CSTCloud 预设固定主机名。服务端校验 DNS/IP、固定到校验 IP、禁用代理并拒绝重定向。共享预览或非 loopback bind 会禁用模型目录、Key 输入、上传和外部 API。

## 6. 原有只读检索能力

- 正式 release 内 5 篇 PDF、239 个 evidence blocks、45 条九维 provisional 编码、来源图谱与 BM25 检索。
- 默认回答模式是原文证据包，不调用模型。公式分析类查询会提示超出范围。
- Dense 文档向量随 release 保存；只有与其一致的 FastEmbed query encoder 和本地缓存准备完成后，Dense 才能启用。应用不会自动下载权重。
- release 构建脚本只写新 release 目录并拒绝覆盖；平台本身不会编辑正式 release。

## 7. 目录与接口

```text
平台/
  start.sh / start.bat / launcher.py    # 一键启动、readiness、打开浏览器
  requirements-local.txt               # Step 02 本地依赖
  README_LOCAL.md
  platform/
    app.py                              # loopback 服务与 API 路由
    rag_core/workflows.py               # 隔离 run、上传、Step 02/03 与产物校验
    rag_core/generation.py              # 单次 QA 的可选远程模型与目录请求
    static/                             # 本地 HTML/CSS/JS/SVG 架构图
    data/workflows/                     # 本机隔离运行目录（不进正式 release）
    data/releases/                      # 哈希校验的只读正式 release
```

| 路由 | 作用 |
|---|---|
| `GET /api/status` | Release、模型、loopback 工作流与能力状态（不含 Key） |
| `GET /api/documents`、`GET /api/graph` | 正式先导文献及来源图谱 |
| `GET /api/figures`、`GET /figures/<固定ID>` | 固定目录的版本化图表 |
| `POST /api/qa` | 本地检索/证据包；外部生成仅显式单次授权 |
| `POST /api/models` | 按显式请求读取服务商 `/models`；不含研究内容 |
| `GET/POST /api/workflows` | 列出或创建本机隔离 run；仅 loopback |
| `POST /api/workflows/<run>/files?filename=...` | 上传单个 PDF 原始字节到隔离 run；仅 loopback |
| `POST /api/workflows/<run>/stages/02_pdf_clean_chunk` | 确认后运行真实本地 Step 1/2 |
| `POST /api/workflows/<run>/stages/03_bm25_index` | 确认后构建 BM25-only 索引 |
| `GET /api/workflows/<run>/search?q=...` | 对当前隔离 run 做本机 BM25 检索 |
| `GET /api/workflows/<run>/artifacts/<id>` | 下载 run 产物；`?preview=1` 返回有限文本画布 |

## 8. 验证与未验证事项

本机测试命令：

```bash
python -m py_compile 平台/launcher.py 平台/platform/app.py 平台/platform/rag_core/workflows.py 平台/platform/rag_core/generation.py
node --check 平台/platform/static/app.js
python -m unittest discover -s '平台/platform/tests' -v
```

最近一次离线测试共 28 项通过。测试/Mock 只验证路由安全、清单逻辑、输入隔离与 HTTP 客户端边界，不是本地 LLM、完整离线、真实服务商 API 或研究语义质量验证。真实 CSTCloud Key 未配置；没有向服务商发送过 PDF 或 evidence blocks。Step 02 是否可运行取决于用户本机安装的 PyMuPDF 等依赖与实际 PDF；FastEmbed Dense cache 也未验证。
