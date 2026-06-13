/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    fontFamily: {
      serif: ['"IBM Plex Serif"', 'Georgia', 'serif'],
      sans:  ['"IBM Plex Sans"',  'system-ui', 'sans-serif'],
      mono:  ['"IBM Plex Mono"',  'Menlo', 'monospace'],
    },
    extend: {
      colors: {
        // Dark ink — header background, segmented-control active
        ink:           "#1A1714",
        "ink-light":   "#2C2826",
        "ink-muted":   "#4A4441",

        // Page surfaces
        bg:            "#F7F5F2",
        surface:       "#FFFFFF",
        border:        "#E2DDD8",
        "border-strong":"#C8C2BB",

        // Text
        "text-primary":   "#1A1714",
        "text-secondary": "#6B6560",
        "text-muted":     "#A39D98",

        // Accent — amber-brown
        accent:          "#B45309",
        "accent-hover":  "#92400E",
        "accent-subtle": "#F0E6D8",

        // Status (muted)
        ok:              "#4A7C59",
        "ok-bg":         "#EBF3EE",
        warn:            "#92610A",
        "warn-bg":       "#FDF3DC",
        fail:            "#8B3A3A",
        "fail-bg":       "#FAEBEB",
        degraded:        "#4A6275",
        "degraded-bg":   "#EBF0F3",
      },

      keyframes: {
        "fade-up": {
          "0%":   { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "stamp-press": {
          "0%":   { opacity: "0", transform: "rotate(-3deg) scale(1.18)" },
          "60%":  { opacity: "1", transform: "rotate(-3deg) scale(0.97)" },
          "80%":  { transform: "rotate(-3deg) scale(1.01)" },
          "100%": { opacity: "1", transform: "rotate(-3deg) scale(1)" },
        },
      },
      animation: {
        "fade-up":     "fade-up 0.22s ease-out both",
        "stamp-press": "stamp-press 0.18s cubic-bezier(0.22,1,0.36,1) both",
      },
    },
  },
  plugins: [],
}
