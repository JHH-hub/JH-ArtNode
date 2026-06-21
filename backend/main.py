"""
ArtNode - FastAPI backend
"""
from __future__ import annotations

import base64
import io
import os
import time
from typing import Literal

from google import genai
from google.genai import types as genai_types
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from PIL import Image

from prompts import build_merged_prompt, extract_final_prompt, get_system_prompt, split_bilingual

load_dotenv()

app = FastAPI(title="ArtNode API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

RETRY_DELAYS = [2, 5, 10]
ALLOWED_MIME = {"image/png", "image/jpeg", "image/webp", "image/bmp", "image/gif"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024


def _get_client():
    api_key = os.getenv("GOOGLE_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=500, detail="GOOGLE_API_KEY not configured")
    return genai.Client(api_key=api_key)


def _compress_if_needed(image_bytes, mime):
    if len(image_bytes) <= 4 * 1024 * 1024:
        return image_bytes, mime
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue(), "image/jpeg"


async def _call_gemini(role, image_bytes, mime):
    client = _get_client()
    model_name = os.getenv("ANALYZE_MODEL", "gemini-2.5-flash")
    system_prompt = get_system_prompt(role)
    image_bytes, mime = _compress_if_needed(image_bytes, mime)

    last_err = None
    for attempt, delay in enumerate([-1] + RETRY_DELAYS):
        if attempt > 0:
            time.sleep(delay)
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[
                    genai_types.Content(
                        role="user",
                        parts=[
                            genai_types.Part(
                                inline_data=genai_types.Blob(
                                    mime_type=mime,
                                    data=base64.b64encode(image_bytes).decode(),
                                )
                            ),
                            genai_types.Part(text="Please analyze this image following your system instructions."),
                        ],
                    )
                ],
                config=genai_types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.4,
                ),
            )
            return response.text
        except Exception as e:
            last_err = e
            msg = str(e)
            if "503" in msg or "UNAVAILABLE" in msg.upper() or "overloaded" in msg.lower():
                continue
            raise HTTPException(status_code=502, detail=f"Gemini call failed: {msg}")
    raise HTTPException(status_code=503, detail=f"Gemini service unavailable: {last_err}")


@app.get("/health")
def health():
    return {"status": "ok", "model": os.getenv("ANALYZE_MODEL", "gemini-2.5-flash")}



@app.post("/clarify")
async def clarify(
    subject:     str = Form(...),
    style:       str = Form(""),
    mood:        str = Form(""),
    composition: str = Form(""),
    lighting:    str = Form(""),
    negative:    str = Form(""),
    extra:       str = Form(""),
    lang: Literal["zh", "en"] = Form("zh"),
):
    """
    Intent clarification: AI organizes the user's structured creative intent
    into a clear image description.
    """
    client = _get_client()
    model_name = os.getenv("ANALYZE_MODEL", "gemini-2.5-flash")

    fields = []
    fields.append("Subject: " + subject)
    if style:       fields.append("Style: " + style)
    if mood:        fields.append("Mood: " + mood)
    if composition: fields.append("Composition: " + composition)
    if lighting:    fields.append("Lighting: " + lighting)
    if negative:    fields.append("Exclude: " + negative)
    if extra:       fields.append("Extra: " + extra)

    user_input = "\n".join(fields)

    if lang == "zh":
        system = (
            "You are a professional AI art prompt consultant. "
            "The user provides creative intent in Chinese keywords. "
            "Reorganize into a fluent, clear Chinese scene description:\n"
            "1. Natural Chinese prose, under 150 characters\n"
            "2. Keep core intent, add reasonable details\n"
            "3. Structure: subject -> environment -> style/mood\n"
            "4. Output the description only, no extra explanations"
        )
    else:
        system = (
            "You are a professional AI art prompt consultant. "
            "The user provides creative intent keywords. "
            "Organize into a clear English scene description:\n"
            "1. Natural English prose, under 80 words\n"
            "2. Keep core intent, add reasonable details\n"
            "3. Structure: subject -> environment -> style/mood\n"
            "4. Output description only, no explanations"
        )

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=[genai_types.Content(role="user", parts=[genai_types.Part(text=user_input)])],
            config=genai_types.GenerateContentConfig(
                system_instruction=system,
                temperature=0.6,
            ),
        )
        result = response.text.strip()
    except Exception as e:
        raise HTTPException(status_code=502, detail="Gemini call failed: " + str(e))

    return {"result": result, "lang": lang}

