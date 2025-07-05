#!/bin/bash

# Test script for LibreOffice Document Converter
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check dependencies
print_status $YELLOW "Checking dependencies..."

if ! command_exists python3; then
    print_status $RED "❌ Python3 is required but not installed"
    exit 1
fi

# Check Python version compatibility
print_status $YELLOW "Checking Python version compatibility..."
if python3 scripts/check_python.py; then
    print_status $GREEN "✅ Python compatibility check passed"
else
    print_status $RED "❌ Python compatibility check failed"
    exit 1
fi

# Install test dependencies
print_status $YELLOW "Installing test dependencies..."
pip install -r requirements-dev.txt

# Create test directories
mkdir -p temp
mkdir -p logs

# Set environment variables
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
export TESTING=true

# Run different test suites
run_tests() {
    local test_type=$1
    local test_args=$2
    
    print_status $YELLOW "Running $test_type tests..."
    
    if pytest $test_args --tb=short -v; then
        print_status $GREEN "✅ $test_type tests passed"
        return 0
    else
        print_status $RED "❌ $test_type tests failed"
        return 1
    fi
}

# Parse command line arguments
TEST_TYPE=${1:-all}
VERBOSE=${2:-false}

case $TEST_TYPE in
    "unit")
        run_tests "unit" "-m unit tests/"
        ;;
    "integration")
        print_status $YELLOW "Checking LibreOffice installation for integration tests..."
        if command_exists libreoffice; then
            print_status $GREEN "✅ LibreOffice found"
            run_tests "integration" "-m integration tests/"
        else
            print_status $YELLOW "⚠️  LibreOffice not found - skipping integration tests"
            print_status $YELLOW "To install LibreOffice: sudo apt-get install libreoffice"
        fi
        ;;
    "slow")
        run_tests "slow" "-m slow tests/"
        ;;
    "coverage")
        print_status $YELLOW "Running tests with coverage..."
        pytest --cov=app --cov-report=html --cov-report=term-missing tests/
        print_status $GREEN "✅ Coverage report generated in htmlcov/"
        ;;
    "all")
        print_status $YELLOW "Running all tests..."
        
        # Run unit tests first
        if ! run_tests "unit" "-m unit tests/"; then
            exit 1
        fi
        
        # Run integration tests if LibreOffice is available
        if command_exists libreoffice; then
            if ! run_tests "integration" "-m integration tests/"; then
                exit 1
            fi
        else
            print_status $YELLOW "⚠️  Skipping integration tests (LibreOffice not available)"
        fi
        
        print_status $GREEN "✅ All available tests passed"
        ;;
    "quick")
        run_tests "quick" "-m \"unit and not slow\" tests/"
        ;;
    *)
        print_status $RED "❌ Unknown test type: $TEST_TYPE"
        echo "Usage: $0 [unit|integration|slow|coverage|all|quick] [verbose]"
        echo ""
        echo "Test types:"
        echo "  unit        - Run unit tests only"
        echo "  integration - Run integration tests only"
        echo "  slow        - Run slow tests only"
        echo "  coverage    - Run tests with coverage report"
        echo "  all         - Run all available tests (default)"