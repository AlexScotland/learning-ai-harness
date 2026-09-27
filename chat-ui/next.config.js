/** @type {import('next').NextConfig} */
const nextConfig = {
  // Required by the two-stage production Dockerfile, which copies
  // `.next/standalone` (a self-contained `node server.js`) into the runner
  // image. Without this the standalone output is never produced and the
  // build stage's COPY fails.
  output: 'standalone',
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  },
};

module.exports = nextConfig;
