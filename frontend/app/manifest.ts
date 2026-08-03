import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Dokushodo - Web Novel Platform",
    short_name: "Dokushodo",
    description: "Read translated Japanese web novels with clean navigation, progress tracking, and source-aware metadata.",
    start_url: "/",
    display: "standalone",
    background_color: "#140f17",
    theme_color: "#140f17",
    icons: [
      {
        src: "/assets/dokushodo/brand/icon.svg",
        sizes: "any",
        type: "image/svg+xml",
      },
      {
        src: "/assets/dokushodo/brand/icon-192.png",
        sizes: "192x192",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/assets/dokushodo/brand/icon-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
  };
}
