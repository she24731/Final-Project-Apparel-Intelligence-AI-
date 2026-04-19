/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["ui-sans-serif", "system-ui", "Inter", "Segoe UI", "Roboto", "Helvetica Neue", "Arial"],
      },
      colors: {
        ink: {
          950: "#0B0D10",
          900: "#12151B",
          800: "#1B2029",
        },
        mist: "#E7E9EE",
        line: "#2A3140",
        accent: "#C8A96A",
      },
    },
  },
  plugins: [],
};
