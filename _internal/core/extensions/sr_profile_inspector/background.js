// srkBrowser Profile Inspector - Background Service Worker

async function updateBadge() {
  try {
    const res = await fetch(chrome.runtime.getURL("profile_info.json"));
    if (!res.ok) return;
    const data = await res.json();
    
    let num = (data.number || "1").replace("Profile", "").replace("#", "").trim();
    if (num.length > 4) num = num.substring(0, 4);

    chrome.action.setBadgeText({ text: num });
    chrome.action.setBadgeBackgroundColor({ color: data.color || "#7c3aed" });
    if (chrome.action.setBadgeTextColor) {
      chrome.action.setBadgeTextColor({ color: "#ffffff" });
    }
    chrome.action.setTitle({ title: `srkBrowser • Profile #${num} (${data.name || 'Default'})` });
  } catch (err) {
    console.error("Inspector badge error:", err);
  }
}

chrome.runtime.onInstalled.addListener(() => {
  updateBadge();
});

chrome.runtime.onStartup.addListener(() => {
  updateBadge();
});

chrome.tabs.onActivated.addListener(() => {
  updateBadge();
});

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete') {
    updateBadge();
  }
});

// Run immediate update
updateBadge();
