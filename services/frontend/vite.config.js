import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 3000,
    proxy: {
      '/auth': 'http://127.0.0.1:8080',
      '/api': 'http://127.0.0.1:8080',
      '/soc': 'http://127.0.0.1:8080',
      '/waf': 'http://127.0.0.1:8080',
      '/rag': 'http://127.0.0.1:8080'
    }
  }
});
