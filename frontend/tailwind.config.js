/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    fontFamily: {
      serif: ['"IBM Plex Serif"', 'Georgia', 'serif'],
      sans: ['"IBM Plex Sans"', 'system-ui', 'sans-serif'],
      mono: ['"IBM Plex Mono"', 'Menlo', 'monospace'],
    },
    extend: {
      colors: {
        // Page surfaces
        bg:        "#F7F5F2",
        surface:   "#FFFFFF",
        border:    "#E2DDD8",
        "border-strong": "#C8C2BB",

        // Text
        "text-primary":   "#1A1714",
        "text-secondary": "#6B6560",
        "text-muted":     "#A39D98",

        // Accent — amber-brown
        accent:        "#B45309",
        "accent-hover":"#92400E",
        "accent-subtle":"#F0E6D8",

        // Status (muted)
        ok:       "#4A7C59",
        "ok-bg":  "#EBF3EE",
        warn:     "#92610A",
        "warn-bg":"#FDF3DC",
        fail:     "#8B3A3A",
        "fail-bg":"#FAEBEB",
        // Degraded — cool slate, deliberately distinct from warm trio
        degraded:       "#4A6275",
        "degraded-bg":  "#EBF0F3",
      },
    },
  },
  plugins: [],
}
