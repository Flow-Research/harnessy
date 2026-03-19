#!/bin/bash
#
# Jarvis Runner Script
# Usage: ./run-jarvis.sh [command]
#
# Commands:
#   analyze  - Show workload analysis
#   suggest  - Generate AI suggestions
#   apply    - Apply pending suggestions
#   full     - Run full workflow (analyze → suggest → apply)
#   help     - Show this help
#

set -e

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load environment variables from .env
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
else
    echo "Error: .env file not found"
    echo "Create one with: cp .env.example .env"
    echo "Then add your ANTHROPIC_API_KEY"
    exit 1
fi

# Check API key is set
if [ -z "$ANTHROPIC_API_KEY" ] || [ "$ANTHROPIC_API_KEY" = "your-api-key-here" ]; then
    echo "Error: ANTHROPIC_API_KEY not configured"
    echo "Edit .env and add your API key from https://console.anthropic.com/"
    exit 1
fi

# Default to 14 days
DAYS=${JARVIS_DAYS:-14}

case "${1:-help}" in
    analyze)
        echo "📊 Analyzing schedule (next $DAYS days)..."
        uv run jarvis analyze --days "$DAYS"
        ;;
    suggest)
        echo "💡 Generating suggestions..."
        uv run jarvis suggest --days "$DAYS"
        ;;
    apply)
        echo "✅ Applying suggestions..."
        uv run jarvis apply
        ;;
    full)
        echo "🚀 Running full Jarvis workflow..."
        echo ""
        echo "Step 1/3: Analyzing schedule..."
        uv run jarvis analyze --days "$DAYS"
        echo ""
        echo "Step 2/3: Generating suggestions..."
        uv run jarvis suggest --days "$DAYS"
        echo ""
        echo "Step 3/3: Review and apply..."
        uv run jarvis apply
        ;;
    help|--help|-h|*)
        echo "Jarvis - Intelligent Task Scheduler for AnyType"
        echo ""
        echo "Usage: ./run-jarvis.sh [command]"
        echo ""
        echo "Commands:"
        echo "  analyze  - Show workload analysis"
        echo "  suggest  - Generate AI suggestions"
        echo "  apply    - Apply pending suggestions"
        echo "  full     - Run full workflow (analyze → suggest → apply)"
        echo "  help     - Show this help"
        echo ""
        echo "Environment variables:"
        echo "  JARVIS_DAYS  - Number of days to analyze (default: 14)"
        echo ""
        echo "Example:"
        echo "  ./run-jarvis.sh full              # Run everything"
        echo "  JARVIS_DAYS=7 ./run-jarvis.sh analyze  # Analyze 7 days"
        ;;
esac
