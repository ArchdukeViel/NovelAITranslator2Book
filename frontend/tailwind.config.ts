import type { Config } from "tailwindcss";
import tailwindcssAnimate from "tailwindcss-animate";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}"
  ],
  theme: {
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
          text: "hsl(var(--primary-text))"
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))"
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))"
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))"
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
          text: "hsl(var(--destructive-text))"
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))"
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))"
        },
        sidebar: {
          DEFAULT: "hsl(var(--sidebar))",
          accent: "hsl(var(--sidebar-accent))"
        },
        success: {
          DEFAULT: "hsl(var(--success))",
          foreground: "hsl(var(--success-foreground))",
          text: "hsl(var(--success-text))"
        },
        warning: {
          DEFAULT: "hsl(var(--warning))",
          foreground: "hsl(var(--warning-foreground))",
          text: "hsl(var(--warning-text))"
        },
        info: {
          DEFAULT: "hsl(var(--info))",
          foreground: "hsl(var(--info-foreground))",
          text: "hsl(var(--info-text))"
        },

        // Stitch Tokens - Dokushodo Palette
        surface: {
          DEFAULT: "#fcf9f3",
          dim: "#dcdad4",
          bright: "#fcf9f3",
          variant: "#e5e2dc",
          container: {
            lowest: "#ffffff",
            low: "#f6f3ed",
            DEFAULT: "#f0eee8",
            high: "#ebe8e2",
            highest: "#e5e2dc"
          }
        },
        "on-surface": {
          DEFAULT: "#1c1c18",
          variant: "#59413d"
        },
        "inverse-surface": {
          DEFAULT: "#31312d",
          "on-surface": "#f3f0ea"
        },
        outline: {
          DEFAULT: "#8c716c",
          variant: "#e0bfb9"
        },
        "surface-tint": "#ad3222",
        "primary-container": {
          DEFAULT: "#bd3e2c",
          on: "#ffe6e2"
        },
        "inverse-primary": "#ffb4a7",
        "secondary-container": {
          DEFAULT: "#dde0e5",
          on: "#5f6368"
        },
        tertiary: {
          DEFAULT: "#005975",
          on: "#ffffff",
          container: {
            DEFAULT: "#007396",
            on: "#d5f0ff"
          },
          fixed: {
            DEFAULT: "#bfe8ff",
            dim: "#7fd1f7",
            on: "#001f2b",
            "on-variant": "#004d65"
          }
        },
        "error-container": {
          DEFAULT: "#ffdad6",
          on: "#93000a"
        },
        "primary-fixed": {
          DEFAULT: "#ffdad4",
          dim: "#ffb4a7",
          on: "#400200",
          "on-variant": "#8b1a0c"
        },
        "secondary-fixed": {
          DEFAULT: "#e0e3e8",
          dim: "#c3c7cc",
          on: "#181c20",
          "on-variant": "#43474c"
        },
        "shuji-vermillion": "#B83220",
        "washi-paper": "#F4F1EA",
        "sumi-ink": "#2B2826",
        "aged-parchment": "#EBE7DF",
        "muted-obsidian": "#1F1E1D",
        "discord-blurple": "#5865F2"
      },
      fontFamily: {
        sans: ["var(--font-dm-sans)", "Hanken Grotesk", "sans-serif"],
        serif: ["var(--font-noto-serif-jp)", "EB Garamond", "serif"],
        mono: ["var(--font-dm-mono)", "monospace"],
        literary: ["var(--font-noto-serif-jp)", "EB Garamond", "serif"],
        ui: ["var(--font-dm-sans)", "Hanken Grotesk", "sans-serif"],
        metadata: ["var(--font-dm-mono)", "Hanken Grotesk", "monospace"],
        "display-lg": ["EB Garamond", "serif"],
        "headline-lg": ["EB Garamond", "serif"],
        "title-md": ["EB Garamond", "serif"],
        "body-lg": ["Hanken Grotesk", "sans-serif"],
        "body-md": ["Hanken Grotesk", "sans-serif"],
        "label-md": ["Hanken Grotesk", "sans-serif"],
        caption: ["Hanken Grotesk", "sans-serif"]
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
        DEFAULT: "0.25rem",
        full: "9999px"
      },
      boxShadow: {
        // Resting elevation for raised card surfaces (sumi-ink based, soft in dark).
        card: "0 1px 2px 0 rgb(28 28 24 / 0.06)",
        // Hover lift for interactive cards; only the hero may exceed this.
        raised: "0 12px 28px -8px rgb(28 28 24 / 0.18)"
      }
    }
  },
  plugins: [tailwindcssAnimate]
};

export default config;
