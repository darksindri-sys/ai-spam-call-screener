# Spam Blocker – AI Spam Call Screener Eng-Ita-Pol

Automatic system that answers and analyzes unwanted phone calls using **Twilio** (voice) + **OpenAI** (intelligence).

## Features
- Auto-answers incoming calls
- Uses Twilio Speech-to-Text to understand the caller
- GPT evaluates if it's spam (score 0–10)
- Smart responses:
  - High spam → hangs up immediately
  - Suspicious → wastes the caller's time
  - Legitimate → polite / forwards call

## Tech Stack
- FastAPI + Uvicorn
- Twilio Programmable Voice
- OpenAI (recommended: gpt-4o-mini)
- Python 3.11
- ngrok (for local testing)

## Quick Local Setup

```bash
conda create -n spam-blocker python=3.11
conda activate spam-blocker
pip install -r requirements.txt
