/* Service worker «СМП Справочник».
   Схема: при первом открытии страница целиком кладётся в кэш (офлайн сразу готов);
   дальше сеть в приоритете (свежая версия по ссылке), но если сеть отвечает дольше
   ~2,5 с (слабый сигнал в машине) — мгновенно отдаётся копия из кэша, а свежая версия
   докачивается в фоне для следующего запуска. Для обновления приложения достаточно
   заменить index.html на хостинге — этот файл менять не нужно. */
const CACHE = "spravochnik-cache";
const PAGE = "index.html";
const CORE = [PAGE, "manifest.webmanifest", "icons/icon-192.png", "icons/icon-512.png",
              "icons/icon-maskable-512.png", "icons/apple-touch-icon.png"];
const SLOW_MS = 2500;

const pageKey = () => new URL(PAGE, self.registration.scope).href;

self.addEventListener("install", e => {
  e.waitUntil(
    caches.open(CACHE)
      .then(c => Promise.all(CORE.map(u => c.add(new Request(u, { cache: "reload" })))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys()
      .then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  const nav = req.mode === "navigate";
  const key = nav ? pageKey() : req;
  const fromCache = () => caches.match(key, { ignoreSearch: true });

  const net = fetch(req).then(r => {
    if (r && r.ok) {
      const copy = r.clone();
      e.waitUntil(caches.open(CACHE).then(c => c.put(key, copy)).catch(() => {}));
    }
    return r;
  });
  e.waitUntil(net.catch(() => {}));

  const slow = new Promise(resolve => {
    setTimeout(() => fromCache().then(r => { if (r) resolve(r); }), SLOW_MS);
  });

  e.respondWith(
    Promise.race([net, slow]).catch(() => fromCache().then(r => r || Response.error()))
  );
});
