from fastapi import FastAPI, Form, File, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import openai
import base64
import tempfile
import os
import subprocess
from typing import Dict, List
from dotenv import load_dotenv
import traceback
import random

# Ladda miljövariabler från .env
load_dotenv()

# Hämta API-nycklar från miljövariabler
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ELEVEN_API_KEY = os.getenv("ELEVEN_API_KEY")
VOICE_ID = os.getenv("VOICE_ID", "Adam")

# Sätt OpenAI-nyckeln för gamla API:t
openai.api_key = OPENAI_API_KEY

# Skapa FastAPI-app
app = FastAPI()

# Tillåt frontend att prata med backend (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8080", "http://127.0.0.1:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Konversationshistorik per session
conversation_history: Dict[str, List[dict]] = {}

# --- Static quiz data grouped by level ---
QUIZ_QUESTIONS = {
    "1-2": [
        {"question": "Which hand wins at showdown: A♣ K♦ 8♠ 8♥ 3♣ or K♣ Q♠ Q♥ 10♦ 4♣?", "choices": ["A♣ K♦ 8♠ 8♥ 3♣", "K♣ Q♠ Q♥ 10♦ 4♣"], "answer": "K♣ Q♠ Q♥ 10♦ 4♣"},
        # ... (lägg till fler frågor här)
    ],
    "3-4": [
        {"question": "You face a half-pot bet of 50 $ into 100 $. How often must you win to break even on a call?", "choices": ["25 %", "33 %", "40 %", "50 %"], "answer": "25 %"},
        # ... (lägg till fler frågor här)
    ],
    # ... (lägg till övriga nivåer på samma sätt)
}

@app.get("/")
def root():
    return {"message": "API is running!"}

