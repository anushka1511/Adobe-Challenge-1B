#!/bin/bash

# Start Ollama in background
ollama serve &

# Wait a few seconds for the server to be ready
sleep 5

# Run the tinyllama model in background
ollama run tinyllama &

# Optional: wait again if you want more safety
sleep 5

# Run your main script
python3 main.py
