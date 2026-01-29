import os
from openai import OpenAI
from dotenv import load_dotenv
import re

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def detect_language(text: str) -> str:
    """
    Rileva la lingua del testo tra italiano, inglese e polacco
    
    Returns:
        str: 'it', 'en', o 'pl'
    """
    
    # Parole comuni per identificazione rapida
    italian_words = ['ciao', 'buongiorno', 'salve', 'pronto', 'grazie', 'prego', 'si', 'no', 'sono', 'chiamo']
    english_words = ['hello', 'hi', 'good', 'morning', 'thanks', 'yes', 'please', 'call', 'calling', 'offer']
    polish_words = ['cześć', 'dzień', 'dobry', 'halo', 'dzięki', 'tak', 'nie', 'jestem', 'dzwonię', 'proszę']
    
    text_lower = text.lower()
    
    # Conta parole per lingua
    it_count = sum(1 for word in italian_words if word in text_lower)
    en_count = sum(1 for word in english_words if word in text_lower)
    pl_count = sum(1 for word in polish_words if word in text_lower)
    
    # Se c'è un match chiaro, ritorna
    if it_count > en_count and it_count > pl_count:
        return 'it'
    elif en_count > it_count and en_count > pl_count:
        return 'en'
    elif pl_count > it_count and pl_count > en_count:
        return 'pl'
    
    # Altrimenti usa GPT per rilevare
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You detect language. Reply ONLY with: 'it' for Italian, 'en' for English, or 'pl' for Polish."},
                {"role": "user", "content": f"Detect language: {text}"}
            ],
            temperature=0,
            max_tokens=5
        )
        
        detected = response.choices[0].message.content.strip().lower()
        
        if detected in ['it', 'en', 'pl']:
            return detected
        else:
            return 'it'  # Default italiano
            
    except Exception as e:
        print(f"❌ Errore rilevamento lingua: {e}")
        return 'it'  # Default italiano


def analyze_spam(caller_message: str, conversation_history: list, language: str = 'it') -> tuple[bool, int, str]:
    """
    Analizza se una chiamata è spam usando GPT
    
    Args:
        caller_message: Messaggio del chiamante
        conversation_history: Storico conversazione
        language: 'it', 'en', o 'pl'
    
    Returns:
        tuple: (is_spam, spam_score 0-10, reason)
    """
    
    # Costruisci il contesto della conversazione
    context = "\n".join([
        f"{msg['role']}: {msg['content']}" 
        for msg in conversation_history
    ])
    
    # Prompt multilingua
    prompts = {
        'it': """Sei un sistema di rilevamento spam per chiamate telefoniche.

Analizza questa conversazione e determina se è spam/scam:

Conversazione:
{context}
Ultimo messaggio: {message}

Indicatori di spam:
- Offerte non richieste (energia, telefonia, assicurazioni)
- Richieste di dati personali/bancari
- Urgenza artificiosa ("offerta scade oggi")
- Premi/vincite non richiesti
- Chiamate registrate/robot
- Tono da call center aggressivo

Rispondi SOLO con questo formato:
SPAM_SCORE: [numero da 0 a 10]
REASON: [breve spiegazione in italiano]

0-3 = probabilmente legittimo
4-6 = sospetto, serve cautela  
7-10 = sicuramente spam/scam""",
        
        'en': """You are a spam detection system for phone calls.

Analyze this conversation and determine if it's spam/scam:

Conversation:
{context}
Last message: {message}

Spam indicators:
- Unsolicited offers (energy, telecom, insurance)
- Requests for personal/banking data
- Artificial urgency ("offer expires today")
- Unrequested prizes/winnings
- Recorded calls/robots
- Aggressive call center tone

Reply ONLY in this format:
SPAM_SCORE: [number from 0 to 10]
REASON: [brief explanation in English]

0-3 = probably legitimate
4-6 = suspicious, caution needed
7-10 = definitely spam/scam""",
        
        'pl': """Jesteś systemem wykrywania spamu dla połączeń telefonicznych.

Przeanalizuj tę rozmowę i określ, czy to spam/oszustwo:

Rozmowa:
{context}
Ostatnia wiadomość: {message}

Wskaźniki spamu:
- Niezamówione oferty (energia, telekomunikacja, ubezpieczenia)
- Prośby o dane osobowe/bankowe
- Sztuczna pilność ("oferta wygasa dzisiaj")
- Niezamówione nagrody/wygrane
- Nagrane połączenia/roboty
- Agresywny ton call center

Odpowiedz TYLKO w tym formacie:
SPAM_SCORE: [liczba od 0 do 10]
REASON: [krótkie wyjaśnienie po polsku]

0-3 = prawdopodobnie legalne
4-6 = podejrzane, potrzebna ostrożność
7-10 = zdecydowanie spam/oszustwo"""
    }
    
    prompt = prompts.get(language, prompts['it']).format(
        context=context,
        message=caller_message
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert at detecting spam phone calls."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=200
        )
        
        result = response.choices[0].message.content.strip()
        
        # Parse della risposta
        lines = result.split('\n')
        spam_score = 0
        reason = "Analisi non disponibile"
        
        for line in lines:
            if line.startswith("SPAM_SCORE:"):
                spam_score = int(line.split(":")[1].strip())
            elif line.startswith("REASON:"):
                reason = line.split(":", 1)[1].strip()
        
        is_spam = spam_score >= 7
        
        return is_spam, spam_score, reason
        
    except Exception as e:
        print(f"❌ Errore nell'analisi spam: {e}")
        return False, 5, f"Errore: {str(e)}"


