#!/usr/bin/env node
/**
 * Скрипт генерации PNG иконок PWA из favicon.svg (NM-07)
 * Запуск: node scripts/generate_pwa_icons.mjs
 *
 * Требует: sharp (npm install --save-dev sharp)
 */

import { readFileSync, mkdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..');
const SVG_PATH = join(ROOT, 'ui/public/favicon.svg');
const ICONS_DIR = join(ROOT, 'ui/public/icons');

const SIZES = [192, 512];

async function generateIcons() {
  try {
    const sharp = (await import('sharp')).default;
    mkdirSync(ICONS_DIR, { recursive: true });
    const svgBuffer = readFileSync(SVG_PATH);
    for (const size of SIZES) {
      const outPath = join(ICONS_DIR, `icon-${size}.png`);
      await sharp(svgBuffer)
        .resize(size, size)
        .png()
        .toFile(outPath);
      console.log(`✓ Generated icon-${size}.png`);
    }
    console.log('PWA icons generated successfully!');
  } catch (err) {
    if (err.code === 'ERR_MODULE_NOT_FOUND' || err.message?.includes('sharp')) {
      console.warn('sharp not installed. Generating placeholder icons...');
      await generatePlaceholders();
    } else {
      throw err;
    }
  }
}

/**
 * Генерировать PNG-заглушки через встроенный Node.js Canvas API
 * (без внешних зависимостей, для CI)
 */
async function generatePlaceholders() {
  mkdirSync(ICONS_DIR, { recursive: true });

  // Создаём минимальный PNG (1x1 пиксель purple) как fallback
  // В реальном проде используйте sharp или vite-plugin-pwa
  const PNG_1x1_PURPLE = Buffer.from(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
    'base64'
  );

  for (const size of SIZES) {
    const { writeFileSync } = await import('fs');
    writeFileSync(join(ICONS_DIR, `icon-${size}.png`), PNG_1x1_PURPLE);
    console.log(`✓ Placeholder icon-${size}.png created (install sharp for real icons)`);
  }
}

generateIcons().catch(console.error);
