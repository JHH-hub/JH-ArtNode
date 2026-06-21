// background.js — Service Worker
// 注册右键菜单，处理图片 URL 转发到 content script

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "artnode-content",
    title: "📷 分析为内容图 (CONTENT)",
    contexts: ["image"],
  });
  chrome.contextMenus.create({
    id: "artnode-style",
    title: "🎨 分析为风格图 (STYLE)",
    contexts: ["image"],
  });
  chrome.contextMenus.create({ id: "artnode-sep", type: "separator", contexts: ["image"] });
  chrome.contextMenus.create({
    id: "artnode-open",
    title: "🖥 打开风格迁移工具",
    contexts: ["action"],
  });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId === "artnode-open") {
    const { serverUrl = "http://localhost:8765" } = await chrome.storage.local.get("serverUrl");
    chrome.tabs.create({ url: serverUrl });
    return;
  }
  const role = info.menuItemId === "artnode-content" ? "content" : "style";
  const imageUrl = info.srcUrl;
  if (!imageUrl) return;

  // 存到 storage 供 popup 读取
  const existing = await chrome.storage.local.get(["artnode_queue"]);
  const queue = existing.artnode_queue || {};
  queue[role] = { url: imageUrl, status: "pending", prompt: "", dim: "" };
  await chrome.storage.local.set({ artnode_queue: queue });

  // 通知 content script 显示浮窗
  try {
    await chrome.tabs.sendMessage(tab.id, {
      type: "artnode_ANALYZE",
      role,
      imageUrl,
    });
  } catch (e) {
    // content script 不可用时 fallback：打开 popup
  }
});

// 监听来自 popup/content 的分析请求
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "artnode_DO_ANALYZE") {
    doAnalyze(msg.role, msg.imageUrl, msg.lang || "zh").then(sendResponse);
    return true; // async
  }
});

async function doAnalyze(role, imageUrl, lang) {
  const { serverUrl = "http://localhost:8765" } = await chrome.storage.local.get("serverUrl");
  try {
    const fd = new FormData();
    fd.append("image_url", imageUrl);
    fd.append("role", role);
    fd.append("lang", lang);
    const resp = await fetch(`${serverUrl}/analyze-url`, { method: "POST", body: fd });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: resp.statusText }));
      return { ok: false, error: err.detail || resp.statusText };
    }
    const data = await resp.json();
    // 缓存结果
    const existing = await chrome.storage.local.get(["artnode_queue"]);
    const queue = existing.artnode_queue || {};
    queue[role] = { url: imageUrl, status: "done", prompt: data.final_prompt, dim: data.dimension_text || "" };
    await chrome.storage.local.set({ artnode_queue: queue });
    return { ok: true, ...data };
  } catch (e) {
    return { ok: false, error: e.message };
  }
}
