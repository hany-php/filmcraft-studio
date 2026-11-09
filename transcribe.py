"""transcribe.py — local speech-to-text for the FilmCraft plugin.

The installed FilmCraft 0.19.0 build has no `whisper` feature, so its own
`transcript.generate` is disabled. This module fills the gap:

    FilmCraft exports the sequence audio as WAV  ->  Whisper runs locally on the
    CPU (torch + transformers, no cloud, no API key)  ->  words with time stamps
    are written both as JSON and in the shape `transcript.set` accepts, so they
    can be pushed back into the project for captions / text-based editing.

Usage:
    python transcribe.py --wav path.wav [--model openai/whisper-small] [--language ar] [--out transcript.json]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import wave

import numpy as np

TICKS_PER_SECOND = 254_016_000_000


def read_wav(path: str) -> tuple[np.ndarray, int]:
    with wave.open(path, "rb") as w:
        frames, channels, width, rate = w.getnframes(), w.getnchannels(), w.getsampwidth(), w.getframerate()
        raw = w.readframes(frames)
    dtype = {1: np.int8, 2: np.int16, 4: np.int32}[width]
    data = np.frombuffer(raw, dtype=dtype).astype(np.float32) / float(2 ** (8 * width - 1))
    if channels > 1:
        data = data.reshape(-1, channels).mean(axis=1)
    return data, rate


def resample(audio: np.ndarray, source_rate: int, target_rate: int = 16_000) -> np.ndarray:
    if source_rate == target_rate or audio.size == 0:
        return audio
    count = int(round(audio.size * target_rate / source_rate))
    src = np.arange(audio.size, dtype=np.float64)
    dst = np.linspace(0.0, audio.size - 1.0, count)
    return np.interp(dst, src, audio.astype(np.float64)).astype(np.float32)


def transcribe(wav_path: str, model: str, language: str | None, verbose: bool = True) -> dict:
    from transformers import pipeline

    started = time.time()
    audio, rate = read_wav(wav_path)
    audio = resample(audio, rate)
    if verbose:
        print(f"audio: {audio.size / 16000:.2f}s at 16 kHz, peak={float(np.abs(audio).max()):.3f}", flush=True)

    asr = pipeline("automatic-speech-recognition", model=model, device=-1)
    if verbose:
        print(f"model loaded in {time.time() - started:.1f}s: {model}", flush=True)

    kwargs = {"return_timestamps": "word"}
    gen = {}
    if language and language != "auto":
        gen["language"] = language
    gen["task"] = "transcribe"
    if gen:
        kwargs["generate_kwargs"] = gen
    result = asr({"raw": audio, "sampling_rate": 16000}, chunk_length_s=30, **kwargs)
    if verbose:
        print(f"transcribed in {time.time() - started:.1f}s", flush=True)

    chunks = result.get("chunks") or []
    words = []
    for chunk in chunks:
        text = (chunk.get("text") or "").strip()
        stamp = chunk.get("timestamp") or (0.0, 0.0)
        start = float(stamp[0] or 0.0)
        end = float(stamp[1]) if stamp[1] is not None else start
        if not text:
            continue
        words.append({
            "text": text,
            "start": int(round(start * TICKS_PER_SECOND)),
            "end": int(round(end * TICKS_PER_SECOND)),
        })
    return {
        "model": model,
        "language": language or "auto",
        "text": (result.get("text") or "").strip(),
        "words": words,
        "seconds": round(time.time() - started, 2),
    }


def to_filmcraft_payload(transcript: dict) -> dict:
    """The shape `transcript.set` takes (ticks, optional speaker)."""
    words = []
    for w in transcript["words"]:
        entry = {"text": w["text"], "start": w["start"], "end": w["end"]}
        if w.get("speaker") is not None:
            entry["speaker"] = w["speaker"]
        words.append(entry)
    return {"language": transcript.get("language") or "en", "speakers": [], "words": words}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wav", required=True)
    ap.add_argument("--model", default="openai/whisper-small")
    ap.add_argument("--language", default="ar")
    ap.add_argument("--out", default=None)
    ap.add_argument("--payload", default=None, help="also write the transcript.set payload here")
    args = ap.parse_args()

    result = transcribe(args.wav, args.model, args.language)
    payload = to_filmcraft_payload(result)
    result["payload"] = payload

    out = args.out or os.path.splitext(args.wav)[0] + ".transcript.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    if args.payload:
        with open(args.payload, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    print(json.dumps({"text": result["text"], "words": len(result["words"]),
                      "language": result["language"], "out": out,
                      "seconds": result["seconds"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
