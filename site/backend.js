// Answers the app's /api calls from a worker running the real Python engine.
(() => {
  const worker = new Worker('./worker.js');
  const pending = new Map();
  let nextId = 0;
  worker.onmessage = ({data}) => {
    if (data.progress) {
      const line = document.querySelector('.loading-screen p');
      if (line) line.textContent = data.progress;
      return;
    }
    const done = pending.get(data.id);
    pending.delete(data.id);
    if (done) done(data);
  };
  const browserFetch = window.fetch.bind(window);
  window.fetch = (url, options = {}) => {
    const path = typeof url === 'string' ? url : url.url;
    if (!path.startsWith('/api/')) return browserFetch(url, options);
    return new Promise((resolve) => {
      const id = ++nextId;
      pending.set(id, ({status, type, body, binary}) => {
        const content = binary ? Uint8Array.from(atob(body), (c) => c.charCodeAt(0)) : body;
        resolve(new Response(content, {status, headers: {'Content-Type': type}}));
      });
      worker.postMessage({id, path, method: options.method || 'GET', body: options.body || null});
    });
  };
})();
