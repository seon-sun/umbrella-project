const CACHE_NAME = 'dongbaek-admin-v2';

self.addEventListener('install', event => {
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// 캐싱 완전 비활성화 - 항상 네트워크에서 가져옴
self.addEventListener('fetch', event => {
  event.respondWith(fetch(event.request));
});
