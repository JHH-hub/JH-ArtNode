# AGENTS.md · JH-ArtNode AI 协作上下文导航

本文档为 `JH-ArtNode` 仓库的 AI 协作导航与工程规范。参与本仓库开发的 AI Agent（Claude Code、Antigravity、OpenCode、Cursor、GitHub Copilot 等）在阅读、修改或提交代码前，请先阅读本文件。

---

## 1. 项目定位与核心工作流

`JH-ArtNode` 是面向**小游戏美术 AIGC 工作流**的决策节点工具（原版 Python GUI `OneKeyStyleTransfer` 的 Web + 浏览器扩展复刻版）。其核心目标是通过结构化提示词工程降低美术生产中的认知负荷，并辅助跨越 Norman 双鸿沟模型中的「执行鸿沟（Gulf of Execution）」。

系统围绕 **5 个核心决策节点** 运作：
1. **节点 1 · 意图梳理与茬点分流 (`/clarify`)**：将策划粗糙剧本与茬点清单拆分为**「底图直出静态茬点」**与**「后期局部重绘 / Spine 动态拆层茬点」**，强制执行移动端竖版 `9:16` 安全区约束（纵向 `15%~85%`，避开顶底 `12%` UI 遮挡死区），为动态层预留干净的物理承载面与受光反射锚点（或独立剪影轮廓不穿模），并禁止将道具名称直接作为汉字印在物体表面。
2. **节点 2 · 内容图 6 维解析 (`/analyze`, `role=content`)**：提取 `[CONTENT-1 主体]`、`[CONTENT-2 场景]`、`[CONTENT-3 构图]`（含 9:16 安全区与非对称纵深）、`[CONTENT-4 视角]`、`[CONTENT-5 几何与线条]`、`[CONTENT-6 关键细节]`（区分静态道具与独立轮廓/预留物理锚点），输出**零颜色、零风格词、零媒介词**的纯内容 Prompt。
3. **节点 3 · 风格图 7 维解析 (`/analyze`, `role=style`)**：提取 `[STYLE-1 媒介]`、`[STYLE-2 调色]`（含 3~5 个 hex 或色名）、`[STYLE-3 光影语言]`、`[STYLE-4 笔触与材质]`、`[STYLE-5 画面氛围]`、`[STYLE-6 标志元素]`、`[STYLE-7 一句话风格标签]`，输出**零具体物件名词**的纯风格 Prompt。
4. **节点 4 · 提示词合并 (`/merge`)**：将纯内容 Prompt 与纯风格 Prompt 套入中英双语结构保留模板（明确指示「保留构图与主体身份，仅替换美术风格、配色、光影与质感」）。
5. **节点 5 · 反向提词 (`/reverse`)**：针对目标效果图逆向解耦提取内容与风格提示词，支持 `both` / `content` / `style` 三种模式。

---

## 2. 仓库目录与架构索引

```text
JH-ArtNode/
├── backend/                  # FastAPI 后端服务与提示词引擎
│   ├── main.py               # FastAPI 入口、路由定义、Gemini SDK 调用与静态资源托管
│   ├── prompts.py            # 双语 System Prompts、双语切割器、四级兜底提取器与合并模板
│   ├── requirements.txt      # Python 依赖清单 (FastAPI, Uvicorn, google-genai, Pillow 等)
│   └── .env.example          # 环境变量模板 (GOOGLE_API_KEY, ANALYZE_MODEL)
├── frontend/
│   └── public/
│       └── index.html        # 零外部依赖的单文件原生 Web 应用 (HTML5 + CSS Variables + Vanilla JS)
├── extension/                # Chrome / Edge 浏览器插件 (Manifest V3)
│   ├── manifest.json         # MV3 扩展配置 (contextMenus, storage, activeTab, scripting)
│   ├── background.js         # Service Worker：注册右键菜单、转发 /analyze-url 请求、维护 storage 队列
│   ├── content.js            # 页面注入脚本：右下角分析浮窗 (#__artnode_panel)、页内复制与合并
│   ├── popup.html            # 扩展弹出面板：展示 CONTENT/STYLE 队列状态、合并提示词与跳转 Web
│   ├── gen_icons.py          # 基于 Pillow 的纯代码图标生成脚本
│   └── icons/                # 插件图标产物 (icon16.png, icon48.png, icon128.png)
└── README.md                 # 项目说明文档
```

