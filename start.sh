#!/bin/bash

# Stripe Invoice Sync - Startup Script
# Usage: ./start.sh [--debug|--reload|--help]

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Default values
MODE="normal"
HOST="0.0.0.0"
PORT="8000"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --debug|--reload)
            MODE="debug"
            shift
            ;;
        --host)
            HOST="$2"
            shift 2
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        --help|-h)
            echo "Stripe Invoice Sync - Startup Script"
            echo ""
            echo "Usage: ./start.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --debug, --reload    Run in debug mode with auto-reload"
            echo "  --host HOST         Set host address (default: 0.0.0.0)"
            echo "  --port PORT         Set port number (default: 8000)"
            echo "  --help, -h          Show this help message"
            echo ""
            echo "Examples:"
            echo "  ./start.sh                    # Run in production mode"
            echo "  ./start.sh --debug            # Run in debug mode with auto-reload"
            echo "  ./start.sh --port 8080        # Run on port 8080"
            echo "  ./start.sh --debug --port 8080 --host localhost"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Check if virtual environment is activated
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo -e "${YELLOW}Virtual environment not activated. Activating...${NC}"
    if [[ -f "venv/bin/activate" ]]; then
        source venv/bin/activate
    else
        echo -e "${RED}Virtual environment not found! Please create it first:${NC}"
        echo "python -m venv venv"
        echo "source venv/bin/activate"
        echo "pip install -r requirements.txt"
        exit 1
    fi
fi

# Check if .env file exists
if [[ ! -f ".env" ]]; then
    echo -e "${YELLOW}Warning: .env file not found!${NC}"
    echo "Please create .env file with your configuration:"
    echo "cp .env.example .env"
    echo ""
fi

# Display startup information
echo -e "${GREEN}Starting Stripe Invoice Sync...${NC}"
echo "Mode: $MODE"
echo "Host: $HOST"
echo "Port: $PORT"
echo ""

# Run the application based on mode
if [[ "$MODE" == "debug" ]]; then
    echo -e "${YELLOW}Running in DEBUG mode with auto-reload${NC}"
    echo "Press CTRL+C to stop"
    echo ""
    exec uvicorn app.main:app --reload --host "$HOST" --port "$PORT"
else
    echo -e "${GREEN}Running in PRODUCTION mode${NC}"
    echo "Press CTRL+C to stop"
    echo ""
    exec python -m app.main
fi