/**
 * Simple YAML frontmatter parser for SKILL.md files.
 * No external dependencies — handles the subset of YAML used in skill metadata.
 */

/**
 * Parse YAML frontmatter from a markdown file's content.
 * Returns { data: {}, body: string }.
 */
export const parseFrontmatter = (content) => {
  const match = content.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/);
  if (!match) {
    return { data: {}, body: content };
  }

  const rawYaml = match[1];
  const body = match[2];
  const data = {};

  for (const line of rawYaml.split(/\r?\n/)) {
    // Skip blank lines, comments, and continuation lines (arrays, etc.)
    if (!line.trim() || line.trim().startsWith("#") || line.trim().startsWith("-")) continue;

    const colonIdx = line.indexOf(":");
    if (colonIdx === -1) continue;

    const key = line.slice(0, colonIdx).trim();
    let value = line.slice(colonIdx + 1).trim();

    // Strip surrounding quotes
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }

    if (key && value) {
      data[key] = value;
    }
  }

  return { data, body };
};
