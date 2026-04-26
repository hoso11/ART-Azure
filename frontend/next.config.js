/** @type {import('next').NextConfig} */
const INTERNAL_API_URL = process.env.INTERNAL_API_URL || "http://backend:8000";

const nextConfig = {
  output: "standalone",
  images: {
    remotePatterns: [
      { protocol: "http", hostname: "localhost", port: "9000" },
      { protocol: "http", hostname: "minio", port: "9000" },
      { protocol: "https", hostname: "*.azurewebsites.net" },
      { protocol: "https", hostname: "*.blob.core.windows.net" },
    ],
  },
  async rewrites() {
    // In Azure the backend sidecar is reachable at http://localhost:8000.
    // In local Docker Compose it is http://backend:8000.
    // Browser calls to /api/* hit the Next.js server, which proxies here.
    return [
      { source: "/api/:path*", destination: `${INTERNAL_API_URL}/api/:path*` },
    ];
  },
};

module.exports = nextConfig;
