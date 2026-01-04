#!/bin/bash
# CCP Quick Start Script
# Activates virtual environment and runs demo

set -e

echo "🚀 CCP - Continuous Chaos Prevention"
echo "===================================="
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    echo "📦 Installing dependencies..."
    pip install -r requirements.txt
else
    echo "✅ Virtual environment found"
    source venv/bin/activate
fi

echo "🔧 Environment: $(which python3)"
echo "📦 Python version: $(python3 --version)"
echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found!"
    echo "Creating from .env.example..."
    cp .env.example .env
    echo "📝 Please edit .env with your actual credentials"
    echo ""
fi

echo "Choose an option:"
echo "  1) Run end-to-end demo (7 seconds)"
echo "  2) Run failure injection tests (20 scenarios)"
echo "  3) Start Docker infrastructure"
echo "  4) Run specific component"
echo "  5) Exit"
echo ""

read -p "Enter choice [1-5]: " choice

case $choice in
    1)
        echo ""
        echo "🎬 Running end-to-end demo..."
        cd examples
        python3 demo_end_to_end.py
        ;;
    2)
        echo ""
        echo "💥 Running failure injection tests..."
        cd examples
        python3 failure_injection.py
        ;;
    3)
        echo ""
        echo "🐳 Starting Docker infrastructure..."
        cd docker
        docker-compose up -d
        echo "✅ Services started:"
        echo "   - Neo4j: http://localhost:7474"
        echo "   - Redis: localhost:6379"
        echo "   - Prometheus: http://localhost:9090"
        echo "   - Grafana: http://localhost:3000"
        ;;
    4)
        echo ""
        echo "Available components:"
        echo "  1) RCA Engine"
        echo "  2) Patch Generator"
        echo "  3) Safety Gate Orchestrator"
        echo "  4) Deployment Orchestrator"
        echo "  5) Post-Deployment Verifier"
        echo ""
        read -p "Enter component [1-5]: " component
        cd examples
        case $component in
            1) python3 rca_engine.py ;;
            2) python3 patch_generator.py ;;
            3) python3 safety_gate_orchestrator.py ;;
            4) python3 deployment_orchestrator.py ;;
            5) python3 post_deployment_verifier.py ;;
            *) echo "Invalid choice" ;;
        esac
        ;;
    5)
        echo "👋 Goodbye!"
        exit 0
        ;;
    *)
        echo "❌ Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "✅ Done!"
