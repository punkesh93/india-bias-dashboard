const V = "mp-202611261524";
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys()
    .then((ks) => Promise.all(ks.filter((k) => k !== V).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin === location.origin) {
    const key = url.pathname.includes("/data/") ? url.origin + url.pathname : req;
    e.respondWith(
      fetch(req, { cache: "no-cache" })
        .then((res) => { if (res.ok) { const copy = res.clone(); caches.open(V).then((c) => c.put(key, copy)); } return res; })
        .catch(() => caches.match(key))
    );
    return;
  }
  e.respondWith(caches.match(req).then((hit) => hit || fetch(req).then((res) => {
    const copy = res.clone(); caches.open(V).then((c) => c.put(req, copy)); return res;
  })));
});
