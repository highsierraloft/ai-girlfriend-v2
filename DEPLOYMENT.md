# 🚀 AI Girlfriend Bot - Production Deployment

## ✅ Status: Phase 3 Complete - Ready for Production!

The bot is fully functional with AI integration. All components work perfectly:
- ✅ Database (PostgreSQL)
- ✅ Redis (rate limiting & caching)  
- ✅ AI Service (Spice8B integration)
- ✅ Telegram Bot handlers
- ✅ Loan system & age verification
- ✅ Context management & token counting

## 🤖 Deploying with Your Spice8B Model

### 1. **Get Your Hugging Face Credentials**

You need:
- **Model name**: `your-username/spice8b`
- **API key**: `hf_xxxxxxxxxxxxxxxxxxxxxx`
- **Telegram token**: From @BotFather

### 2. **Configure Environment**

```bash
# Copy example config
cp env.example .env

# Edit with your real values
nano .env
```

**Required settings in `.env`:**
```env
# Telegram Bot
TELEGRAM_TOKEN=1234567890:your_real_telegram_bot_token

# Hugging Face - YOUR SPICE8B MODEL
HF_ENDPOINT=https://api-inference.huggingface.co/models/your-username/spice8b
HF_API_KEY=hf_your_real_hugging_face_api_key
HF_MODEL_NAME=your-username/spice8b

# Database (keep defaults or customize)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/ai_girlfriend
REDIS_URL=redis://localhost:6380/0

# AI Settings (tune for your model)
HF_MAX_TOKENS=512
HF_TEMPERATURE=0.8
HF_TOP_P=0.9
HF_REPETITION_PENALTY=1.1
```

### 3. **Launch Production**

```bash
# Start all services
docker compose up -d

# Check logs
docker compose logs bot -f

# Health check (if DEBUG=true)
# Send /health command to bot
```

### 4. **Expected Startup Logs**

✅ **Successful startup should show:**
```
INFO - Starting AI Girlfriend Bot v0.1.0
INFO - Database initialized  
INFO - Redis rate limiter initialized
INFO - AI service initialized successfully
INFO - All bot handlers registered
INFO - Bot application created successfully
INFO - Starting bot in polling mode
```

## 🧪 Testing Your Deployment

### Basic Test Flow:
1. **Start chat**: `/start` → Age verification
2. **Check balance**: `/loans` → Should show 10 loans
3. **Send message**: `"Hi Alice!"` → Should get AI response
4. **Check profile**: `/profile` → View settings
5. **Reset chat**: `/reset` → Clear history

### Debug Commands (DEBUG=true only):
- `/health` → AI service status
- Check logs for token counting and API calls

## 🔧 Troubleshooting

### Common Issues:

**❌ "Tokenizer failed to load"**
- ✅ **Solution**: This is normal! Bot uses fallback token counting
- The bot will work perfectly without the tokenizer

**❌ "API key invalid"**  
- ✅ **Solution**: Check your HF_API_KEY in .env
- Make sure it starts with `hf_`

**❌ "Model not found"**
- ✅ **Solution**: Verify HF_MODEL_NAME and HF_ENDPOINT
- Ensure your model is public or API key has access

**❌ "Rate limit exceeded"**
- ✅ **Solution**: Normal behavior, bot handles this gracefully
- Users see friendly "give me a minute" message

## 📊 Monitoring

### Key Metrics to Watch:
- **Bot uptime**: `docker compose ps`
- **Database connections**: Check PostgreSQL logs
- **Redis performance**: Monitor rate limiting
- **AI API calls**: HuggingFace usage dashboard
- **User activity**: Message logs in database

### Log Locations:
- **Bot logs**: `docker compose logs bot`
- **Database**: `docker compose logs postgres`  
- **Redis**: `docker compose logs redis`

## 🎯 Next Steps

Once deployed successfully, consider:

1. **🔒 Security**: Setup proper secrets management
2. **📈 Scaling**: Load balancer for multiple bot instances  
3. **💰 Payments**: Implement real payment gateways
4. **🖼️ Images**: Add SDXL image generation
5. **📊 Analytics**: User behavior tracking
6. **🔄 CI/CD**: Automated deployments

## ⚡ Quick Start Commands

```bash
# Full deployment from scratch
git clone <your-repo>
cd ai-girlfriend-v2
cp env.example .env
# Edit .env with your credentials
docker compose up -d

# Check everything is working
docker compose logs bot --tail=20
```

**🎉 Your AI girlfriend bot is ready for users!** 