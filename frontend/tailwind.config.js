/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Custom colors matching the metrics categories from the image
        volume: {
          light: '#dcfce7',    // green-100
          DEFAULT: '#22c55e',  // green-500
          dark: '#16a34a',     // green-600
        },
        cycleTime: {
          light: '#fee2e2',    // red-100
          DEFAULT: '#ef4444',  // red-500
          dark: '#dc2626',     // red-600
        },
        productivity: {
          light: '#fae8ff',    // fuchsia-100
          DEFAULT: '#d946ef',  // fuchsia-500
          dark: '#c026d3',     // fuchsia-600
        },
        accuracy: {
          light: '#dbeafe',    // blue-100
          DEFAULT: '#3b82f6',  // blue-500
          dark: '#2563eb',     // blue-600
        },
      },
    },
  },
  plugins: [],
}
