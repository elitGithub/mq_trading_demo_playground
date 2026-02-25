/** Pass backend connection info to the client for direct WebSocket. */
export function load() {
  return {
    backendPort: process.env.PUBLIC_BACKEND_PORT || '',
  };
}
