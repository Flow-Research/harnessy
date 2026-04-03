/**
 * PreToolUse hook — blocks writes to protected files during autonomous runs.
 *
 * Matches file paths against glob patterns from .jarvis/hooks.yaml.
 * Protected patterns like '_shared/*.py' prevent accidental modification
 * of shared infrastructure without explicit checkpoint approval.
 */

import { loadConfig } from './lib/config.mjs';

/**
 * Convert a simple glob pattern to a regex.
 * Supports * (any non-slash chars) and ** (any chars including slashes).
 */
function globToRegex(pattern) {
  let re = pattern
    .replace(/[.+^${}()|[\]\\]/g, '\\$&') // escape regex specials (except * and ?)
    .replace(/\*\*/g, '\0')                // placeholder for **
    .replace(/\*/g, '[^/]*')               // * matches within a single path segment
    .replace(/\0/g, '.*')                  // ** matches across segments
    .replace(/\?/g, '[^/]');               // ? matches single non-slash char
  return new RegExp(`(^|/)${re}$`);
}

async function main() {
  const raw = await new Promise((resolve) => {
    const chunks = [];
    process.stdin.on('data', (c) => chunks.push(c));
    process.stdin.on('end', () => resolve(Buffer.concat(chunks).toString()));
  });

  const payload = JSON.parse(raw);
  const filePath = payload.input?.file_path;

  if (!filePath) {
    process.stdout.write(JSON.stringify({ decision: 'allow' }));
    return;
  }

  const config = loadConfig();
  const patterns = config.protected_patterns || [];

  for (const pattern of patterns) {
    const regex = globToRegex(pattern);
    if (regex.test(filePath)) {
      process.stdout.write(JSON.stringify({
        decision: 'block',
        reason: `Protected file: ${pattern}. Checkpoint approval required.`,
      }));
      return;
    }
  }

  process.stdout.write(JSON.stringify({ decision: 'allow' }));
}

main().catch(() => {
  // On error, default to allow — don't block the agent on hook failures
  process.stdout.write(JSON.stringify({ decision: 'allow' }));
});
