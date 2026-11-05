/** @type {import('next').NextConfig} */
const nextConfig = {
  output: process.env.NEXT_OUTPUT_STANDALONE === 'true' ? 'standalone' : undefined,
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
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
}

export default nextConfig