@app.post("/ask")
async def ask_gpt(request: Request, audio: UploadFile = File(None)):
    try:
        question = None
        session_id = request.headers.get("X-Session-ID", "default")
        skill_level = request.headers.get("X-Skill-Level", "1")  # Default to beginner if not specified
        try:
            skill_level = int(skill_level)
        except Exception:
            skill_level = 1
        
        # Om det är en multipart/form-data med audio
        if audio is not None:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_audio:
                content = await audio.read()
                temp_audio.write(content)
                temp_audio_path = temp_audio.name

            # Konvertera till .wav med ffmpeg
            temp_wav_path = temp_audio_path.replace('.mp4', '.wav')
            try:
                subprocess.run([
                    "ffmpeg", "-y", "-i", temp_audio_path, temp_wav_path
                ], check=True)
            except Exception as e:
                return JSONResponse(status_code=500, content={"error": f"FFmpeg error: {str(e)}"})

            try:
                # 2. Transkribera ljud med Whisper
                with open(temp_wav_path, "rb") as audio_file:
                    transcription = openai.Audio.transcribe(
                        model="whisper-1",
                        file=audio_file
                    )
                question = transcription["text"]
            finally:
                if os.path.exists(temp_audio_path):
                    os.unlink(temp_audio_path)
                if os.path.exists(temp_wav_path):
                    os.unlink(temp_wav_path)
        else:
            # Om det är JSON med text
            data = await request.json()
            question = data.get("text", "").strip()

        # Hämta eller skapa konversationshistorik för denna session
        if session_id not in conversation_history:
            conversation_history[session_id] = []

        # Lägg till användarens fråga i historiken
        conversation_history[session_id].append({"role": "user", "content": question})

        # Skapa systemmeddelande baserat på skicklighetsnivå
        if skill_level <= 2:
            system_message = (
                "You are Adam, a friendly and encouraging poker coach for complete beginners. "
                "Focus on explaining basic concepts like hand rankings, betting order, and simple odds. "
                "Use simple language and avoid poker slang. "
                "Be very patient and encouraging. "
                "Always explain everything step by step. "
                "Never use markdown or bold, only plain text. "
                "Always be brief and concise. Never give long or rambling answers. "
                "Always answer in English, regardless of the user's language."
            )
        elif skill_level <= 4:
            system_message = (
                "You are Adam, a supportive poker coach for comfortable beginners. "
                "Focus on position, pot odds, and basic pre-flop strategies. "
                "Introduce basic poker terminology like 'tight/loose' and 'pot control'. "
                "Keep explanations clear but slightly more technical. "
                "Never use markdown or bold, only plain text. "
                "Always be brief and concise. Never give long or rambling answers. "
                "Always answer in English, regardless of the user's language."
            )
        elif skill_level <= 6:
            system_message = (
                "You are Adam, a strategic poker coach for intermediate players. "
                "Focus on range analysis, continuation betting, and implied odds. "
                "Use moderate poker slang and include brief mathematical examples. "
                "Discuss stack-to-pot ratios and basic GTO concepts. "
                "Never use markdown or bold, only plain text. "
                "Always be brief and concise. Never give long or rambling answers. "
                "Always answer in English, regardless of the user's language."
            )
        elif skill_level <= 8:
            system_message = (
                "You are Adam, an advanced poker coach for experienced players. "
                "Focus on GTO deviations, blocker effects, and bet sizing trees. "
                "Use advanced terminology and discuss equity realization. "
                "Include detailed mathematical analysis and range visualization concepts. "
                "Never use markdown or bold, only plain text. "
                "Always be brief and concise. Never give long or rambling answers. "
                "Always answer in English, regardless of the user's language."
            )
        else:
            system_message = (
                "You are Adam, a high-stakes poker coach for professional players. "
                "Focus on solver-based strategies, node locking, and mixed strategy frequencies. "
                "Use advanced poker terminology and discuss complex game theory. "
                "Include detailed mathematical analysis and solver interpretations. "
                "Never use markdown or bold, only plain text. "
                "Always be brief and concise. Never give long or rambling answers. "
                "Always answer in English, regardless of the user's language."
            )

        # Skapa systemmeddelande och inkludera konversationshistorik
        messages = [
            {
                "role": "system",
                "content": system_message
            }
        ]
        
        # Lägg till konversationshistorik (max 10 senaste meddelanden)
        messages.extend(conversation_history[session_id][-10:])

        # 3. Skicka fråga till GPT-4.1 med konversationshistorik
        response = openai.ChatCompletion.create(
            model="gpt-4-turbo",
            messages=messages,
            max_tokens=150,
            temperature=0.9,
        )
        answer = response["choices"][0]["message"]["content"].strip()

        # Lägg till svaret i konversationshistoriken
        conversation_history[session_id].append({"role": "assistant", "content": answer})

        # 4. (Valfritt) Skicka GPT-svar till ElevenLabs för audio
        # Här behöver du anpassa beroende på ditt elevenlabs-paket och version
        # Om du inte använder ElevenLabs, kommentera bort nedan
        # from elevenlabs import ElevenLabs
        # client = ElevenLabs(api_key=ELEVEN_API_KEY)
        # audio_gen = client.generate(
        #     text=answer,
        #     voice=VOICE_ID,
        #     model="eleven_multilingual_v2"
        # )
        # audio_bytes = b"".join(audio_gen)
        # audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')

        # 5. Returnera bara text (eller lägg till audio_b64 om du använder ElevenLabs)
        return JSONResponse(content={
            "question": question, 
            "answer": answer
            # "audio_b64": audio_b64
        })
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

# --- Quiz endpoints (oförändrade, men byt openai_client mot openai.ChatCompletion.create) ---