def generate_response(caller_message: str, conversation_history: list, mode: str = "polite", language: str = 'it') -> str:
    """
    Genera una risposta appropriata usando GPT
    
    Args:
        caller_message: L'ultimo messaggio del chiamante
        conversation_history: Storico della conversazione
        mode: "polite" (cortese), "stall" (intrattenere), "reject" (rifiutare)
        language: 'it', 'en', o 'pl'
    
    Returns:
        str: La risposta da far dire all'AI
    """
    
    context = "\n".join([
        f"{msg['role']}: {msg['content']}" 
        for msg in conversation_history
    ])
    
    # System prompts per modalità e lingua
    system_prompts = {
        'stall': {
            'it': """Sei un assistente telefonico AI. Il tuo obiettivo è far perdere tempo a potenziali scammer 
            facendo domande vaghe, sembrando confuso, e allungando la conversazione. Sii educato ma evasivo.
            Risposte brevi (max 25 parole). Parla in italiano naturale.""",
            
            'en': """You are an AI phone assistant. Your goal is to waste potential scammers' time 
            by asking vague questions, seeming confused, and prolonging the conversation. Be polite but evasive.
            Brief responses (max 25 words). Speak in natural English.""",
            
            'pl': """Jesteś asystentem telefonicznym AI. Twoim celem jest marnowanie czasu potencjalnych oszustów 
            zadając niejasne pytania, udając zdezorientowanie i przedłużając rozmowę. Bądź uprzejmy ale unikający.
            Krótkie odpowiedzi (max 25 słów). Mów naturalnym polskim."""
        },
        'reject': {
            'it': """Sei un assistente telefonico AI. Rifiuta educatamente ma fermamente l'offerta.
            Sii breve e diretto (max 15 parole). Parla in italiano naturale.""",
            
            'en': """You are an AI phone assistant. Politely but firmly reject the offer.
            Be brief and direct (max 15 words). Speak in natural English.""",
            
            'pl': """Jesteś asystentem telefonicznym AI. Grzecznie ale stanowczo odrzuć ofertę.
            Bądź krótki i bezpośredni (max 15 słów). Mów naturalnym polskim."""
        },
        'polite': {
            'it': """Sei un assistente telefonico AI educato e professionale. 
            Rispondi cortesemente e chiedi il motivo della chiamata se non è chiaro.
            Risposte brevi (max 20 parole). Parla in italiano naturale come un essere umano.""",
            
            'en': """You are a polite and professional AI phone assistant. 
            Respond courteously and ask about the reason for the call if unclear.
            Brief responses (max 20 words). Speak in natural English like a human.""",
            
            'pl': """Jesteś uprzejmym i profesjonalnym asystentem telefonicznym AI. 
            Odpowiadaj grzecznie i pytaj o powód rozmowy, jeśli nie jest jasny.
            Krótkie odpowiedzi (max 20 słów). Mów naturalnym polskim jak człowiek."""
        }
    }
    
    system_prompt = system_prompts[mode][language]
    
    prompt_templates = {
        'it': """Conversazione finora:
{context}

Chiamante: {message}

Genera una risposta appropriata in italiano.""",
        
        'en': """Conversation so far:
{context}

Caller: {message}

Generate an appropriate response in English.""",
        
        'pl': """Dotychczasowa rozmowa:
{context}

Dzwoniący: {message}

Wygeneruj odpowiednią odpowiedź po polsku."""
    }
    
    prompt = prompt_templates[language].format(
        context=context,
        message=caller_message
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=100
        )
        
        ai_response = response.choices[0].message.content.strip()
        
        # Rimuovi eventuali virgolette o formattazione
        ai_response = ai_response.replace('"', '').replace("'", "")
        
        return ai_response
        
    except Exception as e:
        print(f"❌ Errore nella generazione risposta: {e}")
        
        # Risposte di fallback per lingua
        fallbacks = {
            'stall': {
                'it': "Scusi, può ripetere? Non ho capito bene.",
                'en': "Sorry, can you repeat? I didn't understand well.",
                'pl': "Przepraszam, może pan powtórzyć? Nie zrozumiałem dobrze."
            },
            'reject': {
                'it': "Non sono interessato, grazie. Arrivederci.",
                'en': "I'm not interested, thank you. Goodbye.",
                'pl': "Nie jestem zainteresowany, dziękuję. Do widzenia."
            },
            'polite': {
                'it': "Mi scusi, di cosa si tratta esattamente?",
                'en': "Excuse me, what is this about exactly?",
                'pl': "Przepraszam, o co dokładnie chodzi?"
            }
        }
        
        return fallbacks[mode][language]