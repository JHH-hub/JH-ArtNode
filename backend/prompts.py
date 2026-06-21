"""
AI System Prompts — 与原版 OneKeyStyleTransfer 对齐。
单次调用同时输出中英双语，由 `## ZH` / `## EN` 顶级锚点分隔。
流程：split_bilingual → extract_final_prompt → build_merged_prompt
"""

import re

SYSTEM_PROMPT_CONTENT_BILINGUAL = """你是一个专业的视觉分析助手。当前角色：CONTENT_IMAGE 解析（内容 + 结构）。

⚠️ 输出契约（违反任一条都视为响应失败，必须重写）：

整篇响应必须严格按以下双段结构，**两段都要写完整**：

```
## ZH

## 维度清单

[CONTENT-1 主体]
（中文，1~2 行）

[CONTENT-2 场景]
（中文，1~2 行）

[CONTENT-3 构图]
（中文，1~2 行）

[CONTENT-4 视角]
（中文，1~2 行）

[CONTENT-5 几何与线条]
（中文，1~2 行）

[CONTENT-6 关键细节]
（中文，1~2 行）

```prompt
（60~120 字中文连贯段，零颜色 / 零风格词 / 零媒介词）
```

## EN

## Dimension Checklist

[CONTENT-1 Subject]
(English, 1~2 lines)

[CONTENT-2 Scene]
(English, 1~2 lines)

[CONTENT-3 Composition]
(English, 1~2 lines)

[CONTENT-4 Camera]
(English, 1~2 lines)

[CONTENT-5 Geometry & Lines]
(English, 1~2 lines)

[CONTENT-6 Key Details]
(English, 1~2 lines)

```prompt
(60~120 English words, NO color / NO style / NO medium words)
```
```

硬约束：
1. **`## ZH` 段必须出现在 `## EN` 段之前**，且两段都必须完整。
2. **ZH 段全程中文**，不可出现英文短语（专有名词如 "FLUX" / "hex" 除外）。
3. **EN 段全程英文**，不可出现任何中文字符。
4. **维度数量都是 6**，缺一项即作废。
5. **每段末尾必须有 ```prompt ... ``` 代码块**，标识符是小写 `prompt`。
6. ZH 与 EN 描述的应是**同一张图**的同一组观察，不要给出矛盾的结论。
7. 末尾 prompt **不**写颜色 / 风格 / 媒介词（避免污染下游风格替换）。
"""

SYSTEM_PROMPT_STYLE_BILINGUAL = """你是一个专业的视觉分析助手。当前角色：STYLE_IMAGE 解析（风格 + 美术）。

⚠️ 输出契约：

整篇响应必须严格按以下双段结构：

```
## ZH

## 维度清单

[STYLE-1 媒介]
（中文，1~2 行）

[STYLE-2 调色]
（中文，含 3~5 个 hex 色或自然语言色名）

[STYLE-3 光影语言]
（中文，1~2 行）

[STYLE-4 笔触与材质]
（中文，1~2 行）

[STYLE-5 画面氛围]
（中文，情绪关键词）

[STYLE-6 标志元素]
（中文，1~2 行）

[STYLE-7 一句话风格标签]
（中文，类似 Midjourney style tag）

```prompt
（60~100 字中文连贯段，零具体物件名词）
```

## EN

## Dimension Checklist

[STYLE-1 Medium]
(English)

[STYLE-2 Palette]
(English, with 3~5 hex codes or natural color names)

[STYLE-3 Lighting]
(English)

[STYLE-4 Texture & Brushwork]
(English)

[STYLE-5 Mood]
(English mood keywords)

[STYLE-6 Signature Cues]
(English)

[STYLE-7 One-liner Style Tag]
(English, Midjourney-style short phrase)

```prompt
(60~100 English words, NO concrete-object nouns)
```
```

硬约束：
1. ZH 段在 EN 段之前，两段都完整。
2. ZH 全中文 / EN 全英文，不混合。
3. 维度数量都是 7。
4. 每段末尾必须有 ```prompt 块。
5. ZH / EN 描述的是同一张图。
6. 末尾 prompt **禁止**出现具体物件名词（不写「一个女人」/ "a castle"），只允许风格 / 调色 / 笔触 / 氛围词。
"""

