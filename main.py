from fastapi import FastAPI, Form, Request
from fastapi.responses import Response
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.rest import Client
import os
from dotenv import load_dotenv
from ai_handler import analyze_spam, generate_response, detect_language

# Carica variabili d'ambiente
load_dotenv()

app = FastAPI()

# Configurazione Twilio
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Dizionario per tracciare le conversazioni
conversations = {}

# Configurazione voci per lingua
VOICE_CONFIG = {
    "it": {"voice": "Polly.Giorgio", "language": "it-IT"},
    "en": {"voice": "Polly.Joey", "language": "en-US"},
    "pl": {"voice": "Polly.Jacek", "language": "pl-PL"}
}

# Messaggi iniziali per lingua
GREETING_MESSAGES = {
    "it": "Pronto, chi parla?",
    "en": "Hello, who's calling?",
    "pl": "Halo, kto mówi?"
}

@app.get("/")
async def root():
    return {"status": "Spam Blocker attivo", "message": "Server funzionante - IT/EN/PL"}

@app.post("/voice/incoming")
async def handle_incoming_call(
    CallSid: str = Form(...),
    From: str = Form(...),
    To: str = Form(None)
):
    """Gestisce le chiamate in arrivo"""
    
    print(f"\n📞 Chiamata in arrivo da: {From}")
    print(f"CallSid: {CallSid}")
    
    # Inizializza la conversazione con lingua di default italiano
    conversations[CallSid] = {
        "caller": From,
        "messages": [],
        "spam_score": 0,
        "language": "it"  # Default, verrà rilevata dopo
    }
    
    # Crea risposta TwiML - usa italiano come default iniziale
    response = VoiceResponse()
    
    # Messaggio iniziale in italiano (neutro)
    response.say(
        GREETING_MESSAGES["it"],
        voice=VOICE_CONFIG["it"]["voice"],
        language=VOICE_CONFIG["it"]["language"]
    )
    
    # Raccoglie l'input vocale - hint per 3 lingue
    gather = Gather(
        input='speech',
        language='it-IT, en-US, pl-PL',  # Twilio proverà a riconoscere tutte e 3
        timeout=5,
        action='/voice/process-speech',
        speech_timeout='auto',
        hints='italiano, english, polski'  # Suggerimenti per il riconoscimento
    )
    
    response.append(gather)
    
    # Se non risponde
    response.say("Arrivederci.", voice=VOICE_CONFIG["it"]["voice"], language=VOICE_CONFIG["it"]["language"])
    response.hangup()
    
    return Response(content=str(response), media_type="application/xml")

