import type { NextConfig } from "next";

const isStaticExport = process.env.ATLAS_STATIC_EXPORT === "true";

const nextConfig: NextConfig = {
  turbopack: {
    root: process.cwd(),
  },
  ...(isStaticExport
    ? {
        output: "export",
        trailingSlash: true,
        images: { unoptimized: true },
      }
    : {
        async rewrites() {
          return [
            {
              source: "/api/:path*",
              destination: `${process.env.NEXT_PUBLIC_API_URL}/api/:path*`,
            },
          ];
        },
      }),
};

export default nextConfig;