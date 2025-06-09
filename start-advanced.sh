#!/bin/bash

# Advanced Stripe Invoice Sync Startup Script
# Includes health checks, logging, and process management

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
APP_NAME="Stripe Invoice Sync"
PID_FILE=".stripe_invoice_sync.pid"
LOG_DIR="logs"
LOG_FILE="$LOG_DIR/stripe_invoice_sync.log"

# Default values
MODE="normal"
HOST="0.0.0.0"
PORT="8000"
WORKERS=1
DAEMON=false

# Functions
show_help() {
    cat << EOF
$APP_NAME - Advanced Startup Script

Usage: ./start-advanced.sh [COMMAND] [OPTIONS]

Commands:
  start       Start the application
  stop        Stop the application
  restart     Restart the application
  status      Check application status
  logs        Show application logs
  health      Check application health

Options:
  --debug, --reload    Run in debug mode with auto-reload
  --daemon, -d         Run as daemon (background)
  --workers N          Number of workers (production only)
  --host HOST          Set host address (default: 0.0.0.0)
  --port PORT          Set port number (default: 8000)
  --log-level LEVEL    Set log level (DEBUG, INFO, WARNING, ERROR)
  --help, -h           Show this help message

Examples:
  ./start-advanced.sh start                    # Start in foreground
  ./start-advanced.sh start --daemon           # Start as daemon
  ./start-advanced.sh start --debug            # Start in debug mode
  ./start-advanced.sh start --workers 4        # Start with 4 workers
  ./start-advanced.sh stop                     # Stop the application
  ./start-advanced.sh logs                     # View logs
  ./start-advanced.sh health                   # Check health status
EOF
}

check_dependencies() {
    # Check Python
    if ! command -v python &> /dev/null; then
        echo -e "${RED}Error: Python is not installed${NC}"
        exit 1
    fi
    
    # Check virtual environment
    if [[ ! -d "venv" ]]; then
        echo -e "${RED}Error: Virtual environment not found${NC}"
        echo "Please run: python -m venv venv"
        exit 1
    fi
}

activate_venv() {
    if [[ -z "$VIRTUAL_ENV" ]]; then
        echo -e "${YELLOW}Activating virtual environment...${NC}"
        source venv/bin/activate
    fi
}

check_env_file() {
    if [[ ! -f ".env" ]]; then
        echo -e "${YELLOW}Warning: .env file not found!${NC}"
        if [[ -f ".env.example" ]]; then
            echo "Creating .env from .env.example..."
            cp .env.example .env
            echo -e "${YELLOW}Please edit .env with your configuration${NC}"
        fi
    fi
}

create_log_dir() {
    if [[ ! -d "$LOG_DIR" ]]; then
        mkdir -p "$LOG_DIR"
    fi
}

start_app() {
    echo -e "${GREEN}Starting $APP_NAME...${NC}"
    
    # Check if already running
    if [[ -f "$PID_FILE" ]]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo -e "${YELLOW}Application is already running (PID: $PID)${NC}"
            exit 1
        else
            rm "$PID_FILE"
        fi
    fi
    
    # Prepare environment
    check_dependencies
    activate_venv
    check_env_file
    create_log_dir
    
    # Build command
    if [[ "$MODE" == "debug" ]]; then
        CMD="uvicorn app.main:app --reload --host $HOST --port $PORT"
    else
        if [[ $WORKERS -gt 1 ]]; then
            CMD="uvicorn app.main:app --host $HOST --port $PORT --workers $WORKERS"
        else
            CMD="python -m app.main"
        fi
    fi
    
    # Add log level if specified
    if [[ -n "$LOG_LEVEL" ]]; then
        export LOG_LEVEL="$LOG_LEVEL"
    fi
    
    # Start application
    if [[ "$DAEMON" == true ]]; then
        echo "Starting in daemon mode..."
        echo "Logs: $LOG_FILE"
        nohup $CMD > "$LOG_FILE" 2>&1 &
        PID=$!
        echo $PID > "$PID_FILE"
        sleep 2
        
        # Check if started successfully
        if ps -p "$PID" > /dev/null; then
            echo -e "${GREEN}Application started successfully (PID: $PID)${NC}"
            echo "API: http://$HOST:$PORT"
            echo "Docs: http://$HOST:$PORT/docs"
        else
            echo -e "${RED}Failed to start application${NC}"
            rm "$PID_FILE"
            tail -n 20 "$LOG_FILE"
            exit 1
        fi
    else
        echo "Starting in foreground mode..."
        echo "Press CTRL+C to stop"
        echo ""
        exec $CMD
    fi
}

