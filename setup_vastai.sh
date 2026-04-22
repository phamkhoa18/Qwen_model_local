#!/bin/bash
# ============================================================
# VKS AI Platform - Vast.ai RTX 5090 Setup Script
# Instance: 35424893 | GPU: RTX 5090 32GB | $0.025/hr
# ============================================================

set -e

echo ""
echo "=============================================="
echo "  VKS AI Platform - Vast.ai Auto Setup"
echo "  GPU: RTX 5090 (32GB VRAM)"
echo "=============================================="
echo ""

# ============ 1. SYSTEM UPDATE ============
echo "[1/7] Updating system packages..."
apt update -y && apt upgrade -y
apt install -y curl wget git python3 python3-pip python3-venv \
    build-essential software-properties-common \
    nginx certbot

echo "[OK] System updated"

# ============ 2. INSTALL MONGODB ============
echo ""
echo "[2/7] Installing MongoDB 7.0..."

# Check if mongod is already running
if command -v mongod &> /dev/null; then
    echo "[OK] MongoDB already installed"
else
    # Import MongoDB GPG key and add repo
    curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | \
        gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor
    echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | \
        tee /etc/apt/sources.list.d/mongodb-org-7.0.list
    apt update -y
    apt install -y mongodb-org

    # Start MongoDB
    systemctl start mongod || mongod --fork --logpath /var/log/mongod.log --dbpath /data/db
    echo "[OK] MongoDB installed and started"
fi

# Ensure MongoDB is running
mkdir -p /data/db
mongod --fork --logpath /var/log/mongod.log --dbpath /data/db 2>/dev/null || true
echo "[OK] MongoDB is running"

# ============ 3. INSTALL OLLAMA ============
echo ""
echo "[3/7] Installing Ollama..."

if command -v ollama &> /dev/null; then
    echo "[OK] Ollama already installed"
else
    curl -fsSL https://ollama.com/install.sh | sh
    echo "[OK] Ollama installed"
fi

# Start Ollama in background
echo "Starting Ollama server..."
OLLAMA_HOST=0.0.0.0 ollama serve &>/var/log/ollama.log &
sleep 5

# Verify Ollama is running
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "[OK] Ollama server is running"
else
    echo "[WARN] Ollama may need a moment to start..."
    sleep 10
fi

# ============ 4. PULL QWEN3 MODEL ============
echo ""
echo "[4/7] Pulling Qwen3-30B-A3B model (~18GB)..."
echo "      This will take 5-15 minutes depending on network speed..."
echo ""

ollama pull qwen3:30b-a3b

echo ""
echo "[OK] Model Qwen3-30B-A3B downloaded successfully!"

# ============ 5. SETUP PROJECT ============
echo ""
echo "[5/7] Setting up VKS AI Platform..."

# Create project directory
PROJECT_DIR="/root/vks-ai-platform"
mkdir -p $PROJECT_DIR
cd $PROJECT_DIR

# Create Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Create requirements.txt
cat > requirements.txt << 'REQUIREMENTS'
fastapi==0.115.0
uvicorn[standard]==0.30.0
motor==3.5.0
pymongo==4.8.0
python-dotenv==1.0.1
httpx==0.27.0
pydantic==2.9.0
PyJWT==2.9.0
python-multipart==0.0.9
jinja2==3.1.4
passlib==1.7.4
REQUIREMENTS

pip install -r requirements.txt
echo "[OK] Python dependencies installed"

# ============ 6. DEPLOY CODE ============
echo ""
echo "[6/7] Deploying application code..."

# Create .env
cat > .env << 'ENVFILE'
APP_NAME=VKS AI Platform
APP_VERSION=1.0.0
DEBUG=false
SECRET_KEY=vks-production-secret-change-this-2024-random

HOST=0.0.0.0
PORT=8000

MONGODB_URI=mongodb://localhost:27017
MONGODB_DB=vks_ai_platform

OLLAMA_BASE_URL=http://localhost:11434
DEFAULT_MODEL=qwen3:30b-a3b

