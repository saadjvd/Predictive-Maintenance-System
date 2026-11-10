/**
 * Cloudflare Pages Advanced Mode Worker
 * Provides edge-level API proxying to Cloudflare Quick Tunnel backend
 * and serves static assets via env.ASSETS.
 */
export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // 1. Edge Proxy to Cloudflare Quick Tunnel backend
    if (url.pathname.startsWith('/api/')) {
      const targetUrl = new URL(url.pathname + url.search, 'https://wed-thousands-kelkoo-centuries.trycloudflare.com');
      const modifiedRequest = new Request(targetUrl.toString(), request);
      modifiedRequest.headers.set('Host', 'wed-thousands-kelkoo-centuries.trycloudflare.com');
      return fetch(modifiedRequest);
    }

    // 2. Client-side SPA routing fallback for dynamic equipment details
    if (url.pathname.startsWith('/dashboard/equipment/') && !url.pathname.includes('.')) {
      const fallbackUrl = new URL('/dashboard/equipment/default.html', request.url);
      return env.ASSETS.fetch(new Request(fallbackUrl.toString(), request));
    }

    // 3. Fallback to serving static assets
    return env.ASSETS.fetch(request);
  },
};
