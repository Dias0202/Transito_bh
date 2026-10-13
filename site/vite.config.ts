import { defineConfig } from "vite";

// Relative base so dist/ works from any static host or subpath.
export default defineConfig({
  base: "./",
  // MapLibre (~800 kB) is a lazy chunk loaded only near the map scene.
  build: { target: "es2020", sourcemap: false, chunkSizeWarningLimit: 900 },
});
