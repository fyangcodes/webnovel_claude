#!/bin/bash
# Test runner script for AI services

set -e  # Exit on error

cd "$(dirname "$0")/myapp"

echo "================================"
echo "AI Services Test Suite"
echo "================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Parse command line arguments
VERBOSE=""
COVERAGE=false
SPECIFIC_TEST=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--verbose)
            VERBOSE="-v 2"
            shift
            ;;
        -c|--coverage)
            COVERAGE=true
            shift
            ;;
        -t|--test)
            SPECIFIC_TEST="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -v, --verbose      Run tests with verbose output"
            echo "  -c, --coverage     Run tests with coverage report"
            echo "  -t, --test TEST    Run specific test (e.g., test_providers.TestOpenAIProvider)"
            echo "  -h, --help         Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                              # Run all tests"
            echo "  $0 -v                           # Run with verbose output"
            echo "  $0 -c                           # Run with coverage"
            echo "  $0 -t test_providers            # Run provider tests only"
            echo "  $0 -v -c                        # Verbose with coverage"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
    esac
done

# Set test target
if [ -n "$SPECIFIC_TEST" ]; then
    TEST_TARGET="ai_services.tests.$SPECIFIC_TEST"
    echo -e "${YELLOW}Running specific tests: $TEST_TARGET${NC}"
else
    TEST_TARGET="ai_services.tests"
    echo -e "${YELLOW}Running all AI services tests${NC}"
fi

echo ""

# Run tests with or without coverage
if [ "$COVERAGE" = true ]; then
    echo -e "${YELLOW}Running tests with coverage...${NC}"
    echo ""

    # Run with coverage
    coverage run --source='ai_services' manage.py test $TEST_TARGET $VERBOSE

    echo ""
    echo "================================"
    echo "Coverage Report"
    echo "================================"
    echo ""

    # Generate coverage report
    coverage report

    echo ""
    echo -e "${GREEN}Generating HTML coverage report...${NC}"
    coverage html
    echo -e "${GREEN}HTML report saved to: htmlcov/index.html${NC}"

else
    echo -e "${YELLOW}Running tests...${NC}"
    echo ""

    # Run without coverage
    python manage.py test $TEST_TARGET $VERBOSE
fi

# Check exit code
if [ $? -eq 0 ]; then
    echo ""
    echo "================================"
    echo -e "${GREEN}✓ All tests passed!${NC}"
    echo "================================"
    exit 0
else
    echo ""
    echo "================================"
    echo -e "${RED}✗ Tests failed${NC}"
    echo "================================"
    exit 1
fi
