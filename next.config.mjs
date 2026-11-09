/** @type {import('next').NextConfig} */
const isExport = process.env.NEXT_OUTPUT_EXPORT === 'true' || process.env.STATIC_EXPORT === 'true' || true;

const nextConfig = {
  output: isExport ? 'export' : (process.env.NEXT_OUTPUT_STANDALONE === 'true' ? 'standalone' : undefined),
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  ...(isExport ? {} : {
    async rewrites() {
      return [
        {
          source: '/api/:path*',
          destination: process.env.BACKEND_INTERNAL_URL
            ? `${process.env.BACKEND_INTERNAL_URL}/api/:path*`
            : 'http://127.0.0.1:5000/api/:path*',
        },
      ]
    },
  }),
}

export default nextConfig
