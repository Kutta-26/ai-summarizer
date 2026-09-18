import os
import subprocess
import tempfile
import sys
import types
import time

from app.core.config import WHISPER_MODEL_SIZE
from app.core.logging_config import get_logger

logger = get_logger("media")


# ============================================================
# CONFIGURATION
# ============================================================

ALLOWED_MEDIA_EXTENSIONS = {
    ".mp3",
    ".wav",
    ".m4a",
    ".mp4",
    ".mkv",
    ".mov",
    ".webm",
    ".avi",
    ".flac",
    ".ogg",
}


# ============================================================
# WHISPER MODEL & ROBUST AUDIO BACKEND
# ============================================================

_whisper_model = None


def _ensure_whisper_audio_backend():
    """
    Ensures faster-whisper audio decoding works even on environments where
    PyAV (av) is blocked by OS code-integrity policies (e.g. Windows Smart App Control).
    Uses the system's verified FFmpeg CLI to decode media into 16kHz mono float32 waveforms.
    """
    try:
        import av  # Check if PyAV can be imported normally
    except Exception:
        # PyAV DLL load blocked or unavailable: stub av and provide ffmpeg fallback
        if "av" not in sys.modules:
            dummy_av = types.ModuleType("av")
            dummy_av.audio = types.ModuleType("audio")
            dummy_av.audio.resampler = types.ModuleType("resampler")
            sys.modules["av"] = dummy_av
            sys.modules["av.audio"] = dummy_av.audio
            sys.modules["av.audio.resampler"] = dummy_av.audio.resampler

        import numpy as np
        import faster_whisper.audio
        import faster_whisper.transcribe

        def ffmpeg_decode(input_file, sampling_rate=16000, split_stereo=False):
            cmd = [
                "ffmpeg",
                "-nostdin",
                "-threads", "0",
                "-i", str(input_file),
                "-f", "s16le",
                "-ac", "1",
                "-acodec", "pcm_s16le",
                "-ar", str(sampling_rate),
                "-"
            ]
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True
            )
            return np.frombuffer(proc.stdout, np.int16).flatten().astype(np.float32) / 32768.0

        faster_whisper.audio.decode_audio = ffmpeg_decode
        faster_whisper.transcribe.decode_audio = ffmpeg_decode


def get_whisper_model():
    """
    Load the Whisper model only when it is first needed.

    Keeping the model lazy-loaded prevents the application
    from loading Whisper during every server startup.
    """
    global _whisper_model

    if _whisper_model is None:
        try:
            _ensure_whisper_audio_backend()
            from faster_whisper import WhisperModel
            _whisper_model = WhisperModel(
                WHISPER_MODEL_SIZE,
                device="cpu",
                compute_type="int8"
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to initialize local Whisper speech model ({WHISPER_MODEL_SIZE}): {str(e)}"
            ) from e

    return _whisper_model



# ============================================================
# MEDIA FILE VALIDATION
# ============================================================

def validate_media_file(filename: str):
    """
    Validate the uploaded audio/video file extension.
    """

    if not filename:
        raise ValueError(
            "No media filename was provided."
        )

    extension = os.path.splitext(
        filename
    )[1].lower()

    if extension not in ALLOWED_MEDIA_EXTENSIONS:

        supported = ", ".join(
            sorted(ALLOWED_MEDIA_EXTENSIONS)
        )

        raise ValueError(
            f"Unsupported media format '{extension}'. "
            f"Supported formats are: {supported}."
        )

    return extension


# ============================================================
# EXTRACT AUDIO USING FFMPEG
# ============================================================

