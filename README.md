# ArtNode — Web + 浏览器插件版

> 原版 Python GUI 工具的 Web 复刻，保持核心提示词逻辑完全一致。

## 核心决策节点功能（5 节点流水线）

- **节点 1 — 💬 意图梳理与茬点分流 (`/clarify`)**：将策划模糊剧本与茬点清单拆分为**「底图直出静态茬点」**与**「后期局部重绘 / 需拆解 Spine 动态层的动态茬点」**，强制执行移动端 9:16 安全区约束（纵向 15%~85%），并为动态层预留干净的物理承载面与受光反射锚点（或保持独立轮廓不穿模）。
- **节点 2 — 🖼 内容图 6 维解析 (`/analyze` role=content)**：提取主体、场景、构图（含 9:16 安全区分布与非对称纵深）、视角、几何线条、关键细节（含拆层隔离关系）共 6 个维度（零颜色/风格词污染）。
- **节点 3 — 🎨 风格图 7 维解析 (`/analyze` role=style)**：提取媒介、调色、光影语言、笔触材质、画面氛围、标志元素、一句话风格标签共 7 个维度（零具体物件名词污染）。
- **节点 4 — ⚡ 提示词合并 (`/merge`)**：按中英双语结构保留模板拼合 6 维内容与 7 维风格，直接用于 SD / MJ / FLUX / Gemini 生图。
- **节点 5 — 🔍 反向提词 (`/reverse`)**：跨越执行鸿沟（Gulf of Execution），支持对草图或参考图执行内容/风格解耦反向提词。
- **Web 版 + 浏览器插件**：支持拖拽上传分析及网页右键任意图片浮窗分析与一键复制。

---

## 快速开始

### 1. 后端服务

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env，填入你的 Gemini API Key
python main.py
```

服务启动在 `http://localhost:8765`，同时托管前端页面。

### 2. 访问 Web 工具

打开浏览器访问 `http://localhost:8765`

### 3. 安装浏览器插件

1. 先生成图标：
   ```bash
   cd extension
   python gen_icons.py
   ```
2. Chrome / Edge 打开 `chrome://extensions/`
3. 开启「开发者模式」
4. 点「加载已解压的扩展程序」，选择 `extension/` 目录

---

## 目录结构

```
ArtNode_web/
├── backend/
│   ├── main.py          # FastAPI 服务入口
│   ├── prompts.py       # 提示词逻辑（从原项目复刻）
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   └── public/
│       └── index.html   # Web 工具页面（单文件无依赖）
└── extension/
    ├── manifest.json
    ├── background.js    # Service Worker + 右键菜单
    ├── content.js       # 页面浮窗注入
    ├── popup.html       # 插件弹出面板
    ├── gen_icons.py     # 图标生成脚本
    └── icons/           # 生成后的图标
```

---

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/analyze` | 上传图片分析（multipart: image, role, lang） |
| POST | `/analyze-url` | 通过 URL 分析图片（供插件使用） |
| POST | `/merge` | 合并 content+style prompt |
| GET  | `/health` | 健康检查 |

---

## 提示词流程（与原版对齐）

```
图片 → Gemini 分析 → 双语响应
  └── split_bilingual()      按 ## ZH / ## EN 切割
  └── extract_final_prompt() 提取 ```prompt 块（四级兜底）
  └── build_merged_prompt()  套入合并模板
```

---

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `GOOGLE_API_KEY` | — | Gemini API Key（必填） |
| `ANALYZE_MODEL` | `gemini-2.5-flash` | 分析模型 |
