self.addEventListener('install', e => self.skipWaiting());

self.addEventListener('activate', e => {
    e.waitUntil(
        caches.keys().then(keys => Promise.all(keys.map(k => caches.delete(k))))
    );
    self.clients.claim();
});

// 캐시 완전 미사용
self.addEventListener('fetch', e => {
    e.respondWith(fetch(e.request, { cache: 'no-store' }).catch(() => new Response('offline')));
});

// 푸시 알림
self.addEventListener('push', e => {
    let data = { title: '🌂 동백 우산', body: '새 알림이 있습니다.' };
    try { data = e.data.json(); } catch(err) {}
    e.waitUntil(
        self.registration.showNotification(data.title, {
            body: data.body,
            icon: '/static/icon-192.png',
            badge: '/static/icon-192.png',
            vibrate: [200, 100, 200],
            tag: 'umbrella-alert',
            renotify: true
        })
    );
});

self.addEventListener('notificationclick', e => {
    e.notification.close();
    e.waitUntil(clients.openWindow('/admin?pass=0927'));
});
