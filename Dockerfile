FROM node:24-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g --registry=https://registry.npmmirror.com supergateway

WORKDIR /app

COPY . /app/

RUN python3 -m py_compile /app/server.py

EXPOSE 8000

CMD ["supergateway", \
     "--stdio", "python3 -B /app/server.py", \
     "--outputTransport", "streamableHttp", \
     "--streamableHttpPath", "/mcp", \
     "--port", "8000", \
     "--host", "0.0.0.0"]
