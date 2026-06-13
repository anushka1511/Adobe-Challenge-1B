FROM --platform=linux/amd64 python:3.9-slim

# Add Ollama to PATH
ENV PATH="/root/.ollama/bin:${PATH}"

# Install curl
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Install Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

# Set working directory
WORKDIR /app

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY main_v2.py ./main.py
COPY start.sh .

# Make start script executable
RUN chmod +x /app/start.sh

# ✅ Preload model (NO pkill; use PID tracking)
RUN ollama serve & \
    echo $! > /tmp/ollama_pid && \
    sleep 10 && \
    ollama pull tinyllama && \
    kill $(cat /tmp/ollama_pid)

# Set default command
ENTRYPOINT ["/app/start.sh"]
