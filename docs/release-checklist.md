# Release Checklist

Use this checklist before merging `develop` into `master` or deploying a tagged
build. The checklist is intentionally mechanical: if a step fails, fix it before
continuing.

## 1. Version And Docs

- `VERSION`, `pyproject.toml`, `src/translate_video/__init__.py`,
  `PUBLIC_ROADMAP.md`, and the latest `change.log` entry all reference the same
  SemVer version.
- `PUBLIC_ROADMAP.md` lists the current release as completed and moves unfinished
  work to the next planned release.
- `change.log` contains the user-visible release summary and verification notes.

## 2. Local Gate

```bash
make ci:quick
make test:release
```

`make ci:quick` is the required pull-request gate. `make test:release` is the
full pre-merge gate and includes browser E2E checks.

## 3. Docker Gate

```bash
docker build \
  --build-arg APP_VERSION="$(cat VERSION)" \
  --build-arg VCS_REF="$(git rev-parse HEAD)" \
  --build-arg BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  -t translate-video:release .

docker run --rm translate-video:release translate-video --help
```

For compose deployments, run:

```bash
APP_VERSION="$(cat VERSION)" \
APP_COMMIT="$(git rev-parse --short HEAD)" \
APP_BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
docker compose up -d --build
```

## 4. Smoke Checks

```bash
curl -fsS http://localhost:8002/api/version
curl -fsS http://localhost:8002/api/health
curl -fsS http://localhost:8002/metrics
```

Confirm that `/api/health` reports the expected version, commit, environment,
uptime, running project count, and resource fields.

## 5. Rollback Note

Keep the previous image tag and compose env values available until smoke checks
pass. Rollback is `docker compose up -d` with the previous image/tag and the
previous `.env`/compose variables.
