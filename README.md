# NiMa CODE YZ

Production-ready TypeScript/Node.js project baseline with linting, formatting, tests, CI, and repository governance templates.

## Setup

1. Install Node.js 22+.
2. Install dependencies.
3. Run quality checks.

```bash
npm ci
npm run lint
npm test
npm run build
```

## Usage

Use exported modules from `src/` and keep tests in `tests/`.

Example:

```ts
import { sum } from "./src/index.js";

console.log(sum(2, 3));
```

## Development

Project structure:

- `src/`: application source code
- `tests/`: test suites
- `.github/workflows/`: CI definitions
- `.github/ISSUE_TEMPLATE/`: issue templates

Common commands:

```bash
npm run lint
npm run format
npm test
npm run build
```

Security and dependency checks:

- CI runs `npm audit --audit-level=high` on every push/PR.

## License

License: TBD
