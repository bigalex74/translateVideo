import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts', 'src/**/*.spec.ts'],
    coverage: {
      provider: 'v8',
      // Пороги покрытия — CI падает если ниже
      thresholds: {
        statements: 80,
        branches: 75,   // ниже остальных: React-компоненты не покрыты Vitest
        functions: 80,
        lines: 80,
      },
      exclude: [
        '**/*.d.ts',
        '**/*.test.ts',
        '**/*.spec.ts',
        'src/types/**',
      ],
    },
  },
});

