#!/bin/bash
set -e

echo "🧪 Testing Frontend Type Check (CI simulation)..."
echo ""

# Install dependencies
echo "📦 Installing dependencies..."
pnpm install --frozen-lockfile

# Build shared package
echo "📦 Building shared package..."
pnpm --filter @cartulary/shared build

# Type check web app (exactly as CI does)
echo "🔍 Type checking web app..."
cd apps/web
pnpm type-check
cd ../..

echo ""
echo "✅ Frontend type-check passed! Ready for CI."
