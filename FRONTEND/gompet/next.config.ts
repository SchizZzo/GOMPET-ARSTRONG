import type { NextConfig } from 'next';
import path from 'path';

const nextConfig: NextConfig = {
  turbopack: {
    root: path.join(__dirname)
  },
  sassOptions: {
    includePaths: [path.join(__dirname, 'src'), path.join(__dirname, 'src/styles')]
  }
};

export default nextConfig;
