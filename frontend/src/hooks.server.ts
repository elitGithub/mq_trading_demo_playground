/** Server-side proxy: forwards /api requests to the backend container. */
import type { Handle } from '@sveltejs/kit';

const BACKEND_URL = process.env.BACKEND_URL || 'http://backend:8000';

export const handle: Handle = async ({ event, resolve }) => {
  if (event.url.pathname.startsWith('/api/')) {
    const target = `${BACKEND_URL}${event.url.pathname}${event.url.search}`;

    const res = await fetch(target, {
      method: event.request.method,
      headers: event.request.headers,
      body: event.request.method !== 'GET' && event.request.method !== 'HEAD'
        ? await event.request.text()
        : undefined,
    });

    return new Response(res.body, {
      status: res.status,
      statusText: res.statusText,
      headers: res.headers,
    });
  }

  return resolve(event);
};
