import type { Config } from "tailwindcss";

/**
 * Semantic color tokens backed by the CSS variables in `src/theme.css`
 * (oklch, light/dark via prefers-color-scheme). `<alpha-value>` lets you use
 * Tailwind opacity modifiers, e.g. `bg-brand/12`, `bg-success/15`.
 */
const TOKENS = [
  "background",
  "foreground",
  "muted",
  "muted-foreground",
  "secondary",
  "secondary-foreground",
  "accent",
  "border",
  "brand",
  "brand-foreground",
  "success",
  "error",
  "warning",
] as const;

const colors = Object.fromEntries(
  TOKENS.map((t) => [t, `oklch(var(--${t}) / <alpha-value>)`]),
);

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "media",
  theme: {
    extend: { colors },
  },
  plugins: [],
} satisfies Config;
