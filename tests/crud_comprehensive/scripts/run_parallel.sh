#!/bin/bash
# Parallel test execution for faster CI/CD feedback

set -e

echo "⚡ Parallel Test Execution"
echo "========================="

cd "$(dirname "$0")/.."

# Environment setup
export DATABASE_URL=${DATABASE_URL:-'postgresql://postgres.bjooglksafuxdeknpaso:SgUHEBQv5vdWG0pF@aws-0-us-east-2.pooler.supabase.com:6543/postgres'}
export RESEND_API_KEY=${RESEND_API_KEY:-'dummy_key'}
export AGENT_DB_BASE_URL=${AGENT_DB_BASE_URL:-'https://luceron-ai-backend-server-909342873358.us-central1.run.app'}

# Detect CPU cores
CORES=$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo "2")
WORKERS=$((CORES > 4 ? 4 : CORES))  # Cap at 4 workers

echo "🔧 Configuration:"
echo "   CPU Cores: $CORES"
echo "   Test Workers: $WORKERS"
echo "   Timeout: 600s per test"

# Install parallel execution dependencies
pip install pytest-xdist pytest-html pytest-json-report pytest-timeout

# Run tests in parallel
echo "🧪 Running parallel test suite..."

timeout 1200s pytest \
    -n $WORKERS \
    --dist=loadgroup \
    -v --tb=short \
    --timeout=300 \
    --maxfail=5 \
    --json-report --json-report-file=parallel-results.json \
    --html=parallel-report.html --self-contained-html \
    || {
        echo "❌ Parallel tests failed or timed out"
        echo "📄 Check parallel-results.json and parallel-report.html for details"
        exit 1
    }

echo "✅ Parallel test execution completed successfully!"
echo "📊 Results available in:"
echo "   - parallel-results.json (machine readable)"  
echo "   - parallel-report.html (human readable)"