/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./exam_token/templates/**/*.html",
    "./templates/**/*.html",
    "./**/templates/**/*.html",
    "./exam_token/static/**/*.js",
  ],
  theme: {
    extend: {
      boxShadow: {
        soft: "0 10px 30px rgba(15, 23, 42, 0.08)",
      },
    },
  },
  plugins: [],
};