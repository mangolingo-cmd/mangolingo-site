// MangaVerse — minimal service worker for installability + offline shell.
// Strategy: network-first for HTML/API, cache-first for static assets.

const CACHE = "mangaverse-v2";
const SHELL = ["/", "/manifest.json", "/icons/icon-192.png", "/icons/icon-512.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(SHELL).catch(() => {}))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Handle messages from the page (e.g., to show a notification when a new chapter
// is detected via in-app polling — the page calls navigator.serviceWorker.controller.postMessage).
self.addEventListener("message", (event) => {
  const data = event.data || {};
  if (data.type === "show-notification") {
    const title = data.title || "MangaVerse";
    const options = {
      body: data.body || "",
      icon: "/icons/icon-192.png",
      badge: "/icons/icon-192.png",
      tag: data.tag || "new-chapter",
      data: { url: data.url || "/" },
      dir: "rtl",
      lang: "ar",
    };
    event.waitUntil(self.registration.showNotification(title, options));
  }
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || "/";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((wins) => {
      for (const w of wins) {
        if (w.url.includes(url) && "focus" in w) return w.focus();
      }
      return self.clients.openWindow ? self.clients.openWindow(url) : null;
    })
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);

  // Never cache API or proxy responses — always go to network.
  if (url.pathname.startsWith("/api/")) return;

  // Cache-first for static assets (JS/CSS/images), network-first otherwise.
  const isStatic = /\.(?:js|css|woff2?|ttf|png|jpg|jpeg|gif|webp|svg|ico)$/.test(url.pathname);

  if (isStatic) {
    event.respondWith(
      caches.match(req).then((cached) => {
        if (cached) return cached;
        return fetch(req).then((res) => {
          if (res && res.status === 200 && res.type === "basic") {
            const clone = res.clone();
            caches.open(CACHE).then((c) => c.put(req, clone));
          }
          return res;
        }).catch(() => cached);
      })
    );
    return;
  }

  // Network-first for navigations.
  event.respondWith(
    fetch(req)
      .then((res) => {
        if (req.mode === "navigate" && res && res.status === 200) {
          const clone = res.clone();
          caches.open(CACHE).then((c) => c.put(req, clone));
        }
        return res;
      })
      .catch(() => caches.match(req).then((c) => c || caches.match("/")))
  );
});