stop_app() {
    echo -e "${YELLOW}Stopping $APP_NAME...${NC}"
    
    if [[ ! -f "$PID_FILE" ]]; then
        echo "Application is not running (no PID file found)"
        exit 0
    fi
    
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        kill -TERM "$PID"
        echo "Waiting for process to stop..."
        
        # Wait up to 10 seconds
        for i in {1..10}; do
            if ! ps -p "$PID" > /dev/null 2>&1; then
                break
            fi
            sleep 1
        done
        
        # Force kill if still running
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "Force killing process..."
            kill -KILL "$PID"
        fi
        
        rm -f "$PID_FILE"
        echo -e "${GREEN}Application stopped${NC}"
    else
        echo "Application is not running (process not found)"
        rm -f "$PID_FILE"
    fi
}

check_status() {
    if [[ -f "$PID_FILE" ]]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo -e "${GREEN}Application is running (PID: $PID)${NC}"
            
            # Try to get health status
            if command -v curl &> /dev/null; then
                echo ""
                echo "Health check:"
                curl -s "http://$HOST:$PORT/health" | python -m json.tool || echo "Health check failed"
            fi
        else
            echo -e "${RED}Application is not running (stale PID file)${NC}"
            rm -f "$PID_FILE"
        fi
    else
        echo -e "${YELLOW}Application is not running${NC}"
    fi
}

show_logs() {
    if [[ -f "$LOG_FILE" ]]; then
        echo -e "${BLUE}=== Application Logs ===${NC}"
        tail -f "$LOG_FILE"
    else
        echo -e "${YELLOW}No log file found${NC}"
        echo "The application may be running in foreground mode or hasn't been started yet"
    fi
}

check_health() {
    echo -e "${BLUE}Checking application health...${NC}"
    
    if ! command -v curl &> /dev/null; then
        echo -e "${RED}Error: curl is not installed${NC}"
        exit 1
    fi
    
    # Check if application is running
    HEALTH_URL="http://$HOST:$PORT/health"
    
    if curl -s -f "$HEALTH_URL" > /dev/null 2>&1; then
        echo -e "${GREEN}Application is healthy${NC}"
        echo ""
        curl -s "$HEALTH_URL" | python -m json.tool
    else
        echo -e "${RED}Application is not responding${NC}"
        echo "Please check if the application is running: ./start-advanced.sh status"
    fi
}

# Parse command
COMMAND=$1
shift

# Parse options
while [[ $# -gt 0 ]]; do
    case $1 in
        --debug|--reload)
            MODE="debug"
            shift
            ;;
        --daemon|-d)
            DAEMON=true
            shift
            ;;
        --workers)
            WORKERS="$2"
            shift 2
            ;;
        --host)
            HOST="$2"
            shift 2
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        --log-level)
            LOG_LEVEL="$2"
            shift 2
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# Execute command
case $COMMAND in
    start)
        start_app
        ;;
    stop)
        stop_app
        ;;
    restart)
        stop_app
        sleep 2
        start_app
        ;;
    status)
        check_status
        ;;
    logs)
        show_logs
        ;;
    health)
        check_health
        ;;
    *)
        echo -e "${RED}Unknown command: $COMMAND${NC}"
        show_help
        exit 1
        ;;
esac