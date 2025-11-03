#!/bin/bash

# Load .env file if it exists
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Set defaults if not already set
export OPENAI_BASE_URL="${OPENAI_BASE_URL:-https://genai.rcac.purdue.edu/api}"
export OPENAI_MODEL="${OPENAI_MODEL:-gpt-oss:120b}"

# Check if API key is set
if [ -z "$OPENAI_API_KEY" ]; then
    echo "❌ Error: OPENAI_API_KEY not set!"
    echo "Please set it in your .env file or export it:"
    echo "  export OPENAI_API_KEY='your-api-key'"
    exit 1
fi

echo "✅ Starting with Docker Compose..."
echo "   Using API endpoint: $OPENAI_BASE_URL"
echo "   Using model: $OPENAI_MODEL"
docker compose up --build