@app.post("/voice/process-speech")
async def process_speech(
    CallSid: str = Form(...),
    SpeechResult: str = Form(None),
    From: str = Form(...),
    Confidence: float = Form(None)
):
    """Processa quello che dice il chiamante"""
    
    print(f"\n🗣️ Chiamante ha detto: '{SpeechResult}'")
    if Confidence:
        print(f"📊 Confidenza riconoscimento: {Confidence}")
    
    response = VoiceResponse()
    
    if not SpeechResult:
        # Usa la lingua salvata o default
        lang = conversations.get(CallSid, {}).get("language", "it")
        no_understand = {
            "it": "Non ho capito. Arrivederci.",
            "en": "I didn't understand. Goodbye.",
            "pl": "Nie zrozumiałem. Do widzenia."
        }
        response.say(
            no_understand[lang],
            voice=VOICE_CONFIG[lang]["voice"],
            language=VOICE_CONFIG[lang]["language"]
        )
        response.hangup()
        return Response(content=str(response), media_type="application/xml")
    
    # Rileva la lingua se è il primo messaggio
    if CallSid in conversations and len(conversations[CallSid]["messages"]) == 0:
        detected_lang = detect_language(SpeechResult)
        conversations[CallSid]["language"] = detected_lang
        print(f"🌍 Lingua rilevata: {detected_lang.upper()}")
    
    lang = conversations[CallSid]["language"]
    
    # Salva il messaggio
    if CallSid in conversations:
        conversations[CallSid]["messages"].append({
            "role": "caller",
            "content": SpeechResult
        })
    
    # Analizza se è spam con AI
    is_spam, spam_score, reason = analyze_spam(
        SpeechResult, 
        conversations[CallSid]["messages"],
        lang
    )
    
    print(f"🤖 Analisi spam: {spam_score}/10 - {reason}")
    
    conversations[CallSid]["spam_score"] = spam_score
    
    # Se è sicuramente spam, termina la chiamata
    if spam_score >= 7:
        reject_messages = {
            "it": "Mi dispiace, non sono interessato. Arrivederci.",
            "en": "I'm sorry, I'm not interested. Goodbye.",
            "pl": "Przepraszam, nie jestem zainteresowany. Do widzenia."
        }
        response.say(
            reject_messages[lang],
            voice=VOICE_CONFIG[lang]["voice"],
            language=VOICE_CONFIG[lang]["language"]
        )
        response.hangup()
        print("❌ Chiamata spam bloccata!")
        return Response(content=str(response), media_type="application/xml")
    
    # Se potrebbe essere spam, intrattieni il chiamante
    if spam_score >= 4:
        ai_response = generate_response(
            SpeechResult, 
            conversations[CallSid]["messages"], 
            mode="stall",
            language=lang
        )
        print(f"⏳ Risposta AI (intrattenimento): {ai_response}")
    else:
        # Sembra legittimo, sii cortese
        ai_response = generate_response(
            SpeechResult, 
            conversations[CallSid]["messages"], 
            mode="polite",
            language=lang
        )
        print(f"✅ Risposta AI (cortese): {ai_response}")
    
    conversations[CallSid]["messages"].append({
        "role": "assistant",
        "content": ai_response
    })
    
    # Rispondi con l'AI nella lingua corretta
    response.say(
        ai_response,
        voice=VOICE_CONFIG[lang]["voice"],
        language=VOICE_CONFIG[lang]["language"]
    )
    
    # Continua ad ascoltare nella lingua rilevata
    gather = Gather(
        input='speech',
        language=VOICE_CONFIG[lang]["language"],
        timeout=5,
        action='/voice/process-speech',
        speech_timeout='auto'
    )
    
    response.append(gather)
    
    # Messaggio di chiusura
    goodbye_messages = {
        "it": "Arrivederci.",
        "en": "Goodbye.",
        "pl": "Do widzenia."
    }
    response.say(
        goodbye_messages[lang],
        voice=VOICE_CONFIG[lang]["voice"],
        language=VOICE_CONFIG[lang]["language"]
    )
    response.hangup()
    
    return Response(content=str(response), media_type="application/xml")

@app.get("/conversations")
async def get_conversations():
    """Endpoint per vedere le conversazioni registrate"""
    return conversations

@app.get("/stats")
async def get_stats():
    """Statistiche sulle chiamate per lingua"""
    stats = {
        "total_calls": len(conversations),
        "by_language": {"it": 0, "en": 0, "pl": 0},
        "spam_blocked": 0,
        "legitimate": 0
    }
    
    for call in conversations.values():
        lang = call.get("language", "it")
        stats["by_language"][lang] += 1
        
        if call.get("spam_score", 0) >= 7:
            stats["spam_blocked"] += 1
        elif call.get("spam_score", 0) < 4:
            stats["legitimate"] += 1
    
    return stats

if __name__ == "__main__":
    import uvicorn
    print("🚀 Avvio server Spam Blocker multilingua...")
    print("🌍 Lingue supportate: IT 🇮🇹 | EN 🇺🇸 | PL 🇵🇱")
    print("📡 Il server sarà disponibile su http://localhost:8000")
    print("⚠️  Ricorda di avviare ngrok in un'altra finestra!")
    uvicorn.run(app, host="0.0.0.0", port=8000)