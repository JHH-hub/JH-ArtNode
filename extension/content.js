// content.js — 注入到每个页面，显示分析浮窗

(function () {
  if (window.__artnode_injected) return;
  window.__artnode_injected = true;

  let panel = null;

  chrome.runtime.onMessage.addListener((msg) => {
    if (msg.type === "artnode_ANALYZE") {
      showPanel(msg.role, msg.imageUrl);
    }
  });

  function showPanel(role, imageUrl) {
    if (panel) panel.remove();

    panel = document.createElement("div");
    panel.id = "__artnode_panel";
    panel.style.cssText = `
      position: fixed; bottom: 24px; right: 24px; z-index: 2147483647;
      width: 340px; background: #1a1a1f; border: 1px solid #2e2e38;
      border-radius: 14px; padding: 16px; font-family: 'Inter','PingFang SC',sans-serif;
      color: #e8e8f0; box-shadow: 0 8px 40px rgba(0,0,0,.6);
      animation: artnode-slide-in .25s ease;
    `;

    const style = document.createElement("style");
    style.textContent = `
      @keyframes artnode-slide-in {
        from { opacity:0; transform: translateY(20px); }
        to   { opacity:1; transform: translateY(0); }
      }
      #__artnode_panel button {
        border: none; border-radius: 7px; padding: 7px 14px;
        cursor: pointer; font-size: 12px; font-weight: 600; transition: opacity .15s;
      }
      #__artnode_panel button:hover { opacity: .85; }
    `;
    document.head.appendChild(style);

    const roleName = role === "content" ? "内容图 CONTENT" : "风格图 STYLE";
    const roleColor = role === "content" ? "#60a5fa" : "#c084fc";

    panel.innerHTML = `
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:12px">
        <span style="font-size:16px">${role === "content" ? "📷" : "🎨"}</span>
        <strong style="font-size:13px">正在分析 <span style="color:${roleColor}">${roleName}</span></strong>
        <button id="__artnode_close" style="margin-left:auto;background:transparent;color:#7878a0;font-size:16px;padding:2px 6px">✕</button>
      </div>
      <div id="__artnode_thumb" style="margin-bottom:10px">
        <img src="${imageUrl}" style="max-width:100%;max-height:120px;border-radius:8px;object-fit:contain" />
      </div>
      <div id="__artnode_status" style="font-size:12px;color:#7878a0;margin-bottom:10px">
        ⏳ 正在请求分析…
      </div>
      <div id="__artnode_result" style="display:none">
        <div style="font-size:11px;color:#7878a0;margin-bottom:4px">提炼 Prompt</div>
        <div id="__artnode_prompt" style="font-size:13px;line-height:1.6;margin-bottom:10px;white-space:pre-wrap;word-break:break-all"></div>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
          <button id="__artnode_copy" style="background:#7c6ef5;color:#fff">📋 复制</button>
          <button id="__artnode_set_content" style="background:#1d3a5f;color:#60a5fa">设为内容图</button>
          <button id="__artnode_set_style" style="background:#2d1a47;color:#c084fc">设为风格图</button>
          <button id="__artnode_merge" style="background:#166534;color:#4ade80">⚡ 合并</button>
        </div>
      </div>
      <div id="__artnode_merge_result" style="display:none;margin-top:10px">
        <div style="font-size:11px;color:#7878a0;margin-bottom:4px">合并提示词</div>
        <div id="__artnode_merged_text" style="font-size:12px;line-height:1.6;white-space:pre-wrap;word-break:break-all;color:#a78bfa"></div>
        <button id="__artnode_copy_merged" style="margin-top:8px;background:#7c6ef5;color:#fff">📋 复制合并提示词</button>
      </div>
    `;
    document.body.appendChild(panel);

    panel.querySelector("#__artnode_close").onclick = () => panel.remove();

    // 触发分析
    chrome.runtime.sendMessage(
      { type: "artnode_DO_ANALYZE", role, imageUrl, lang: "zh" },
      (result) => {
        const statusEl = panel.querySelector("#__artnode_status");
        const resultEl = panel.querySelector("#__artnode_result");
        if (!result || !result.ok) {
          statusEl.textContent = "❌ 分析失败: " + (result?.error || "未知错误");
          statusEl.style.color = "#f87171";
          return;
        }
        statusEl.textContent = "✅ 分析完成";
        statusEl.style.color = "#4ade80";
        panel.querySelector("#__artnode_prompt").textContent = result.final_prompt || "（未提取到 prompt）";
        resultEl.style.display = "block";

        // 存当前 prompt
        panel.__currentRole = role;
        panel.__currentPrompt = result.final_prompt;
      }
    );

    // 按钮事件
    panel.addEventListener("click", async (e) => {
      const btn = e.target;
      if (btn.id === "__artnode_copy") {
        await navigator.clipboard.writeText(panel.__currentPrompt || "");
        showTip(btn, "已复制!");
      }
      if (btn.id === "__artnode_set_content" || btn.id === "__artnode_set_style") {
        const r = btn.id === "__artnode_set_content" ? "content" : "style";
        const q = await getQueue();
        q[r] = { url: imageUrl, status: "done", prompt: panel.__currentPrompt || "", dim: "" };
        await chrome.storage.local.set({ artnode_queue: q });
        showTip(btn, "已设置");
      }
      if (btn.id === "__artnode_merge") {
        const q = await getQueue();
        const cp = q["content"]?.prompt || "";
        const sp = q["style"]?.prompt || "";
        if (!cp || !sp) {
          showTip(btn, "需先设置两图!");
          return;
        }
        const merged = `${cp.replace(/[。.]+$/, "")}，呈现为以下风格：${sp.replace(/[。.]+$/, "")}。保留参考原图的构图、主体身份、相机角度与空间布局；仅应用参考风格图的美术风格、配色、光影与质感。不要改变画面中出现的物体——只改变它们的呈现方式。`;
        panel.querySelector("#__artnode_merged_text").textContent = merged;
        panel.querySelector("#__artnode_merge_result").style.display = "block";
        panel.__mergedPrompt = merged;
      }
      if (btn.id === "__artnode_copy_merged") {
        await navigator.clipboard.writeText(panel.__mergedPrompt || "");
        showTip(btn, "已复制!");
      }
    });
  }

  function showTip(btn, msg) {
    const orig = btn.textContent;
    btn.textContent = msg;
    setTimeout(() => (btn.textContent = orig), 1500);
  }

  async function getQueue() {
    const res = await chrome.storage.local.get(["artnode_queue"]);
    return res.artnode_queue || {};
  }
})();
