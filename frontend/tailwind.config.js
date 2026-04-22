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
          950: "#F5F3F0",
          900: "#EAE7E2",
          800: "#E0DCD5",
        },
        mist: "#2D2D2D",
        line: "#D4CFCB",
        accent: "#C8A96A",
      },
    },
  },
  plugins: [],
};
