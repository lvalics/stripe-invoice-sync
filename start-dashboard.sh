#!/bin/bash

# Start script for the React Dashboard

echo "Starting Stripe Invoice Sync Dashboard..."

# Navigate to dashboard directory
cd frontend/dashboard

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "Installing dependencies..."
    npm install
fi

# Start the dashboard
echo "Starting dashboard on http://localhost:3000"
npm start