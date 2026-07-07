import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standalone output = a self-contained server bundle for the Docker
  // image (node server.js), no node_modules copy needed at runtime.
  output: "standalone",
};

export default nextConfig;
