import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// as horas dos testes de agenda dependem do fuso: fixa o do escritorio
(globalThis as unknown as { process: { env: Record<string, string> } }).process.env.TZ = "America/Sao_Paulo";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    proxy: { "/api": "http://localhost:8000" },
  },
  build: { outDir: "dist", sourcemap: false },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    restoreMocks: true,
  },
});
