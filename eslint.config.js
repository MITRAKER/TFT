import js from "@eslint/js";
import globals from "globals";

const strict = {
  complexity: ["error", 12],
  curly: "error",
  eqeqeq: "error",
  "max-depth": ["error", 3],
  "max-lines-per-function": ["error", { max: 70, skipBlankLines: true, skipComments: true }],
  "no-eval": "error",
  "no-implied-eval": "error",
  "no-new-func": "error",
  "no-var": "error",
  "prefer-const": "error",
};

export default [
  {
    ignores: [
      "node_modules/",
      "test-results/",
      "playwright-report/",
      "build/",
      "dist/",
      "htmlcov/",
      ".venv/",
      "venv/",
    ],
  },
  js.configs.recommended,
  {
    files: ["src/tft/web/**/*.js"],
    languageOptions: { ecmaVersion: 2022, sourceType: "module", globals: globals.browser },
    rules: strict,
  },
  {
    files: ["tests/web/**/*.js", "eslint.config.js", "playwright.config.js"],
    languageOptions: { ecmaVersion: 2022, sourceType: "module", globals: globals.node },
    rules: { ...strict, "max-lines-per-function": "off" },
  },
  {
    // Browser tests hand functions to the page, where they run with the browser's globals.
    files: ["tests/web/e2e/**/*.js"],
    languageOptions: { globals: { ...globals.node, ...globals.browser } },
  },
];
