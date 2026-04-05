/** @type {import('next').NextConfig} */

// Backend URL - defaults to localhost for development
// In production (Vercel), set NEXT_PUBLIC_BACKEND_URL environment variable
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:6000';

const nextConfig = {
  reactStrictMode: true,

  // Enable static export for Vercel
  output: process.env.VERCEL ? undefined : 'standalone',

  async rewrites() {
    return [
      {
        // Recorder always runs locally on client's PC (records microphone)
        source: '/api/recorder/:path*',
        destination: 'http://localhost:5050/:path*',
      },
      {
        // Backend API - uses cloud URL in production
        source: '/api/backend/:path*',
        destination: `${BACKEND_URL}/api/v1/:path*`,
      },
    ];
  },

  // Allow images from various domains
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: '**.railway.app',
      },
      {
        protocol: 'https',
        hostname: '**.vercel.app',
      },
    ],
  },
};

module.exports = nextConfig;
