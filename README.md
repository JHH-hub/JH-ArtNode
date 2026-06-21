# ArtNode — Web + 浏览器插件版

> 原版 Python GUI 工具的 Web 复刻，保持核心提示词逻辑完全一致。

## 功能

- **内容图分析**：提取构图、主体、视角等 6 个维度
- **风格图分析**：提取媒介、调色、光影、笔触等 7 个维度  
- **合并提示词**：按中英双语模板拼合，直接用于 SD / MJ / FLUX
- **Web 版**：拖拽上传，本地运行
- **浏览器插件**：右键任意网页图片 → 分析 → 浮窗显示 prompt → 一键复制

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
