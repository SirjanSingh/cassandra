/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // "Mission control" - graphite + bone + a single signal amber.
        // Deliberately NO purple/violet, no candy gradients.
        ink: {
          0: "#070707",
          1: "#0C0D0E",
          2: "#121315",
          3: "#191A1D",
          4: "#222428",
        },
        bone: "#F4F1EA",
        ash: "#A7A39B",
        slate: "#6C6A66",
        line: "rgba(244,241,234,0.08)",
        line2: "rgba(244,241,234,0.16)",
        signal: { DEFAULT: "#F2A93B", deep: "#D98A14", soft: "rgba(242,169,59,0.12)" },
        alert: "#F0443E",
        good: "#21C07A",
        steel: "#5A6B82",
      },
      fontFamily: {
        display: ['"Space Grotesk"', "system-ui", "sans-serif"],
        sans: ['"Inter"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      letterSpacing: { tightish: "-0.02em", wide2: "0.14em" },
      keyframes: {
        rise: { "0%": { opacity: 0, transform: "translateY(14px)" }, "100%": { opacity: 1, transform: "none" } },
        flick: { "0%,100%": { opacity: 1 }, "45%": { opacity: 0.4 } },
        sweep: { "0%": { transform: "translateY(-100%)" }, "100%": { transform: "translateY(220%)" } },
      },
      animation: {
        rise: "rise .5s cubic-bezier(.22,.61,.36,1) both",
        flick: "flick 2.4s ease-in-out infinite",
        sweep: "sweep 7s linear infinite",
      },
    },
  },
  plugins: [],
};
