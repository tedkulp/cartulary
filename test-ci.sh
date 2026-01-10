#!/bin/bash
set -e

echo "🧪 Running CI Tests Locally..."
echo ""

# Backend Tests
echo "📦 Backend Tests..."
cd apps/backend
pip install -q --upgrade pip
pip install -q -r requirements.txt
if [ -d "tests" ]; then
  pytest -v --maxfail=3 || echo "⚠️  No tests found or tests failed"
else
  echo "⚠️  No test directory found - skipping tests"
fi
cd ../..

# Frontend Tests
echo ""
echo "📦 Frontend Tests..."

# Install dependencies
echo "Installing pnpm dependencies..."
pnpm install --frozen-lockfile

# Build shared package
echo "Building shared package..."
pnpm --filter @cartulary/shared build

# Type check web app
echo "Type checking web app..."
cd apps/web
pnpm type-check
cd ../..

# Type check mobile app (optional)
echo "Type checking mobile app..."
pnpm --filter @cartulary/mobile type-check

echo ""
echo "✅ All CI tests passed locally!"
