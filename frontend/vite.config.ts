import path from 'path';
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '');
  return {
    server: {
      port: 3000,
      host: '0.0.0.0',
      proxy: {
        '/api/summarizer': {
          target: 'http://localhost:8002',
          changeOrigin: true,
          rewrite: (path: string) => path.replace(/^\/api\/summarizer/, ''),
        },
        '/api/transcriber': {
          target: 'http://localhost:8001',
          changeOrigin: true,
          rewrite: (path: string) => path.replace(/^\/api\/transcriber/, ''),
          ws: true,
        },
      },
    },
    plugins: [react()],
    define: {
      'process.env.API_KEY': JSON.stringify(env.GEMINI_API_KEY),
      'process.env.GEMINI_API_KEY': JSON.stringify(env.GEMINI_API_KEY)
    },
    resolve: {
      alias: {
        '@': path.resolve(__dirname, '.'),
      }
    }
  };
});
