import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  base: './',
  plugins: [react(), {
    name: 'workbench-csp',
    transformIndexHtml(_html, context) {
      const scripts = context.server ? "'self' 'unsafe-inline'" : "'self'"
      const address = context.server?.httpServer?.address()
      const connect = address && typeof address !== 'string'
        ? `ws://127.0.0.1:${address.port} http://127.0.0.1:${address.port}`
        : "'none'"
      return [{
        tag: 'meta',
        attrs: {
          'http-equiv': 'Content-Security-Policy',
          content: `default-src 'none'; script-src ${scripts}; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; connect-src ${connect}; base-uri 'none'; form-action 'none'`,
        },
        injectTo: 'head-prepend',
      }]
    },
  }],
  server: { host: '127.0.0.1', port: 5173, strictPort: true },
})
