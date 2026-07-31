/** @type {import('next').NextConfig} */
const isGitHubPages = process.env.GITHUB_PAGES === "true";

const nextConfig = isGitHubPages
  ? {
      output: "export",
      basePath: "/AI-AI",
      assetPrefix: "/AI-AI/",
      trailingSlash: true,
    }
  : {
      output: "standalone",
    };

export default nextConfig;
