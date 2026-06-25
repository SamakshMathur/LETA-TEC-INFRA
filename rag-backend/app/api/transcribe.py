"""
Voice transcription endpoint — powered by OpenAI Whisper (whisper-1).
Receives a raw audio file from MediaRecorder (webm/ogg/wav) and returns
the transcript with a domain-specific prompt that improves accuracy for
GST, FEMA, Company Law, and Income Tax terminology.
"""

import logging
from fastapi import APIRouter, File, UploadFile, HTTPException

from app.config import OPENAI_API_KEY

router = APIRouter()
logger = logging.getLogger("transcribe")

# Domain hint fed to Whisper as a prompt — dramatically improves recognition
# of legal/tax abbreviations, section numbers, and Indian English phrases.
_DOMAIN_PROMPT = (
    "GST, CGST, IGST, SGST, UTGST, ITC, input tax credit, DRC-01, DRC-03, DRC-07, "
    "ASMT-10, GSTR-1, GSTR-3B, GSTR-2A, GSTR-2B, GSTR-9, show cause notice, SCN, "
    "Section 16, Section 17, Section 73, Section 74, Section 54, Rule 86A, Rule 42, "
    "Rule 43, reverse charge mechanism, RCM, CBIC, AAR, advance ruling, "
    "input service distributor, ISD, composition scheme, e-way bill, LUT, "
    "FEMA, RBI, FDI, ODI, ECB, repatriation, adjudication, commissioner, "
    "income tax, TDS, TCS, Section 143, Section 147, CIT, ITAT, penalty, "
    "interest, demand, refund, appeal, tribunal, high court, supreme court."
)


@router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """
    Accepts an audio file (webm, ogg, wav, mp4, m4a) and returns
    a JSON object: { "transcript": "..." }
    """
    audio_bytes = await file.read()

    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file received.")

    if not OPENAI_API_KEY:
        raise HTTPException(
            status_code=503,
            detail=(
                "Voice transcription requires OPENAI_API_KEY to be set in your .env file. "
                "Add OPENAI_API_KEY=sk-... and restart the server."
            ),
        )

    try:
        import openai as _openai
        client = _openai.OpenAI(api_key=OPENAI_API_KEY)

        mime = file.content_type or "audio/webm"
        fname = file.filename or "recording.webm"

        logger.info(f"Transcribing audio | size={len(audio_bytes)} bytes | mime={mime}")

        response = client.audio.transcriptions.create(
            model="whisper-1",
            file=(fname, audio_bytes, mime),
            language="en",
            prompt=_DOMAIN_PROMPT,
            response_format="text",
        )

        transcript = response.strip() if isinstance(response, str) else str(response).strip()
        logger.info(f"Transcription complete | chars={len(transcript)}")
        return {"transcript": transcript}

    except _openai.AuthenticationError:
        raise HTTPException(status_code=401, detail="Invalid OPENAI_API_KEY — check your .env file.")
    except _openai.RateLimitError:
        raise HTTPException(status_code=429, detail="OpenAI rate limit hit — please wait a moment and try again.")
    except Exception as e:
        logger.error(f"Transcription error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