@app.post("/quiz")
async def generate_quiz(request: Request):
    try:
        data = await request.json()
        skill_level = int(data.get("skill_level", 1))

        # Välj rätt prompt baserat på nivå
        if skill_level <= 2:
            prompt = (
                "Create 10 multiple-choice questions that test absolute hand strength in Texas Hold'em. "
                "For each, show two 5-card showdown hands, ask which one wins, and explain the answer in one sentence for learners. "
                "After the quiz, give a personal comment on what the player should practice next. "
                "Return as a JSON array: [{question, choices, correct, explanation}], and a final comment."
            )
        elif skill_level <= 4:
            prompt = (
                "Write 10 one-sentence scenarios that force the player to use basic pot odds or position. "
                "For each, give four answer choices (fold / call / min-raise / shove) and briefly state the correct choice with a short pot-odds calculation. "
                "After the quiz, give a personal comment on what the player should practice next. "
                "Return as a JSON array: [{question, choices, correct, explanation}], and a final comment."
            )
        elif skill_level <= 6:
            prompt = (
                "Generate 10 quiz spots from the turn in a cash game (100 bb effective) where villain's range is described in words. "
                "For each, ask which bet-sizing or line maximises EV, include board texture, and reveal solver-approximate equities in the explanation. "
                "After the quiz, give a personal comment on what the player should practice next. "
                "Return as a JSON array: [{question, choices, correct, explanation}], and a final comment."
            )
        elif skill_level <= 8:
            prompt = (
                "Pose 10 tournament hands (40 bb, 9-max, ICM in play) that test range construction and blocker logic. "
                "For each, give four nuanced options (e.g., small-bet, over-bet, check-call, check-fold) and in the answer justify with range vs. range equity and blocker effects. "
                "After the quiz, give a personal comment on what the player should practice next. "
                "Return as a JSON array: [{question, choices, correct, explanation}], and a final comment."
            )
        else:
            prompt = (
                "Create 10 solver-style quizzes: 200 bb deep, H2H on the river after a polarising 3-barrel in a 4-bet pot. "
                "For each, present exact hand ranges in notation, node-lock villain to a 25% over-fold, and ask for the optimal mixed strategy (bet sizes + frequencies) with GTO EV figures. "
                "Return the solver breakdown in the explanation. "
                "After the quiz, give a personal comment on what the player should practice next. "
                "Return as a JSON array: [{question, choices, correct, explanation}], and a final comment."
            )

        # Skicka prompt till GPT
        response = openai.ChatCompletion.create(
            model="gpt-4-turbo",
            messages=[{"role": "system", "content": "You are a world-class poker coach and quizmaster. Always answer in English and return only valid JSON."},
                      {"role": "user", "content": prompt}],
            max_tokens=1800,
            temperature=0.7,
        )
        # Försök att hitta JSON i svaret
        import re, json
        raw = response["choices"][0]["message"]["content"]
        try:
            match = re.search(r'(\[.*\])', raw, re.DOTALL)
            questions = json.loads(match.group(1)) if match else []
            comment_match = re.search(r'"final_comment"\s*:\s*"([^"]+)"', raw)
            final_comment = comment_match.group(1) if comment_match else "Great job!"
        except Exception:
            return JSONResponse(content={"error": "Could not parse quiz JSON.", "raw": raw})

        return JSONResponse(content={"questions": questions, "final_comment": final_comment})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/quiz_static")
async def quiz_static(request: Request):
    data = await request.json()
    skill_level = int(data.get("skill_level", 1))
    if skill_level <= 2:
        level_key = "1-2"
    elif skill_level <= 4:
        level_key = "3-4"
    else:
        level_key = "1-2"  # fallback
    questions = QUIZ_QUESTIONS.get(level_key, [])
    questions = random.sample(questions, min(10, len(questions)))
    questions_with_answer = [
        {"question": q["question"], "choices": q["choices"], "answer": q.get("answer"), "explanation": q.get("explanation", "")}
        for q in questions
    ]
    return JSONResponse(content={"questions": questions_with_answer})

@app.post("/quiz_feedback")
async def quiz_feedback(request: Request):
    data = await request.json()
    user_answers = data.get("answers", [])
    skill_level = int(data.get("skill_level", 1))
    if skill_level <= 2:
        level_key = "1-2"
    elif skill_level <= 4:
        level_key = "3-4"
    else:
        level_key = "1-2"  # fallback
    correct_questions = QUIZ_QUESTIONS.get(level_key, [])
    correct_dict = {q["question"]: q["answer"] for q in correct_questions}
    score = 0
    for ans in user_answers:
        q = ans.get("question")
        user_a = ans.get("user_answer")
        if q in correct_dict and user_a == correct_dict[q]:
            score += 1
    prompt = (
        "A poker player just completed a quiz. Here are the questions, their answers, and which were correct or incorrect. "
        "Give a concise, personal feedback (max 3-4 sentences, max 200 tokens). Do NOT use bold text. Use clear paragraph breaks (\n\n) for each new thought or topic. Focus on the most important improvement points.\n" +
        str(user_answers)
    )
    response = openai.ChatCompletion.create(
        model="gpt-4-turbo",
        messages=[{"role": "system", "content": "You are a world-class poker coach. Always answer in English."},
                  {"role": "user", "content": prompt}],
        max_tokens=200,
        temperature=0.7,
    )
    feedback = response["choices"][0]["message"]["content"].strip()
    return JSONResponse(content={"feedback": feedback, "score": score})