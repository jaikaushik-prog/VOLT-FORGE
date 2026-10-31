// Runs the same Python engine as the local app, using WebAssembly.
importScripts('https://cdn.jsdelivr.net/pyodide/v0.27.7/full/pyodide.js');

async function start() {
  postMessage({progress: 'Loading the real simulator into your browser. The first time takes about 15 seconds.'});
  const pyodide = await loadPyodide();
  await pyodide.loadPackage(['numpy', 'scipy', 'pandas']);
  const archive = await fetch('./engine.zip').then((r) => r.arrayBuffer());
  pyodide.unpackArchive(archive, 'zip', {extractDir: '/home/pyodide/volt'});
  pyodide.runPython("import sys; sys.path[:0] = ['/home/pyodide/volt', '/home/pyodide/volt/src']");
  postMessage({progress: 'Starting your private workspace…'});
  return {pyodide, bridge: pyodide.pyimport('bridge')};
}

async function ask(prompt) {
  try {
    const response = await fetch('/api/ai', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({prompt})});
    const value = await response.json();
    return response.ok ? {text: value.text} : {error: value.error || 'The AI could not answer. Please try again.'};
  } catch {
    return {error: 'The AI could not be reached. Check your connection and try again.'};
  }
}

const ready = start();
onmessage = async ({data}) => {
  const {pyodide, bridge} = await ready;
  if (data.path.startsWith('/api/studio/export/')) {
    await pyodide.loadPackage('matplotlib');
    bridge.real_plots();
  }
  const call = (reply) => JSON.parse(bridge.handle(data.path, data.method, data.body, reply ? JSON.stringify(reply) : null));
  let answer = call(null);
  if (answer.ai_prompt) answer = call(await ask(answer.ai_prompt));
  postMessage({id: data.id, ...answer});
};
