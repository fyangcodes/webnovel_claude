/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class', // Enable class-based dark mode
  content: [
    "./myapp/reader/templates/reader-tw/**/*.html",
    "./myapp/reader/static/reader-tw/js/**/*.js"
  ],
  safelist: [
    'btn',
    'btn-primary',
    'btn-secondary',
    'btn-ghost',
    'btn-square',
    'btn-circle',
  ],
  theme: {
    extend: {},
  },
  plugins: [
    require('daisyui'),
  ],

  // DaisyUI v5 config
  daisyui: {
    themes: ["light", "dark"],
    darkTheme: "dark",
    base: true,
    styled: true,
    utils: true,
    prefix: "", // No prefix for daisyUI classes
    logs: true,
  },
}

