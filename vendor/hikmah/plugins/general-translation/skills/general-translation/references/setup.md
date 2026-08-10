# Setup — installation & configuration

> Reference loaded by the `general-translation` skill. For the rule list
> and decision tree see `../SKILL.md`.

## 1. Dependencies

```jsonc
// package.json
{
  "dependencies": {
    "gt-next": "^6.16.23"      // runtime library (use latest)
  },
  "devDependencies": {
    "gt": "^2.14.32"            // CLI tool used during build
  },
  "scripts": {
    "build": "npx gt translate --publish && next build"
  }
}
```

> The `gt translate --publish` step **must run before** `next build`. It
> extracts every `<T>` and `t('...')` static literal, uploads them, and
> downloads target-locale translations into `public/_gt/` for the build to
> embed.

## 2. `gt.config.json` (repo root)

```json
{
  "defaultLocale": "en",
  "locales": ["ar", "fr"]
}
```

- `defaultLocale` is your source language. Write all `<T>` content in this
  language.
- `locales` is the set of target languages GT will produce.

## 3. `next.config.ts`

```ts
import { withGTConfig } from 'gt-next/config';

const nextConfig: NextConfig = {
  // ...your normal Next config
};

export default withGTConfig(nextConfig, {
  description: 'One-line app description used as translation context',
});
```

The `description` is sent to the translation engine as global context — keep
it short and accurate (e.g. "B2B logistics dashboard for trucking
companies"). Bad context → bad translations.

## 4. Environment variables

GT publishing requires an API key (see GT dashboard for the exact env var
name — typically `GT_API_KEY` or `GT_PROJECT_ID` + `GT_API_KEY`). Add to:

- Local `.env.local`
- CI secrets
- Production hosting platform (e.g. Vercel project settings)

If the build step fails with "missing API key", that's why.

## 5. `.gitignore`

```
public/_gt/
```

The `public/_gt/` directory is regenerated on every build. Never commit it.

## 6. Content Security Policy

If you have a CSP, add `https://*.gtx.dev` to `connect-src`:

```ts
// in next.config.ts headers
"Content-Security-Policy": "connect-src 'self' https://*.gtx.dev ..."
```

Without this, the browser blocks the GT runtime fetch and locales silently
fall back to the source language.