### 2.1 后端模块 (`backend/`)
- **`backend/main.py`**：
  - 使用最新 `google-genai` SDK（`from google import genai`），通过 `_get_client()` 读取环境变量 `GOOGLE_API_KEY`。
  - **图像预处理 `_compress_if_needed(image_bytes, mime)`**：支持 `png` / `jpeg` / `webp` / `bmp` / `gif`，单图上限 `10MB`（`MAX_IMAGE_BYTES`）；当图片体积 `> 4MB` 时自动用 Pillow 转为 RGB `JPEG (quality=85)` 再做 Base64 编码上传。
  - **重试机制 `_call_gemini(role, image_bytes, mime)`**：默认使用 `ANALYZE_MODEL=gemini-2.5-flash`（`temperature=0.4`），当遇到 `503`、`UNAVAILABLE` 或 `overloaded` 错误时按 `RETRY_DELAYS = [2, 5, 10]` 秒退避重试。
  - **API 端点清单**：
    - `GET /health`：返回 `{"status": "ok", "model": ...}`。
    - `POST /clarify`：节点 1 意图梳理与茬点分流（`temperature=0.6`）。
    - `POST /analyze`：上传图片文件分析（表单字段：`image`, `role: content|style`, `lang: zh|en`）。
    - `POST /analyze-url`：通过图片 URL 下载并分析（`urllib.request` 超时 15s，专供浏览器插件右键菜单调用）。
    - `POST /merge`：合并 `content_prompt` 与 `style_prompt`。
    - `POST /reverse`：服务端聚合反向提词接口（支持 `mode: both|content|style`）。
  - **静态托管**：当 `../frontend/public` 存在时，自动挂载到根路径 `/`，访问 `http://localhost:8765` 即进入 Web 界面。

- **`backend/prompts.py`**：
  - **单次调用双语输出契约**：`SYSTEM_PROMPT_CONTENT_BILINGUAL` 与 `SYSTEM_PROMPT_STYLE_BILINGUAL` 强制模型在单次响应中先后输出 `## ZH` 与 `## EN` 两个完整段落。
  - **`split_bilingual(full_response)`**：通过正则 `_ZH_BLOCK_RE` 和 `_EN_BLOCK_RE` 切分中英文段落。
  - **`extract_final_prompt(segment)` 四级兜底提取**：
    1. 匹配标准 ` ```prompt ... ``` ` 代码块；
    2. 匹配任意 ` ```...``` ` 代码块的最后一个；
    3. 从段落末尾逐行向上扫描自然语言行，遇到维度标记（`[`、`#`、`-`、`*`、`|`、数字编号、`[CONTENT-`、`[STYLE-`、`维度清单`）停止；
    4. 整段 `strip()` 兜底。
  - **`build_merged_prompt(content_prompt, style_prompt, lang)`**：剥离句尾标点后套入 `MERGE_TEMPLATE_ZH` 或 `MERGE_TEMPLATE_EN`。

### 2.2 Web 前端 (`frontend/public/index.html`)
- 单文件原生实现，无任何构建打包步骤或第三方前端框架依赖。
- **状态管理**：全局 `state` 对象维护 `clarify`、`content: {file, prompt, dim}`、`style: {file, prompt, dim}`、`reverse: {file}` 与 `lang: 'zh'|'en'`；服务地址保存在 `localStorage.getItem('artnode_server')`。
- **离线/容错兜底**：`mergePrompts()` 优先请求后端 `POST /merge`，若网络或服务异常则直接在前端按相同双语模板完成拼接。
- **注意细节**：
  - 初始 DOM 中 `#panel-clarify` 与 `#panel-content` 均带有 `active` 类（首屏同时展示意图梳理与内容解析），点击 `#pipeline` 中的 `.pnode` 节点会调用 `switchTab(name)` 切换为单面板激活状态。
  - 前端 `doReverse()` 目前直接在浏览器端按序请求 `/analyze`（`content` / `style`）与 `/merge`，后端同时保留了独立的 `/reverse` 接口。
  - 顶部栏的 `#api-key-input` 保存在 `localStorage.getItem('artnode_key')`，但目前后端统一从服务端环境变量 `GOOGLE_API_KEY` 读取密钥；如需支持客户端传入 Key，需前后端同步扩展请求头或表单字段。

