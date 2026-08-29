// Service worker mínimo: cachea el shell estático para que la PWA sea
// instalable y arranque más rápido en visitas repetidas. No cachea rutas
// dinámicas (pedidos, login, etc.) porque los datos siempre deben venir
// frescos del servidor.
const CACHE = "al-toque-shell-v1";
const SHELL = [
  "/static/css/style.css",
  "/static/img/logo.svg",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)));
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

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);
  if (!SHELL.includes(url.pathname)) return;
  event.respondWith(
    caches.match(event.request).then((cached) => cached || fetch(event.request))
  );
});
