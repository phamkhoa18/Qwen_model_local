# VKS AI Platform

Local AI API Platform for Vietnamese Legal System (Vien Kiem Sat Nhan Dan Viet Nam).

## Features

- **Chat Playground** - Google AI Studio-like interface
- **OpenAI-Compatible API** - `/v1/chat/completions` with streaming
- **API Key Management** - Create, revoke, rate limiting
- **Usage Tracking** - MongoDB-based analytics dashboard
- **Qwen3-30B-A3B** - MoE model, Vietnamese + reasoning optimized

## Tech Stack

- **Backend:** FastAPI + Ollama + MongoDB
- **Frontend:** Vanilla HTML/CSS/JS (premium dark theme)
- **Model:** Qwen3-30B-A3B (30B params, 3B active, ~18GB VRAM)
- **GPU:** RTX 5090 / RTX 4090 (24-32GB VRAM)

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start MongoDB
docker run -d --name mongodb -p 27017:27017 mongo:7.0

# 3. Start Ollama + pull model
ollama serve &
ollama pull qwen3:30b-a3b

# 4. Run server
python -m uvicorn backend.main:app --reload

# 5. Open http://localhost:8000
# Login: admin / vks@2024
```

## API Usage

```python
from openai import OpenAI

client = OpenAI(api_key="vks-YOUR_KEY", base_url="http://SERVER_IP:8000/v1")

response = client.chat.completions.create(
    model="qwen3:30b-a3b",
    messages=[
        {"role": "system", "content": "Ban la tro ly phap luat VKS"},
        {"role": "user", "content": "Giai thich Dieu 173 BLHS 2015"}
    ]
)
print(response.choices[0].message.content)
```

## Deploy to Vast.ai

```bash
# Upload code
deploy_to_vastai.bat <SSH_PORT>

# SSH and setup
ssh -p <PORT> root@<SERVER_IP>
chmod +x /root/setup_vastai.sh && /root/setup_vastai.sh
cd /root/vks-ai-platform && ./start.sh
```

## License

Private - VKS Internal Use Only