### 2.3 浏览器扩展 (`extension/`)
- **通信链路**：
  1. 用户在网页图片上右键点击「📷 分析为内容图」或「🎨 分析为风格图」；
  2. `background.js` 将待分析项写入 `chrome.storage.local` 的 `artnode_queue[role]`，并向当前标签页发送 `artnode_ANALYZE` 消息；
  3. `content.js` 注入右下角浮窗 `#__artnode_panel`，再向 `background.js` 发送 `artnode_DO_ANALYZE`；
  4. `background.js` 调用后端 `POST /analyze-url`，将返回的 `final_prompt` 和 `dimension_text` 写回 `artnode_queue` 并通知浮窗展示；
  5. `popup.html` 通过 `chrome.storage.onChanged` 与 2 秒轮询实时同步 `artnode_queue` 状态，支持一键合并。

---

## 3. 启动、构建与验证命令

### 3.1 启动后端与 Web 界面
```powershell
cd backend
pip install -r requirements.txt
Copy-Item .env.example .env
# 在 .env 中填入真实的 GOOGLE_API_KEY（严禁提交 .env）
python main.py
```
- 默认监听地址：`http://0.0.0.0:8765`（开启 `reload=True`）。
- 浏览器访问：`http://localhost:8765`。

### 3.2 健康检查与接口自测
```powershell
# 1. 健康检查
curl http://localhost:8765/health

# 2. 测试提示词合并接口（无需消耗 Gemini 配额）
curl -X POST http://localhost:8765/merge `
  -F "content_prompt=一座破败的荒村古戏台，中远景微俯视" `
  -F "style_prompt=中式民俗悬疑厚涂，冷月光与暖煤油灯双色温对比" `
  -F "lang=zh"
```

### 3.3 重新生成浏览器扩展图标与加载扩展
```powershell
cd extension
python gen_icons.py
```
- 在 Chrome / Edge 打开 `chrome://extensions/` → 开启「开发者模式」→「加载已解压的扩展程序」→ 选择 `extension/` 目录。

---

## 4. 编码与维护规范

1. **提示词契约一致性**：
   - 修改 `backend/prompts.py` 中的维度定义时，必须遵守硬约束：内容图固定 **6 维**（零颜色/风格/媒介词），风格图固定 **7 维**（零具体物件名词），且 `## ZH` 必须在 `## EN` 之前，每段末尾必须带小写 ` ```prompt ` 代码块。
   - 若修改 `MERGE_TEMPLATE_ZH` / `MERGE_TEMPLATE_EN`，需同步检查 `frontend/public/index.html`、`extension/content.js` 与 `extension/popup.html` 中的本地离线合并兜底模板，保持三端一致。
2. **零构建依赖原则**：
   - `frontend/public/index.html` 与 `extension/` 保持原生 HTML/CSS/JS 单文件或轻量脚本结构，不要无故引入复杂的 npm 打包工具链。
3. **安全与隐私红线（零泄露原则）**：
   - **严禁提交真实密钥**：`backend/.env` 及任何真实的 `GOOGLE_API_KEY`（`AIza...`）绝不可进入 Git 暂存区；仓库仅保留 `backend/.env.example` 占位符。
   - **严禁提交个人隐私信息**：代码、注释、文档与 Commit Message 中不得出现个人真实姓名、私人邮箱、手机号、局域网/公网 IP 或带个人用户名的本机绝对路径。
4. **Git 提交规范**：
   - 遵循 Conventional Commits（`feat:`、`fix:`、`docs:`、`refactor:`、`chore:`）。
   - 提交前务必执行 `git status` 与 `git diff --cached`，确认无 `.env`、`__pycache__/`、临时测试图片或敏感凭据混入。
