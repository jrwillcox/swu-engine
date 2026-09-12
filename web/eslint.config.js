// ESLint 9 flat config.
//
// Deliberately conservative, in the same spirit as the Ruff config in
// ../pyproject.toml: the job here is catching real mistakes (unused bindings,
// broken hook dependencies, misuse of promises) on an existing 12k-line
// frontend, not reformatting it to a new house style.  Formatting opinions are
// left entirely to Prettier, and `eslint-config-prettier` (last in the chain)
// switches off every rule that would argue with it.
import js from "@eslint/js";
import globals from "globals";
import tseslint from "typescript-eslint";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import prettier from "eslint-config-prettier";

export default tseslint.config(
  {
    ignores: [
      "dist/**",
      "node_modules/**",
      "coverage/**",
      "test-results/**",
      "playwright-report/**",
      "screenshots/**",
    ],
  },
  js.configs.recommended,
  // Non-type-aware preset: type-aware linting needs a full program per run and
  // would make `npm run lint` several times slower than `npm run typecheck`,
  // which already does that job properly.
  ...tseslint.configs.recommended,
  {
    files: ["**/*.{ts,tsx}"],
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      globals: {
        ...globals.browser,
        // import.meta.env is Vite's, but `process.env.NODE_ENV` still appears in
        // a few guards, and vitest injects a node-ish environment.
        ...globals.node,
      },
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],

      // TypeScript resolves identifiers itself and reports genuinely undefined
      // ones far more accurately; core no-undef only produces false positives on
      // type-only names and ambient globals.
      "no-undef": "off",

      // The react-compiler-era rules that ship with eslint-plugin-react-hooks v7
      // (set-state-in-effect, static-components, refs, immutability) flag ~30
      // places in this existing UI.  They are worth SEEING — several are genuine
      // "effect that syncs state instead of deriving it" patterns — but they are
      // advisory here, not a gate: fixing them means reworking working game
      // components with no test failure to prove the rework correct.  Kept as
      // warnings so `npm run lint` stays green and the list stays visible; the
      // classic rules-of-hooks and exhaustive-deps remain errors.
      "react-hooks/set-state-in-effect": "warn",
      "react-hooks/static-components": "warn",
      "react-hooks/refs": "warn",
      "react-hooks/immutability": "warn",

      // `_`-prefixed bindings are the established convention here for a value
      // that must be destructured but isn't used.
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_", caughtErrors: "none" },
      ],

      // The API layer crosses an untyped JSON boundary; `any` there is honest,
      // and banning it would only produce a wave of `unknown` + casts.
      "@typescript-eslint/no-explicit-any": "off",

      // Non-null assertions are used at a handful of DOM-root and
      // known-present-map-key sites where the alternative is dead error paths.
      "@typescript-eslint/no-non-null-assertion": "off",
    },
  },
  {
    // The .mjs helpers under scripts/ (Playwright-driven screenshots, the
    // localStorage diagnostic) are plain Node, not part of the app bundle.
    files: ["**/*.{js,mjs,cjs}"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      globals: { ...globals.node, ...globals.browser },
    },
  },
  {
    // Tests may reach for empty mocks and loose shapes.
    files: ["**/*.test.{ts,tsx}", "tests/**", "src/**/__tests__/**"],
    rules: {
      "@typescript-eslint/no-empty-function": "off",
    },
  },
  prettier,
);
