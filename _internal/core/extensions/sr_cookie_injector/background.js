chrome.runtime.onInstalled.addListener(() => {
    injectCookies();
});

chrome.runtime.onStartup.addListener(() => {
    injectCookies();
});

injectCookies();

async function injectCookies() {
    try {
        const url = chrome.runtime.getURL("cookies_payload.json");
        const resp = await fetch(url);
        if (!resp.ok) return;

        const data = await resp.json();

        // 1. Structured Multi-Domain Cookies List (Supports Gmail, Netflix, TikTok, Twitter/X, Amazon, Discord, etc.)
        if (Array.isArray(data.cookies) && data.cookies.length > 0) {
            for (const ck of data.cookies) {
                if (!ck.name || !ck.value) continue;
                const domain = ck.domain || "";
                const cleanDomain = domain.replace(/^\./, "");
                if (!cleanDomain) continue;

                const targetUrl = `https://${cleanDomain}${ck.path || "/"}`;
                const cookieObj = {
                    url: targetUrl,
                    name: ck.name,
                    value: ck.value,
                    path: ck.path || "/",
                    secure: ck.secure !== undefined ? Boolean(ck.secure) : true,
                    httpOnly: ck.httpOnly !== undefined ? Boolean(ck.httpOnly) : false,
                    expirationDate: Math.floor(Date.now() / 1000) + (365 * 86400)
                };
                if (domain.startsWith(".")) {
                    cookieObj.domain = domain;
                }
                await chrome.cookies.set(cookieObj).catch(() => {});
            }
            console.log("srkBrowser: Multi-domain cookies injected successfully for all sites!");
            return;
        }

        // 2. Fallback to Raw Cookie String Parser
        const cookieStr = data.cookie || "";
        if (!cookieStr || cookieStr.trim().length === 0) return;

        const items = cookieStr.split(";");
        for (const item of items) {
            if (!item.includes("=")) continue;
            const idx = item.indexOf("=");
            const name = item.substring(0, idx).trim();
            const val = item.substring(idx + 1).trim();

            if (!name || !val) continue;

            const isFB = name.match(/^(c_user|cuser|xs|fr|datr|sb|presence|wd|locale|dpr|fbl_ci|fbl_st|fbl_cs|pas|ps_l|ps_n|checkpoint)$/i) || cookieStr.includes("c_user=") || cookieStr.includes("cuser=");
            const isGoogle = name.match(/^(SID|HSID|SSID|APISID|SAPISID|__Secure|NID|1P_JAR)/i);
            const domain = isFB ? ".facebook.com" : (isGoogle ? ".google.com" : "");
            const targetUrl = isFB ? "https://www.facebook.com/" : (isGoogle ? "https://www.google.com/" : "https://www.facebook.com/");

            try {
                const cookieObj = {
                    url: targetUrl,
                    name: name,
                    value: val,
                    path: "/",
                    secure: true,
                    expirationDate: Math.floor(Date.now() / 1000) + (365 * 86400)
                };
                if (domain) {
                    cookieObj.domain = domain;
                }
                await chrome.cookies.set(cookieObj).catch(() => {});
            } catch (err) {}
        }
        console.log("srkBrowser Cookies injected successfully!");
    } catch (e) {
        console.error("srkBrowser Cookie Injector Exception:", e);
    }
}
