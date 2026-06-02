#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import tempfile
import wave
from pathlib import Path

import av


def chunk_audio_to_wav(input_path: Path, chunk_minutes: int, temp_dir: Path) -> list[Path]:
    container = av.open(str(input_path))
    stream = container.streams.audio[0]
    resampler = av.audio.resampler.AudioResampler(format="s16", layout="mono", rate=16000)

    sample_rate = 16000
    channels = 1
    sample_width = 2
    samples_per_chunk = chunk_minutes * 60 * sample_rate

    chunk_paths: list[Path] = []
    chunk_index = 0
    chunk_samples = 0

    def start_chunk() -> tuple[Path, wave.Wave_write]:
        nonlocal chunk_index
        wav_path = temp_dir / f"chunk_{chunk_index:03d}.wav"
        wav_file = wave.open(str(wav_path), "wb")
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        chunk_index += 1
        return wav_path, wav_file

    wav_path, wav_file = start_chunk()

    for frame in container.decode(stream):
        resampled = resampler.resample(frame)
        if resampled is None:
            continue
        frames = resampled if isinstance(resampled, list) else [resampled]
        for out_frame in frames:
            pcm = out_frame.to_ndarray().tobytes()
            frame_samples = out_frame.samples
            if chunk_samples + frame_samples > samples_per_chunk and chunk_samples > 0:
                wav_file.close()
                chunk_paths.append(wav_path)
                chunk_samples = 0
                wav_path, wav_file = start_chunk()
            wav_file.writeframes(pcm)
            chunk_samples += frame_samples

    wav_file.close()
    chunk_paths.append(wav_path)
    container.close()
    return chunk_paths


def transcribe_remote(
    chunk_paths: list[Path],
    output_path: Path,
    remote_base_url: str,
    remote_model: str,
    api_key: str,
) -> None:
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=remote_base_url)
    parts: list[str] = []
    for idx, chunk_path in enumerate(chunk_paths, start=1):
        with chunk_path.open("rb") as audio_file:
            result = client.audio.transcriptions.create(
                model=remote_model,
                file=audio_file,
                response_format="text",
                language="zh",
            )
        text = result if isinstance(result, str) else str(result)
        parts.append(f"[Chunk {idx}]\n{text.strip()}\n")
    output_path.write_text("\n".join(parts), encoding="utf-8")


def transcribe_local(
    input_path: Path,
    output_path: Path,
    local_model: str,
    local_model_dir: Path | None,
) -> None:
    from faster_whisper import WhisperModel

    if local_model_dir is not None:
        local_model_dir.mkdir(parents=True, exist_ok=True)
        os.environ["HF_HOME"] = str(local_model_dir)
        os.environ["HUGGINGFACE_HUB_CACHE"] = str(local_model_dir / "hub")

    model = WhisperModel(local_model, device="cpu", compute_type="int8")
    segments, _info = model.transcribe(str(input_path), language="zh", vad_filter=True, beam_size=5)

    lines: list[str] = []
    for seg in segments:
        text = seg.text.strip()
        if text:
            lines.append(f"[{seg.start:.2f} --> {seg.end:.2f}] {text}")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Transcribe audio with local Whisper or remote Whisper API.")
    parser.add_argument("--provider", choices=["local", "remote"], default="local")
    parser.add_argument("--input", required=True, help="Input audio path")
    parser.add_argument("--output", required=True, help="Output transcript path")
    parser.add_argument("--chunk-minutes", type=int, default=10, help="Chunk length for remote API uploads")
    parser.add_argument("--local-model", default="base", help="Local faster-whisper model name")
    parser.add_argument("--local-model-dir", help="Local model cache directory")
    parser.add_argument("--remote-base-url", default=None, help="Remote API base URL")
    parser.add_argument("--remote-model", default="whisper-1", help="Remote model name")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.provider == "local":
        model_dir = Path(args.local_model_dir) if args.local_model_dir else None
        transcribe_local(input_path, output_path, args.local_model, model_dir)
        print(output_path)
        return 0

    api_key = os.environ.get("WHISPER_API_KEY")
    if not api_key:
        raise RuntimeError("Missing WHISPER_API_KEY environment variable")

    remote_base_url = args.remote_base_url or os.environ.get("WHISPER_BASE_URL")
    if not remote_base_url:
        raise RuntimeError("Missing remote base URL. Use --remote-base-url or WHISPER_BASE_URL.")

    with tempfile.TemporaryDirectory(dir=str(output_path.parent)) as tmp:
        temp_dir = Path(tmp)
        chunk_paths = chunk_audio_to_wav(input_path, args.chunk_minutes, temp_dir)
        transcribe_remote(chunk_paths, output_path, remote_base_url, args.remote_model, api_key)

    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
