const backendUrl = process.env.BACKEND_URL || "http://localhost:8000";

const proxiedPaths = [
  "/audit/:path*",
  "/healthz",
  "/gauntlet/:path*",
  "/activity/:path*",
  "/test-vendor/:path*",
  "/interrogate/:path*",
  "/api/:path*",
  "/shop/:path*",
  "/buyer/:path*",
  "/agents/:path*",
  "/vet",
  "/agent/:path*",
];

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  async rewrites() {
    return proxiedPaths.map((source) => ({
      source,
      destination: `${backendUrl}${source}`,
    }));
  },
};

export default nextConfig;
