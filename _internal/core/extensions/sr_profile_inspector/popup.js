// srkBrowser Profile Inspector Popup Logic

document.addEventListener("DOMContentLoaded", async () => {
  try {
    const res = await fetch(chrome.runtime.getURL("profile_info.json"));
    if (res.ok) {
      const data = await res.json();
      
      const num = (data.number || "01").replace("Profile", "").replace("#", "").trim();
      document.getElementById("profBadge").innerText = `#${num}`;
      document.getElementById("profName").innerText = data.name || `Profile ${num}`;
      document.getElementById("profGroup").innerText = data.group || "Default";

      const pType = data.proxy_type || "None";
      document.getElementById("proxyType").innerText = pType === "None" ? "Direct Connection" : pType;
      
      if (data.proxy_host && data.proxy_port) {
        document.getElementById("proxyHost").innerText = `${data.proxy_host}:${data.proxy_port}`;
      } else {
        document.getElementById("proxyHost").innerText = "Local Network (Direct)";
      }
    }
  } catch (e) {
    console.error("Failed to load profile info:", e);
  }

  document.getElementById("btnCheckIP").addEventListener("click", () => {
    chrome.tabs.create({ url: "https://ipinfo.io" });
  });

  document.getElementById("btnWebRTC").addEventListener("click", () => {
    chrome.tabs.create({ url: "https://browserleaks.com/webrtc" });
  });

  document.getElementById("btnClearCache").addEventListener("click", () => {
    if (chrome.browsingData) {
      chrome.browsingData.removeCache({}, () => {
        const btn = document.getElementById("btnClearCache");
        btn.innerText = "✓ Cleared!";
        btn.style.borderColor = "#10b981";
        btn.style.color = "#10b981";
        setTimeout(() => {
          btn.innerText = "🧹 Clear Cache";
          btn.style.borderColor = "#45475a";
          btn.style.color = "#ffffff";
        }, 1800);
      });
    }
  });
});
