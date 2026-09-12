import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  serverExternalPackages: ["read-excel-file"],
  turbopack: {
    root: process.cwd(),
  },
};

export default nextConfig;
