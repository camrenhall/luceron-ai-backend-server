#!/bin/bash
# Quick smoke test runner for rapid development feedback

set -e

echo "🚀 Quick Smoke Tests - Fast Development Feedback"
echo "=================================================="

# Change to test directory
cd "$(dirname "$0")/.."

# Set environment variables if not already set
export DATABASE_URL=${DATABASE_URL:-'postgresql://postgres.bjooglksafuxdeknpaso:SgUHEBQv5vdWG0pF@aws-0-us-east-2.pooler.supabase.com:6543/postgres'}
export RESEND_API_KEY=${RESEND_API_KEY:-'dummy_key'}  
export AGENT_DB_BASE_URL=${AGENT_DB_BASE_URL:-'https://luceron-ai-backend-server-909342873358.us-central1.run.app'}

# Install dependencies if needed
if [ ! -f ".installed" ]; then
    echo "📦 Installing dependencies..."
    pip install -r requirements.txt
    touch .installed
fi

# Run smoke tests with timeout
echo "🧪 Running smoke tests..."
timeout 300s pytest -m smoke -v --tb=short --maxfail=2 --timeout=60 || {
    echo "❌ Smoke tests failed or timed out"
    exit 1
}

echo "✅ Smoke tests completed successfully!"
echo "   Ready for development work"