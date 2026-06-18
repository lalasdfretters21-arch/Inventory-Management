const CACHE_NAME = 'inventory-app-v1';
const urlsToCache = [
    '/',
    '/static/app.js',
    '/static/manifest.json'
];

// Install Service Worker
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => {
                return cache.addAll(urlsToCache);
            })
            .catch(error => {
                console.log('Cache addAll error:', error);
            })
    );
    self.skipWaiting();
});

// Activate Service Worker
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cacheName => {
                    if (cacheName !== CACHE_NAME) {
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
    self.clients.claim();
});

// Fetch Event - Network First Strategy
self.addEventListener('fetch', event => {
    // Skip non-GET requests
    if (event.request.method !== 'GET') {
        return;
    }

    // Skip requests to api endpoints - they have their own logic
    if (event.request.url.includes('/api/')) {
        event.respondWith(networkFirst(event.request));
        return;
    }

    // For static assets, use cache first
    event.respondWith(cacheFirst(event.request));
});

// Network First Strategy (for API calls)
async function networkFirst(request) {
    try {
        const response = await fetch(request);
        if (response.ok) {
            // Cache successful API responses
            const cache = await caches.open(CACHE_NAME);
            cache.put(request, response.clone());
        }
        return response;
    } catch (error) {
        // Fall back to cache if network fails
        const cached = await caches.match(request);
        if (cached) {
            return cached;
        }
        
        // Return a custom offline response
        return new Response(
            JSON.stringify({ error: 'Offline - using cached data' }),
            {
                status: 503,
                statusText: 'Service Unavailable',
                headers: new Headers({ 'Content-Type': 'application/json' })
            }
        );
    }
}

// Cache First Strategy (for static assets)
async function cacheFirst(request) {
    const cached = await caches.match(request);
    if (cached) {
        return cached;
    }

    try {
        const response = await fetch(request);
        if (response.ok) {
            const cache = await caches.open(CACHE_NAME);
            cache.put(request, response.clone());
        }
        return response;
    } catch (error) {
        return new Response('Offline - Resource not available', {
            status: 503,
            statusText: 'Service Unavailable'
        });
    }
}

// Background Sync
self.addEventListener('sync', event => {
    if (event.tag === 'sync-inventory') {
        event.waitUntil(syncInventory());
    }
});

async function syncInventory() {
    try {
        // Attempt to sync pending changes
        const cache = await caches.open(CACHE_NAME);
        const requests = await cache.keys();
        
        for (const request of requests) {
            try {
                await fetch(request.clone());
            } catch (error) {
                console.log('Sync error:', error);
            }
        }
    } catch (error) {
        console.log('Background sync failed:', error);
    }
}

// Push Notifications
self.addEventListener('push', event => {
    const options = {
        body: event.data ? event.data.text() : 'Inventory notification',
        icon: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 192 192"><rect fill="%232c3e50" width="192" height="192"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" font-size="120" fill="white" font-weight="bold">📦</text></svg>',
        badge: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 192 192"><rect fill="white" width="192" height="192"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" font-size="120" fill="%232c3e50" font-weight="bold">📦</text></svg>'
    };

    event.waitUntil(
        self.registration.showNotification('IT Inventory System', options)
    );
});

// Notification Click
self.addEventListener('notificationclick', event => {
    event.notification.close();
    
    event.waitUntil(
        clients.matchAll({ type: 'window' }).then(clientList => {
            // Check if app is already open
            for (let i = 0; i < clientList.length; i++) {
                const client = clientList[i];
                if (client.url === '/' && 'focus' in client) {
                    return client.focus();
                }
            }
            // Open app if not already open
            if (clients.openWindow) {
                return clients.openWindow('/');
            }
        })
    );
});
