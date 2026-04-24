/**
 * Harnessy hook notification utilities.
 * Desktop notifications (macOS/Linux) and webhook delivery.
 */

import { execFile } from 'node:child_process';
import { request } from 'node:https';
import { request as httpRequest } from 'node:http';

/**
 * Send a desktop notification.
 * macOS: osascript, Linux: notify-send.
 */
export function sendDesktopNotification(title, message) {
  return new Promise((resolve, reject) => {
    if (process.platform === 'darwin') {
      execFile('osascript', [
        '-e',
        `display notification "${message}" with title "${title}"`,
      ], (err) => (err ? reject(err) : resolve()));
    } else {
      // Linux — notify-send
      execFile('notify-send', [title, message], (err) => {
        if (err) reject(err);
        else resolve();
      });
    }
  });
}

/**
 * POST a JSON payload to a webhook URL.
 * Supports both https and http URLs.
 */
export function sendWebhook(url, payload) {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify(payload);
    const parsed = new URL(url);
    const doRequest = parsed.protocol === 'https:' ? request : httpRequest;

    const req = doRequest(
      url,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(body),
        },
      },
      (res) => {
        const chunks = [];
        res.on('data', (c) => chunks.push(c));
        res.on('end', () => resolve({ status: res.statusCode, body: Buffer.concat(chunks).toString() }));
      },
    );

    req.on('error', reject);
    req.write(body);
    req.end();
  });
}

/**
 * Send notification via all configured channels.
 *
 * @param {string} title
 * @param {string} message
 * @param {object} config - Output of loadConfig()
 */
export async function notify(title, message, config) {
  const results = [];

  if (config.notifications?.desktop) {
    try {
      await sendDesktopNotification(title, message);
      results.push({ channel: 'desktop', ok: true });
    } catch (err) {
      results.push({ channel: 'desktop', ok: false, error: err.message });
    }
  }

  if (config.notifications?.webhook_url) {
    try {
      const res = await sendWebhook(config.notifications.webhook_url, { title, message });
      results.push({ channel: 'webhook', ok: res.status < 400, status: res.status });
    } catch (err) {
      results.push({ channel: 'webhook', ok: false, error: err.message });
    }
  }

  return results;
}