ADMIN_USERNAME=admin
ADMIN_PASSWORD=vks@2024

RATE_LIMIT_PER_MINUTE=30
ENVFILE

echo "[OK] Environment configured"
echo ""
echo "=============================================="
echo "  IMPORTANT: Upload your code now!"
echo ""
echo "  Option A - SCP from your local machine:"
echo "    scp -P <PORT> -r ./backend ./frontend root@1.193.139.71:$PROJECT_DIR/"
echo ""
echo "  Option B - Git clone:"
echo "    cd $PROJECT_DIR && git clone <your-repo> ."
echo ""
echo "  Option C - Code is already in place"
echo "=============================================="

# ============ 7. CREATE SYSTEMD SERVICES ============
echo ""
echo "[7/7] Creating system services..."

# Create Ollama service
cat > /etc/systemd/system/ollama-server.service << 'OLLAMA_SVC'
[Unit]
Description=Ollama LLM Server
After=network.target

[Service]
Type=simple
User=root
Environment="OLLAMA_HOST=0.0.0.0"
ExecStart=/usr/local/bin/ollama serve
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
OLLAMA_SVC

# Create VKS API service
cat > /etc/systemd/system/vks-api.service << VKSAPI
[Unit]
Description=VKS AI Platform API
After=network.target mongod.service ollama-server.service

[Service]
Type=simple
User=root
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$PROJECT_DIR/venv/bin:/usr/local/bin:/usr/bin"
ExecStart=$PROJECT_DIR/venv/bin/python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
VKSAPI

# Reload and enable services
systemctl daemon-reload
systemctl enable ollama-server.service 2>/dev/null || true
systemctl enable vks-api.service 2>/dev/null || true

echo "[OK] System services created"

# Create start/stop scripts
cat > $PROJECT_DIR/start.sh << 'START'
#!/bin/bash
echo "Starting VKS AI Platform..."

# Start MongoDB
mkdir -p /data/db
mongod --fork --logpath /var/log/mongod.log --dbpath /data/db 2>/dev/null || true

# Start Ollama
OLLAMA_HOST=0.0.0.0 ollama serve &>/var/log/ollama.log &
sleep 3

# Start API
cd /root/vks-ai-platform
source venv/bin/activate
nohup python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 &>/var/log/vks-api.log &

echo ""
echo "[OK] All services started!"
echo "  API:        http://$(hostname -I | awk '{print $1}'):8000"
echo "  Playground: http://$(hostname -I | awk '{print $1}'):8000/playground"
echo "  Ollama:     http://localhost:11434"
echo "  MongoDB:    mongodb://localhost:27017"
START
chmod +x $PROJECT_DIR/start.sh

cat > $PROJECT_DIR/stop.sh << 'STOP'
#!/bin/bash
echo "Stopping VKS AI Platform..."
pkill -f "uvicorn backend.main" 2>/dev/null || true
pkill -f "ollama serve" 2>/dev/null || true
mongod --shutdown 2>/dev/null || true
echo "[OK] All services stopped"
STOP
chmod +x $PROJECT_DIR/stop.sh

# ============ DONE ============
echo ""
echo "=============================================="
echo "  SETUP COMPLETE!"
echo "=============================================="
echo ""
echo "  Server IP:    1.193.139.71"
echo "  GPU:          RTX 5090 (32GB VRAM)"
echo "  Model:        Qwen3-30B-A3B"
echo "  Cost:         ~\$0.025/hr (~\$18/month)"
echo ""
echo "  Next steps:"
echo "  1. Upload your code (backend/ + frontend/ folders)"
echo "  2. Run: cd $PROJECT_DIR && ./start.sh"
echo "  3. Open: http://1.193.139.71:8000"
echo "  4. Login: admin / vks@2024"
echo ""
echo "  Quick commands:"
echo "    ./start.sh    - Start all services"
echo "    ./stop.sh     - Stop all services"
echo ""
echo "=============================================="
