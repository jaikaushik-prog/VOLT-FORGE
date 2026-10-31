// Holds the Gemini key on the server. The browser only ever sees the answer.
import {SCHEMA, SYSTEM} from './_prompt.js';

const LIMIT_PER_MINUTE = 12;
const MAX_PROMPT = 120000;
const seen = new Map();

function tooMany(ip) {
  const now = Date.now(), recent = (seen.get(ip) || []).filter((t) => now - t < 60000);
  recent.push(now); seen.set(ip, recent);
  return recent.length > LIMIT_PER_MINUTE;
}

export default async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).json({error: 'Use POST.'});
  const origin = req.headers.origin;
  if (origin && new URL(origin).host !== req.headers.host) return res.status(403).json({error: 'This AI only serves the VOLT-FORGE app.'});
  const key = process.env.GEMINI_API_KEY;
  if (!key) return res.status(503).json({error: 'The AI is not connected yet.'});
  if (tooMany(String(req.headers['x-forwarded-for'] || '').split(',')[0])) return res.status(429).json({error: 'Too many AI requests. Wait a minute and try again.'});
  const prompt = req.body?.prompt;
  if (typeof prompt !== 'string' || !prompt || prompt.length > MAX_PROMPT) return res.status(400).json({error: 'That request is too large for the AI.'});
  try {
    const response = await fetch('https://generativelanguage.googleapis.com/v1beta/interactions', {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'x-goog-api-key': key},
      body: JSON.stringify({
        model: process.env.GEMINI_MODEL || 'gemini-3.8-flash',
        input: `${SYSTEM}\n\n${prompt}`,
        store: false,
        generation_config: {max_output_tokens: 1500},
        response_format: {type: 'text', mime_type: 'application/json', schema: SCHEMA},
      }),
    });
    if (response.status === 429) return res.status(429).json({error: 'The free AI limit has been reached. Try again later.'});
    if (!response.ok) return res.status(502).json({error: 'The AI could not answer. Please try again.'});
    const value = await response.json();
    const text = value.steps?.find((s) => s.type === 'model_output')?.content?.find((c) => c.type === 'text')?.text;
    if (!text) return res.status(502).json({error: 'The AI returned an empty answer. Please try again.'});
    return res.status(200).json({text});
  } catch {
    return res.status(502).json({error: 'The AI could not be reached. Please try again.'});
  }
}