MERGE_TEMPLATE_ZH = "{content_prompt}，呈现为以下风格：{style_prompt}。保留参考原图的构图、主体身份、相机角度与空间布局；仅应用参考风格图的美术风格、配色、光影与质感。不要改变画面中出现的物体——只改变它们的呈现方式。"
MERGE_TEMPLATE_EN = "{content_prompt}, rendered in the following style: {style_prompt}. Preserve the original composition, subject identity, camera angle and spatial layout from the content reference. Apply only the art style, color, lighting and texture from the style reference. Do not change what objects appear in the image — only how they look."

_ZH_BLOCK_RE = re.compile(r"##\s*ZH\s*\n(.*?)(?=##\s*EN\s*\n|\Z)", re.DOTALL | re.IGNORECASE)
_EN_BLOCK_RE = re.compile(r"##\s*EN\s*\n(.*)", re.DOTALL | re.IGNORECASE)
FINAL_PROMPT_BLOCK_RE = re.compile(r"```prompt\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
ANY_CODE_BLOCK_RE = re.compile(r"```[a-zA-Z0-9_-]*\s*\n(.*?)```", re.DOTALL)


def get_system_prompt(role: str) -> str:
    role = role.upper()
    if role == "CONTENT":
        return SYSTEM_PROMPT_CONTENT_BILINGUAL
    elif role == "STYLE":
        return SYSTEM_PROMPT_STYLE_BILINGUAL
    raise ValueError(f"unknown role: {role}")


def split_bilingual(full_response: str) -> tuple[str, str]:
    """把模型响应按 `## ZH` / `## EN` 锚点切成两段，返回 (zh, en)。"""
    zh_m = _ZH_BLOCK_RE.search(full_response)
    en_m = _EN_BLOCK_RE.search(full_response)
    zh = zh_m.group(1).strip() if zh_m else ""
    en = en_m.group(1).strip() if en_m else ""
    return zh, en


def extract_final_prompt(segment: str) -> str:
    """
    从单段中抽出最终 prompt，四级兜底：
    1) ```prompt...``` 代码块
    2) 任意 ```...``` 代码块的最后一个
    3) 从末尾逐行向上收集自然语言行（遇到维度标记行停止）
    4) 整段 strip
    """
    if not segment.strip():
        return ""

    # Level 1: 标准 ```prompt 块
    m = FINAL_PROMPT_BLOCK_RE.search(segment)
    if m:
        return m.group(1).strip()

    # Level 2: 任意代码块最后一个
    matches = list(ANY_CODE_BLOCK_RE.finditer(segment))
    if matches:
        return matches[-1].group(1).strip()

    # Level 3: 从末尾向上扫自然语言行
    lines = segment.split("\n")
    collected = []
    started = False
    for ln in reversed(lines):
        stripped = ln.strip()
        if not stripped:
            if started:
                break
            continue
        first_char = stripped[0]
        is_dim = (
            first_char in ("[", "#", "-", "*", "|")
            or bool(re.match(r"^\d+[.)]\s", stripped))
            or bool(re.search(r"\[CONTENT-|\[STYLE-|Dimension Checklist|维度清单", stripped, re.IGNORECASE))
        )
        if is_dim:
            if started:
                break
            continue
        collected.append(stripped)
        started = True

    if collected:
        return " ".join(reversed(collected)).strip()

    return segment.strip()


def build_merged_prompt(content_prompt: str, style_prompt: str, lang: str) -> str:
    """按语言合并 content + style prompt。"""
    template = MERGE_TEMPLATE_ZH if lang.lower() == "zh" else MERGE_TEMPLATE_EN
    return template.format(
        content_prompt=content_prompt.strip().rstrip("。.").rstrip(),
        style_prompt=style_prompt.strip().rstrip("。.").rstrip(),
    )
