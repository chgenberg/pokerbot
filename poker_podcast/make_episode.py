#!/usr/bin/env python3

import os
import textwrap
import datetime
from pathlib import Path
from typing import Optional
import io

from openai import OpenAI
from pydub import AudioSegment
from dotenv import load_dotenv
from elevenlabs.simple import generate, set_api_key

# Load environment variables
load_dotenv()

# Configuration
EXPERT_VOICE_ID = "pNInz6obpgDQGcFmaJgB"  # Adam
AMATEUR_VOICE_ID = "EXAVITQu4vr4xnSDxMaL"  # Bella
OUTPUT_DIR = Path("episodes")  # Directory to store generated episodes

# API Keys (temporary for testing)
OPENAI_API_KEY = "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"
ELEVEN_API_KEY = "sk_9717ef05f5a9966d21c74a1061d02fdd63edfb54135227f7"

def setup_clients() -> tuple[OpenAI, None]:
    """Initialize OpenAI client and set ElevenLabs API key."""
    set_api_key(ELEVEN_API_KEY)
    return OpenAI(api_key=OPENAI_API_KEY), None

def generate_script(client: OpenAI) -> str:
    """Generate a natural-sounding dialog between an expert and an amateur."""
    prompt_system = {
        "role": "system",
        "content": textwrap.dedent("""
            You are writing a podcast dialog between two people about poker strategy.
            - The expert (Adam, male) explains and leads the conversation.
            - The amateur (Bella, female) is curious, asks questions, and sometimes laughs or reacts spontantously.
            - The topic: Why check-raise the turn with Ah 5d on a 9s 4c 8s 5d board after both players checked the flop?
            - The dialog should be about 60 seconds long, with 8-12 short turns, and sound like real speech (with filler words, laughter, natural pauses, etc).
            - Mark each line with the speaker's name (Adam: or Bella:).
            - Make it lively, friendly, and easy to follow for beginners.
            - End with a punchy takeaway from Adam.
        """)
    }
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[prompt_system],
            max_tokens=400,
            temperature=0.9,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        raise RuntimeError(f"Failed to generate script: {str(e)}")

def generate_dialog_audio(script: str, output_path: Path) -> None:
    """Generate dialog audio from script and merge into one file."""
    # Split script into lines
    lines = [line.strip() for line in script.split('\n') if line.strip()]
    audio_segments = []
    for line in lines:
        if line.startswith("Adam:"):
            text = line.replace("Adam:", "").strip()
            voice_id = EXPERT_VOICE_ID
        elif line.startswith("Bella:"):
            text = line.replace("Bella:", "").strip()
            voice_id = AMATEUR_VOICE_ID
        else:
            continue
        # Generate audio for this line
        audio_bytes = generate(
            text=text,
            voice=voice_id,
            model="eleven_monolingual_v1"
        )
        # Load as AudioSegment
        segment = AudioSegment.from_mp3(io.BytesIO(audio_bytes))
        audio_segments.append(segment)
        # Add a short pause after each line
        audio_segments.append(AudioSegment.silent(400))
    # Concatenate all segments
    final_audio = sum(audio_segments)
    final_audio.export(str(output_path), format="mp3")

def main() -> Optional[str]:
    """Main function to generate a podcast episode."""
    try:
        OUTPUT_DIR.mkdir(exist_ok=True)
        openai_client, _ = setup_clients()
        print("Generating script...")
        script = generate_script(openai_client)
        print("\n=== Generated dialog ===\n", script)
        print("\nGenerating dialog audio...")
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = OUTPUT_DIR / f"episode_{timestamp}.mp3"
        generate_dialog_audio(script, output_file)
        print(f"\nSaved dialog podcast to {output_file}")
        return str(output_file)
    except Exception as e:
        print(f"Error: {str(e)}")
        return None

if __name__ == "__main__":
    main() 