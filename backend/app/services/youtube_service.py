import re
from urllib.parse import urlparse, parse_qs
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
    YouTubeRequestFailed
)

# Supported YouTube URL patterns
YOUTUBE_REGEX_PATTERNS = [
    r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/watch\?(?:.*&)?v=([a-zA-Z0-9_-]{11})',
    r'(?:https?:\/\/)?(?:www\.)?youtu\.be\/([a-zA-Z0-9_-]{11})',
    r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/embed\/([a-zA-Z0-9_-]{11})',
    r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/v\/([a-zA-Z0-9_-]{11})',
    r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/shorts\/([a-zA-Z0-9_-]{11})',
]


def extract_video_id(url: str) -> str:
    """
    Extract the 11-character YouTube video ID from various YouTube URL formats.
    """
    if not url or not isinstance(url, str):
        raise ValueError("A valid YouTube URL must be provided.")

    clean_url = url.strip()

    # Check direct video ID format
    if re.match(r'^[a-zA-Z0-9_-]{11}$', clean_url):
        return clean_url

    for pattern in YOUTUBE_REGEX_PATTERNS:
        match = re.search(pattern, clean_url)
        if match:
            return match.group(1)

    # Fallback to query parameter parsing
    parsed = urlparse(clean_url)
    if "youtube.com" in parsed.netloc:
        query_params = parse_qs(parsed.query)
        if "v" in query_params and len(query_params["v"]) > 0:
            return query_params["v"][0]

    raise ValueError(
        f"Could not extract a valid YouTube video ID from the provided URL: '{url}'. "
        "Please provide a standard YouTube video or shorts URL."
    )


def fetch_youtube_transcript(url: str, languages: list[str] = None) -> str:
    """
    Fetch and clean transcript text from a YouTube video URL using youtube-transcript-api.
    """
    video_id = extract_video_id(url)

    if not languages:
        languages = ["en", "en-US", "en-GB"]

    try:
        api = YouTubeTranscriptApi()

        try:
            # 1. Try fetching directly in preferred languages
            transcript_obj = api.fetch(video_id, languages=languages)
        except NoTranscriptFound:
            # 2. Resilient fallback: Check all available transcripts for this video
            try:
                transcript_list = api.list(video_id)
                available = list(transcript_list)
                if not available:
                    raise ValueError(
                        "No transcripts or closed captions were found for this YouTube video."
                    )
                # If available and translatable to English, translate; otherwise fetch native
                candidate = available[0]
                if candidate.is_translatable:
                    transcript_obj = candidate.translate("en").fetch()
                else:
                    transcript_obj = candidate.fetch()
            except (TranscriptsDisabled, VideoUnavailable):
                raise
            except Exception as inner_e:
                raise ValueError(
                    "No matching transcript was found for this YouTube video in the requested languages."
                ) from inner_e

        # Extract text snippets
        snippets = transcript_obj.snippets
        if not snippets:
            raise RuntimeError("The transcript retrieved for this video is empty.")

        text_parts = [snippet.text.strip() for snippet in snippets if snippet.text and snippet.text.strip()]
        full_text = " ".join(text_parts).strip()

        # Clean music and formatting tokens often found in YouTube auto-captions
        cleaned_text = re.sub(r'\[[a-zA-Z\s]+\]', '', full_text)
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()

        if not cleaned_text:
            raise RuntimeError("No readable speech content found in the video transcript.")

        return cleaned_text

    except TranscriptsDisabled as e:
        raise ValueError(
            "Transcripts or closed captions are disabled for this YouTube video."
        ) from e

    except NoTranscriptFound as e:
        raise ValueError(
            "No matching transcript was found for this YouTube video in the requested languages."
        ) from e

    except VideoUnavailable as e:
        raise ValueError(
            "The requested YouTube video is unavailable, private, or has been removed."
        ) from e

    except YouTubeRequestFailed as e:
        raise RuntimeError(
            f"Failed to communicate with YouTube: {str(e)}"
        ) from e

    except (ValueError, RuntimeError):
        raise

    except Exception as e:
        raise RuntimeError(
            f"An error occurred while retrieving the YouTube transcript: {str(e)}"
        ) from e
