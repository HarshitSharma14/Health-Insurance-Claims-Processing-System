/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    fontFamily: {
      // GT Alpina Standard → Fraunces (optical-size serif, italic support)
      serif: ['"Fraunces"', 'Georgia', 'serif'],
      // Passengersans → Sora (clean, slightly rounded geometric sans)
      sans:  ['"Sora"', 'system-ui', 'sans-serif'],
      // IBM Plex Mono: IDs, policy clauses, claim refs
      mono:  ['"IBM Plex Mono"', 'Menlo', 'monospace'],
    },
    extend: {
      colors: {
        // ── Plum brand (extracted from plumhq.com CSS tokens) ──────────
        aubergine:       "#2c0b21",   // --dark-1 / --esops-primary
        "aubergine-deep":"#1d0716",   // --nav--nav-dark (hover/borders)
        "aubergine-mid": "#3a0e2b",   // --dark-2 (elevated surfaces on dark bg)

        paper:           "#fffaf2",   // body background (rgb 255,250,242)
        cream:           "#fff1e5",   // --light-0 / nav-white / text on dark
        "cream-mid":     "#ffe4cc",   // --plum-promise-4 (subtle tints)

        coral:           "#ff4052",   // --esops-tertiary (CTA / primary accent)
        "coral-hover":   "#e6293c",   // darker for hover states

        // Page text (on paper background)
        "ink":           "#460932",   // rgb(70,9,50) — body text on cream/paper
        "ink-light":     "#7a3060",   // secondary text (derived)
        "ink-muted":     "#bea0b3",   // --plum-vision-light (muted/placeholder)

        // ── Surface & border ─────────────────────────────────────────────
        surface:         "#ffffff",
        border:          "#f0e4d8",   // subtle warm border on paper
        "border-strong": "#d9c4b8",   // stronger border

        // ── Status palette (derived from Plum's world) ────────────────────
        // APPROVED  — muted sage/teal (cool counterpoint to warm palette)
        ok:              "#4e7d6a",
        "ok-bg":         "#eaf2ee",
        // PARTIAL   — warm gold/ochre between cream and coral
        warn:            "#c49428",
        "warn-bg":       "#fdf4d6",
        // REJECTED  — coral direct (brand CTA = stop signal, coherent)
        fail:            "#ff4052",
        "fail-bg":       "#fff0f1",
        // MANUAL_REVIEW / degraded — dusty mauve, lighter than aubergine
        degraded:        "#9c7a94",
        "degraded-bg":   "#f5eef4",
      },

      keyframes: {
        "fade-up": {
          "0%":   { opacity: "0", transform: "translateY(6px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "stamp-press": {
          "0%":   { opacity: "0", transform: "rotate(-3deg) scale(1.18)" },
          "55%":  { opacity: "1", transform: "rotate(-3deg) scale(0.96)" },
          "78%":  { transform: "rotate(-3deg) scale(1.02)" },
          "100%": { opacity: "1", transform: "rotate(-3deg) scale(1)" },
        },
      },
      animation: {
        "fade-up":     "fade-up 0.22s ease-out both",
        "stamp-press": "stamp-press 0.2s cubic-bezier(0.22,1,0.36,1) both",
      },
    },
  },
  plugins: [],
}