@app.post("/analyze")
async def analyze(
    image: UploadFile = File(...),
    role: Literal["content", "style"] = Form(...),
    lang: Literal["zh", "en"] = Form("zh"),
):
    mime = image.content_type or "image/jpeg"
    if mime not in ALLOWED_MIME:
        raise HTTPException(status_code=400, detail=f"Unsupported image format: {mime}")
    image_bytes = await image.read()
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="Image exceeds 10MB")
    raw = await _call_gemini(role.upper(), image_bytes, mime)
    zh_seg, en_seg = split_bilingual(raw)
    segment = zh_seg if lang == "zh" else en_seg
    final_prompt = extract_final_prompt(segment)
    return {
        "role": role, "lang": lang,
        "raw_response": raw, "zh_segment": zh_seg, "en_segment": en_seg,
        "dimension_text": segment, "final_prompt": final_prompt,
    }


@app.post("/merge")
async def merge(
    content_prompt: str = Form(...),
    style_prompt: str = Form(...),
    lang: Literal["zh", "en"] = Form("zh"),
):
    if not content_prompt.strip() or not style_prompt.strip():
        raise HTTPException(status_code=400, detail="content_prompt and style_prompt are required")
    return {"merged_prompt": build_merged_prompt(content_prompt, style_prompt, lang), "lang": lang}


@app.post("/analyze-url")
async def analyze_url(
    image_url: str = Form(...),
    role: Literal["content", "style"] = Form(...),
    lang: Literal["zh", "en"] = Form("zh"),
):
    import urllib.request
    import urllib.error
    try:
        req = urllib.request.Request(image_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            image_bytes = resp.read()
            mime = resp.headers.get_content_type() or "image/jpeg"
    except urllib.error.URLError as e:
        raise HTTPException(status_code=400, detail=f"Failed to download image: {e}")
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="Image exceeds 10MB")
    raw = await _call_gemini(role.upper(), image_bytes, mime)
    zh_seg, en_seg = split_bilingual(raw)
    segment = zh_seg if lang == "zh" else en_seg
    final_prompt = extract_final_prompt(segment)
    return {
        "role": role, "lang": lang,
        "raw_response": raw, "zh_segment": zh_seg, "en_segment": en_seg,
        "dimension_text": segment, "final_prompt": final_prompt,
    }



@app.post("/reverse")
async def reverse(
    image: UploadFile = File(...),
    mode: Literal["both", "content", "style"] = Form("both"),
    lang: Literal["zh", "en"] = Form("zh"),
):
    """
    执行鸿沟辅助接口：上传目标效果图，反向生成可用提示词。
    mode=both   -> 同时分析内容+风格，合并为完整提示词
    mode=content -> 仅分析内容结构
    mode=style   -> 仅分析美术风格
    """
    mime = image.content_type or "image/jpeg"
    if mime not in ALLOWED_MIME:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {mime}")
    image_bytes = await image.read()
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="Image exceeds 10MB")

    content_prompt = style_prompt = ""

    if mode in ("both", "content"):
        raw_c = await _call_gemini("CONTENT", image_bytes, mime)
        zh_c, en_c = split_bilingual(raw_c)
        seg_c = zh_c if lang == "zh" else en_c
        content_prompt = extract_final_prompt(seg_c)

    if mode in ("both", "style"):
        raw_s = await _call_gemini("STYLE", image_bytes, mime)
        zh_s, en_s = split_bilingual(raw_s)
        seg_s = zh_s if lang == "zh" else en_s
        style_prompt = extract_final_prompt(seg_s)

    if mode == "both" and content_prompt and style_prompt:
        merged = build_merged_prompt(content_prompt, style_prompt, lang)
    elif mode == "content":
        merged = content_prompt
    else:
        merged = style_prompt

    return {
        "mode": mode, "lang": lang,
        "final_prompt": merged,
        "content_prompt": content_prompt,
        "style_prompt": style_prompt,
    }

_frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend", "public")
if os.path.isdir(_frontend_dir):
    app.mount("/", StaticFiles(directory=_frontend_dir, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8765, reload=True)