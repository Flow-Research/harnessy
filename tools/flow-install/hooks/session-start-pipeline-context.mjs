/**
 * SessionStart hook — injects pipeline status into the conversation context.
 *
 * Reads autoflow pool and goal-agent state files to build a brief summary
 * of active pipeline work. Outputs {} when nothing is running.
 */

import { readFileSync, readdirSync, statSync } from 'node:fs';
import { resolve, join } from 'node:path';

function readJson(path) {
  try {
    return JSON.parse(readFileSync(path, 'utf-8'));
  } catch {
    return null;
  }
}

function getAutoflowSummary(root) {
  const pool = readJson(resolve(root, '.jarvis', 'context', 'autoflow', 'pool.json'));
  if (!pool || !Array.isArray(pool.issues)) return null;

  const active = pool.issues.filter((i) => i.status === 'active').length;
  const waiting = pool.issues.filter((i) => i.status === 'waiting' || i.status === 'gate_blocked').length;
  const total = pool.issues.length;

  if (total === 0) return null;
  return { active, waiting, total };
}

function getGoalAgentSummary(root) {
  const gaDir = resolve(root, '.goal-agent');
  let dirs;
  try {
    dirs = readdirSync(gaDir);
  } catch {
    return null;
  }

  let running = 0;
  let completed = 0;

  for (const name of dirs) {
    const statePath = join(gaDir, name, 'state.json');
    try {
      statSync(join(gaDir, name)); // verify it's a directory
    } catch {
      continue;
    }
    const state = readJson(statePath);
    if (!state) continue;

    if (state.status === 'running' || state.status === 'active') running++;
    else if (state.status === 'completed' || state.status === 'done') completed++;
  }

  if (running === 0 && completed === 0) return null;
  return { running, completed };
}

async function main() {
  const raw = await new Promise((resolve) => {
    const chunks = [];
    process.stdin.on('data', (c) => chunks.push(c));
    process.stdin.on('end', () => resolve(Buffer.concat(chunks).toString()));
  });

  // Parse stdin (not strictly needed for output, but validates protocol)
  JSON.parse(raw);

  const root = process.cwd();
  const autoflow = getAutoflowSummary(root);
  const goalAgent = getGoalAgentSummary(root);

  if (!autoflow && !goalAgent) {
    process.stdout.write('{}');
    return;
  }

  const parts = [];

  if (autoflow) {
    parts.push(`Autoflow: ${autoflow.active} active, ${autoflow.waiting} waiting (${autoflow.total} total)`);
  }

  if (goalAgent) {
    parts.push(`Goal-agent: ${goalAgent.running} running, ${goalAgent.completed} completed`);
  }

  const summary = `Pipeline status: ${parts.join('. ')}.`;
  process.stdout.write(JSON.stringify({ user_message: summary }));
}

main().catch(() => {
  // Hook must never crash with non-zero exit
  process.stdout.write('{}');
});
