/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // The schema package is a workspace dependency shipped as compiled ESM;
  // listing it under transpilePackages tells Next to treat it as first-party
  // (no stale `dist/` quirks during dev hot-reload).
  transpilePackages: ['@arcana/schema'],
};

export default nextConfig;
