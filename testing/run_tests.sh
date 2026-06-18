#!/bin/bash

# Get-Deep API Test Runner
# Simple script to execute comprehensive API tests

set -e

# Configuration
BASE_URL="${1:-http://localhost:8080}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_SCRIPT="$SCRIPT_DIR/comprehensive_api_test.py"

echo "🚀 Get-Deep API Test Runner"
echo "=================================="
echo "📍 Base URL: $BASE_URL"
echo "📁 Script Dir: $SCRIPT_DIR"
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed"
    exit 1
fi

# Check if test script exists
if [[ ! -f "$TEST_SCRIPT" ]]; then
    echo "❌ Test script not found: $TEST_SCRIPT"
    exit 1
fi

# Install requirements if needed
if [[ -f "$SCRIPT_DIR/requirements.txt" ]]; then
    echo "📦 Installing/updating requirements..."
    pip3 install -r "$SCRIPT_DIR/requirements.txt" --quiet
fi

# Create test results directory
mkdir -p "$SCRIPT_DIR/test_results"

echo "🔍 Starting API tests..."
echo ""

# Run the tests
python3 "$TEST_SCRIPT" "$BASE_URL"

# Capture exit code
exit_code=$?

echo ""
if [[ $exit_code -eq 0 ]]; then
    echo "✅ All tests completed successfully!"
    echo "📊 Check test_results/ directory for detailed reports"
else
    echo "❌ Some tests failed. Check the reports for details."
fi

# Show latest report files
echo ""
echo "📁 Generated reports:"
ls -la "$SCRIPT_DIR/test_results/"*.{json,html} 2>/dev/null | tail -2 || echo "No reports found"

exit $exit_code
