#!/bin/bash

# Fly.io secrets setup script
# Run this after flyctl launch

echo "Setting up Fly.io secrets..."

# Set your Groq API key
read -p "Enter your GROQ_API_KEY: " GROQ_KEY
flyctl secrets set GROQ_API_KEY="$GROQ_KEY"

echo "✅ Secrets configured!"
echo ""
echo "Next steps:"
echo "1. flyctl deploy"
echo "2. flyctl open"
