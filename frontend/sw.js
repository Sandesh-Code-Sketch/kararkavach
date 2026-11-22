const CACHE = "kararkavach-shell-v5";
const SHELL = ["/", "/frontend/index.html", "/frontend/styles.css?v=5", "/frontend/app.js?v=5", "/frontend/manifest.json"];
self.addEventListener("install", (event) => event.waitUntil(
  caches.open(CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting())
));
self.addEventListener("activate", (event) => event.waitUntil(
  caches.keys()
    .then((keys) => Promise.all(keys.filter((key) => key.startsWith("kararkavach-shell-") && key !== CACHE).map((key) => caches.delete(key))))
    .then(() => self.clients.claim())
));
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.pathname.startsWith("/api/")) return;
  event.respondWith(fetch(event.request).then((response) => {
    if (response.ok && (url.pathname === "/" || url.pathname.startsWith("/frontend/") || url.pathname.startsWith("/assets/"))) {
      const copy = response.clone(); caches.open(CACHE).then((cache) => cache.put(event.request, copy));
    }
    return response;
  }).catch(async () => {
    const cached = await caches.open(CACHE).then((cache) => cache.match(event.request));
    if (cached) return cached;
    return Response.error();
  }));
});