def extract_audio(media_path: str) -> str:
    """
    Extract audio from an audio/video file using FFmpeg.

    Returns:
        Path to the temporary WAV audio file.
    """

    if not os.path.exists(media_path):

        raise FileNotFoundError(
            "Media file was not found."
        )

    audio_path = tempfile.NamedTemporaryFile(
        suffix=".wav",
        delete=False
    ).name

    command = [
        "ffmpeg",
        "-y",
        "-i",
        media_path,
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        audio_path
    ]

    try:
        start_t = time.perf_counter()
        logger.info("Starting FFmpeg audio extraction...")
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=120
        )

        if result.returncode != 0:

            if os.path.exists(audio_path):
                os.remove(audio_path)

            raise RuntimeError(
                "FFmpeg failed to extract audio.\n"
                f"{result.stderr}"
            )

        if not os.path.exists(audio_path):

            raise RuntimeError(
                "FFmpeg completed but no audio file was produced."
            )

        if os.path.getsize(audio_path) == 0:

            os.remove(audio_path)

            raise RuntimeError(
                "The extracted audio file is empty."
            )

        elapsed = time.perf_counter() - start_t
        logger.info(f"FFmpeg audio extraction completed in {elapsed * 1000.0:.1f}ms ({os.path.getsize(audio_path)} bytes)")
        return audio_path

    except subprocess.TimeoutExpired as e:

        if os.path.exists(audio_path):
            os.remove(audio_path)

        raise RuntimeError(
            "Audio extraction timed out after 120 seconds."
        ) from e

    except FileNotFoundError as e:

        if os.path.exists(audio_path):
            os.remove(audio_path)

        raise RuntimeError(
            "FFmpeg was not found. "
            "Make sure FFmpeg is installed and available in PATH."
        ) from e


# ============================================================
# TRANSCRIBE AUDIO USING WHISPER
# ============================================================

def transcribe_audio(audio_path: str) -> str:
    """
    Transcribe an audio file using faster-whisper.
    """

    if not os.path.exists(audio_path):

        raise FileNotFoundError(
            "Audio file was not found."
        )

    model = get_whisper_model()

    start_t = time.perf_counter()
    logger.info("Starting Whisper audio transcription...")

    try:

        segments, info = model.transcribe(
            audio_path,
            beam_size=5,
            vad_filter=True
        )

        transcript_parts = []

        for segment in segments:

            text = segment.text.strip()

            if text:
                transcript_parts.append(text)

        transcript = " ".join(
            transcript_parts
        ).strip()

        if not transcript:

            raise RuntimeError(
                "Whisper did not detect any speech "
                "in the media file."
            )

        elapsed = time.perf_counter() - start_t
        logger.info(
            f"Whisper transcription completed in {elapsed * 1000.0:.1f}ms "
            f"(language: {getattr(info, 'language', 'unknown')}, segments: {len(transcript_parts)})"
        )
        return transcript

    except Exception as e:

        raise RuntimeError(
            f"Audio transcription failed: {str(e)}"
        ) from e


# ============================================================
# MEDIA → TRANSCRIPT
# ============================================================

def transcribe_media(media_path: str) -> str:
    """
    Convert an audio/video file into a text transcript.

    For video files:
        Video → FFmpeg → Audio → Whisper → Transcript

    For audio files:
        Audio → Whisper → Transcript
    """

    extension = os.path.splitext(
        media_path
    )[1].lower()

    audio_path = None

    try:

        # ----------------------------------------------------
        # Video formats need FFmpeg audio extraction
        # ----------------------------------------------------

        video_extensions = {
            ".mp4",
            ".mkv",
            ".mov",
            ".webm",
            ".avi"
        }

        if extension in video_extensions:

            audio_path = extract_audio(
                media_path
            )

        else:

            # ------------------------------------------------
            # Audio files can be sent directly to Whisper
            # ------------------------------------------------

            audio_path = media_path

        # ----------------------------------------------------
        # Transcribe audio
        # ----------------------------------------------------

        transcript = transcribe_audio(
            audio_path
        )

        return transcript

    finally:

        # ----------------------------------------------------
        # Delete temporary extracted audio
        # ----------------------------------------------------

        if (
            audio_path
            and audio_path != media_path
            and os.path.exists(audio_path)
        ):

            os.remove(audio_path)