/**
 * PostToolUse hook — detects gate passage via trace_capture.py and sends notifications.
 *
 * Watches for Bash commands that invoke trace_capture.py capture, extracts
 * the --gate and --outcome flags, and notifies via desktop/webhook.
 */

import { loadConfig } from './lib/config.mjs';
import { notify } from './lib/notify.mjs';

function extractFlag(command, flag) {
  // Match --flag value or --flag=value
  const pattern = new RegExp(`${flag}[=\\s]+([^\\s]+)`);
  const match = command.match(pattern);
  return match ? match[1] : null;
}

async function main() {
  const raw = await new Promise((resolve) => {
    const chunks = [];
    process.stdin.on('data', (c) => chunks.push(c));
    process.stdin.on('end', () => resolve(Buffer.concat(chunks).toString()));
  });

  const payload = JSON.parse(raw);
  const command = payload.input?.command || '';

  if (!command.includes('trace_capture.py capture')) {
    process.stdout.write('{}');
    return;
  }

  const gate = extractFlag(command, '--gate') || 'unknown';
  const outcome = extractFlag(command, '--outcome') || 'unknown';
  const message = `Issue gate: ${gate} — ${outcome}`;

  const config = loadConfig();
  await notify('Harnessy Gate', message, config);

  process.stdout.write('{}');
}

main().catch(() => {
  // PostToolUse hooks must never crash — just emit empty response
  process.stdout.write('{}');
});
