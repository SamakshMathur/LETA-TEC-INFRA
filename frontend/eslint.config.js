import js from '@eslint/js'
import globals from 'globals'
import react from 'eslint-plugin-react'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{js,jsx}'],
    // `react` plugin is scoped to just jsx-uses-vars below, not its full
    // recommended ruleset — core no-unused-vars mis-detects any component
    // used only as a lowercase-named JSX member expression (e.g.
    // <motion.div>, framer-motion's whole API surface) as unreferenced,
    // since espree's JSX scope analysis skips lowercase JSXMemberExpression
    // objects the same way it correctly skips lowercase plain JSXIdentifiers
    // (intrinsic DOM tags like <div>) — but a member expression is never an
    // intrinsic element, so that skip is wrong here. jsx-uses-vars marks the
    // object identifier as used regardless of case, closing that gap.
    plugins: { react },
    extends: [
      js.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
      parserOptions: {
        ecmaVersion: 'latest',
        ecmaFeatures: { jsx: true },
        sourceType: 'module',
      },
    },
    rules: {
      // varsIgnorePattern only covers var/let/const declarations — destructured
      // function params (e.g. `{ isDark: _isDark = false }` in a component's
      // props) are checked under the separate `args` category, so an
      // underscore-prefixed unused prop needs argsIgnorePattern too.
      'no-unused-vars': ['warn', { varsIgnorePattern: '^[A-Z_]', argsIgnorePattern: '^_' }],
      'react/jsx-uses-vars': 'error',
    },
  },
])
