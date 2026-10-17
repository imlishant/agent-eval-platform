import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

// dev: the UI on :5173 talks to the API on :3000; production: the API serves dist/ itself
export default defineConfig({
  plugins: [vue()],
  server: { proxy: { '/api': 'http://localhost:3000' } },
});
