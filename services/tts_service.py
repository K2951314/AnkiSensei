import asyncio
import os
import random

import edge_tts


async def generate_audio(text: str, output_path: str, voice: str) -> None:
    max_retries = int(os.getenv("TTS_MAX_RETRIES", "3"))
    backoff_base = float(os.getenv("TTS_BACKOFF_BASE", "1.6"))
    backoff_max = float(os.getenv("TTS_BACKOFF_MAX", "10"))

    for attempt in range(1, max_retries + 1):
        try:
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(output_path)
            return
        except Exception as exc:
            if attempt >= max_retries:
                raise RuntimeError(
                    f"Failed to generate audio at {output_path}: {exc}"
                ) from exc
            delay = min(backoff_max, backoff_base ** attempt) + random.uniform(0, 0.3)
            await asyncio.sleep(delay)
