import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path';

// const hmr = {
//   clientPort: 443,
//   host: "localhost",
//   protocol: "wss"
// };

export default defineConfig({
  plugins: [vue()],
  server: {
    host: "0.0.0.0",
    port: 4200,
    watch: {
      usePolling: true,
    },
    hmr: {
      host: 'localhost',
    }
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src')
    }
  },
})
