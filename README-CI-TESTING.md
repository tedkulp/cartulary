# Local CI Testing

## Quick Frontend Test (Recommended)

Test just the frontend type-check that runs in CI:

```bash
just type-check-web
```

This does what GitHub Actions does:
1. Build the `@cartulary/shared` package
2. Run type-check on the web app

**Time**: ~3-5 seconds (vs 5+ minutes on GitHub)

## Full CI Run

To reproduce the whole `test` job — backend pytest with coverage, then the web
type-check — from a clean install:

```bash
just ci
```

## Using `act` (Full Workflow Simulation)

For testing the entire workflow including Docker builds:

```bash
# Test just the test job (fast)
act -j test

# Test entire workflow (slow - builds Docker images)
act push

# Test specific job
act -j build --matrix name:backend
```

**Note**: `act` requires Docker and downloads large runner images (~500MB-17GB depending on size chosen).

## Individual Steps

`just --list` shows everything; the pieces CI runs are:

```bash
# Backend tests
just test-backend

# Backend tests with coverage
just test-cov

# Build shared package
just build-shared

# Type check web only
just type-check-web

# Type check mobile only
just type-check-mobile

# Type check everything, mobile included
just type-check
```

## Tips

- **Before pushing**: Run `just test` to catch issues early
- **Faster iteration**: Test locally instead of waiting for CI
- **Debug CI failures**: Replicate the exact environment and commands
