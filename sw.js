self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => {
  e.waitUntil(
    self.clients.claim()
      .then(() => caches.keys())
      .then(keys => Promise.all(keys.map(k => caches.delete(k))))
      .then(() => self.clients.matchAll({ includeUncontrolled: true, type: 'window' }))
      .then(clients => {
        clients.forEach(c => c.navigate(c.url));
        return self.registration.unregister();
      })
  );
});
