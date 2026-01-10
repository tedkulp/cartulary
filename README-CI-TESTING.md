# Local CI Testing

## Quick Frontend Test (Recommended)

Test just the frontend type-check that runs in CI:

```bash
./test-frontend.sh
```

This simulates exactly what GitHub Actions does:
1. Install pnpm dependencies
2. Build @cartulary/shared package
3. Run type-check on web app

**Time**: ~3-5 seconds (vs 5+ minutes on GitHub)

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

## Manual Commands

You can also run individual steps:

```bash
# Type check web
cd apps/web && pnpm type-check

# Type check mobile
pnpm --filter @cartulary/mobile type-check

# Build shared package
pnpm --filter @cartulary/shared build

# Run all type checks
pnpm type-check
```

## Tips

- **Before pushing**: Run `./test-frontend.sh` to catch issues early
- **Faster iteration**: Test locally instead of waiting for CI
- **Debug CI failures**: Replicate the exact environment and commands
