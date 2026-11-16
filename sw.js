/* TG di Famiglia – service worker
   - interfaccia e sigla: in cache (funzionano anche offline)
   - data/grezzo.json: sempre dalla rete (network-first), copia di riserva in cache
   - richieste ad altri siti (Gemini, podcast, radio): non toccate */
const CACHE = 'tg-famiglia-v1';
const GUSCIO = ['./', 'index.html', 'manifest.json', 'assets/sigla.mp3',
  'icons/icon-192.png', 'icons/icon-512.png', 'icons/apple-touch-icon.png'];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(GUSCIO)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys()
    .then((k) => Promise.all(k.filter((n) => n !== CACHE).map((n) => caches.delete(n))))
    .then(() => self.clients.claim()));
});

async function reteDiPrima(req) {
  const c = await caches.open(CACHE);
  try {
    const r = await fetch(req, { cache: 'no-store' });
    if (r.ok) c.put(req, r.clone());
    return r;
  } catch (e) {
    const salvata = await c.match(req, { ignoreSearch: true });
    if (salvata) return salvata;
    throw e;
  }
}
async function cacheDiPrima(req) {
  const c = await caches.open(CACHE);
  const salvata = await c.match(req, { ignoreSearch: true });
  if (salvata) return salvata;
  const r = await fetch(req);
  if (r.ok && r.status === 200) c.put(req, r.clone());
  return r;
}

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;          // Gemini, podcast, radio: rete diretta
  if (req.headers.has('range')) return;                      // lascia gestire l'audio al browser
  if (url.pathname.endsWith('/data/grezzo.json')) { e.respondWith(reteDiPrima(req)); return; }
  // pagina: rete di prima, così gli aggiornamenti arrivano subito; offline usa la copia
  if (req.mode === 'navigate' || url.pathname.endsWith('/index.html') || url.pathname.endsWith('/')) {
    e.respondWith(reteDiPrima(req).catch(() => caches.match('index.html'))); return;
  }
  e.respondWith(cacheDiPrima(req));
});
