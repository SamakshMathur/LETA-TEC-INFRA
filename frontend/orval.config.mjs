import { defineConfig } from 'orval';

export default defineConfig({
  letaApi: {
    input: {
      target: './.orval/openapi.json',
    },
    output: {
      mode: 'split',
      target: './src/api/generated/endpoints.ts',
      schemas: './src/api/generated/model',
      client: 'axios',
      clean: true,
      prettier: true,
      override: {
        mutator: {
          path: './src/api/mutator/custom-instance.ts',
          name: 'customInstance',
        },
      },
    },
  },
});
