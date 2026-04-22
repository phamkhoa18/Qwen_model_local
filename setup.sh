#!/bin/bash
# ============================================
# VKS AI Platform - Setup Script (Linux/Mac)
# ============================================

echo "🏛️ ========================================="
echo "   VKS AI Platform - Auto Setup"
echo "========================================="

# 1. Install Python dependencies
echo ""
echo "📦 [1/4] Cài đặt Python dependencies..."
pip install -r requirements.txt

# 2. Check MongoDB
echo ""
echo "🍃 [2/4] Kiểm tra MongoDB..."
if command -v mongosh &> /dev/null; then
    echo "✅ MongoDB đã cài đặt"
else
    echo "⚠️  MongoDB chưa cài. Cài bằng Docker:"
    echo "    docker run -d --name vks-mongodb -p 27017:27017 mongo:7.0"
    echo ""
    echo "   Hoặc dùng docker-compose:"
    echo "    docker-compose up -d mongodb"
fi

# 3. Check Ollama
echo ""
echo "🤖 [3/4] Kiểm tra Ollama..."
if command -v ollama &> /dev/null; then
    echo "✅ Ollama đã cài đặt"
    echo "   Đang pull model Qwen3-30B-A3B..."
    ollama pull qwen3:30b-a3b
else
    echo "⚠️  Ollama chưa cài. Cài bằng:"
    echo "    curl -fsSL https://ollama.com/install.sh | sh"
    echo "    ollama serve &"
    echo "    ollama pull qwen3:30b-a3b"
fi

# 4. Create .env if not exists
echo ""
echo "⚙️  [4/4] Kiểm tra .env..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "✅ Đã tạo .env từ .env.example"
    echo "   ⚠️  Hãy sửa SECRET_KEY và ADMIN_PASSWORD trong .env!"
else
    echo "✅ .env đã tồn tại"
fi

# Done
echo ""
echo "🎉 ========================================="
echo "   Setup hoàn tất!"
echo ""
echo "   Chạy server:"
echo "     python -m uvicorn backend.main:app --reload"
echo ""
echo "   Hoặc dùng Docker:"
echo "     docker-compose up -d"
echo ""
echo "   Truy cập: http://localhost:8000"
echo "   Admin:    admin / vks@2024"
echo "========================================="
