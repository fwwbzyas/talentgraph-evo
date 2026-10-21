import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    chunkSizeWarningLimit: 550,
    rolldownOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;
          if (id.includes("three/examples")) return "three-addons";
          if (id.includes("three")) return "three";
          if (id.includes("echarts") || id.includes("zrender")) return "charts";
          if (id.includes("motion")) return "motion";
          if (id.includes("react")) return "react";
          return "vendor";
        },
      },
    },
  },
});
