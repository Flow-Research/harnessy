/**
 * Flow hook configuration loader.
 * Reads .jarvis/hooks.yaml with graceful defaults when missing.
 */

import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const DEFAULTS = {
  notifications: {
    desktop: true,
    webhook_url: null,
  },
  sla: {
    stale_gate_hours: 4,
  },
  protected_patterns: ['_shared/*.py', 'program.md'],
};

/**
 * Minimal YAML parser — handles flat keys, nested single-level objects,
 * and simple inline arrays. No external deps.
 */
function parseSimpleYaml(text) {
  const result = {};
  let currentSection = null;

  for (const raw of text.split('\n')) {
    const line = raw.replace(/#.*$/, '').trimEnd(); // strip comments
    if (!line.trim()) continue;

    const indent = line.search(/\S/);
    const trimmed = line.trim();

    // Inline array: key: ["a", "b"]
    const arrayMatch = trimmed.match(/^(\w+):\s*\[(.+)\]$/);
    if (arrayMatch) {
      const key = arrayMatch[1];
      const items = arrayMatch[2]
        .split(',')
        .map((s) => s.trim().replace(/^["']|["']$/g, ''));
      if (indent > 0 && currentSection) {
        result[currentSection][key] = items;
      } else {
        result[key] = items;
      }
      continue;
    }

    const kvMatch = trimmed.match(/^(\w+):\s*(.*)$/);
    if (!kvMatch) continue;

    const [, key, rawVal] = kvMatch;

    if (indent === 0 && (!rawVal || rawVal === '')) {
      // Section header
      currentSection = key;
      if (!result[currentSection]) result[currentSection] = {};
      continue;
    }

    // Parse value
    let value = rawVal;
    if (value === 'true') value = true;
    else if (value === 'false') value = false;
    else if (value === 'null' || value === '' || value === '~') value = null;
    else if (/^\d+(\.\d+)?$/.test(value)) value = Number(value);
    else value = value.replace(/^["']|["']$/g, '');

    if (indent > 0 && currentSection) {
      result[currentSection][key] = value;
    } else {
      currentSection = null;
      result[key] = value;
    }
  }

  return result;
}

/** Deep merge source into target (source wins). */
function merge(target, source) {
  const out = { ...target };
  for (const [k, v] of Object.entries(source)) {
    if (v && typeof v === 'object' && !Array.isArray(v) && typeof out[k] === 'object') {
      out[k] = merge(out[k], v);
    } else {
      out[k] = v;
    }
  }
  return out;
}

/**
 * Load hook configuration from .jarvis/hooks.yaml.
 * Returns defaults merged with any file-based overrides.
 *
 * @param {string} [projectRoot] - Absolute path to project root. Defaults to cwd.
 * @returns {object} Merged configuration.
 */
export function loadConfig(projectRoot) {
  const root = projectRoot || process.cwd();
  const configPath = resolve(root, '.jarvis', 'hooks.yaml');

  try {
    const raw = readFileSync(configPath, 'utf-8');
    const parsed = parseSimpleYaml(raw);
    return merge(DEFAULTS, parsed);
  } catch {
    // File missing or unreadable — use defaults
    return { ...DEFAULTS };
  }
}
