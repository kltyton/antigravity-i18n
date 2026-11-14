/*
 * antigravity-i18n — ESM Main Entry Bootstrap for Antigravity IDE
 */
import { createRequire } from 'node:module';

try {
  const require = createRequire(import.meta.url);
  const ideMain = require('./electron-ide-i18n.cjs');
  if (ideMain && typeof ideMain.init === 'function') {
    ideMain.init();
  }
} catch (_err) {
  // Never break IDE launch if external runtime fails to initialize
}
