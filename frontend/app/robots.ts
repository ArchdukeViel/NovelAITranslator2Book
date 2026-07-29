import type { MetadataRoute } from "next";
import { getSiteUrl } from "@/lib/seo";

export default function robots(): MetadataRoute.Robots {
  const siteUrl = getSiteUrl().replace(/\/+$/, "");

  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: [
          "/admin/",
          "/api/",
          "/login",
          "/auth/",
          "/account/",
          "/contact",
          "/dmca",
        ],
      },
    ],
    sitemap: `${siteUrl}/sitemap.xml`,
  };
}
