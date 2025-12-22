"""Speech-to-Text service supporting OpenAI and Gemini providers."""

import logging
from typing import BinaryIO, Literal

from google import genai
from openai import OpenAI

logger = logging.getLogger(__name__)

# Default prompt for transcription
DEFAULT_PROMPT = (
    "Generate a verbatim speech-to-text transcript of the audio file "
    "in the same language as of the audio in the same script too. "
    "If the script of the language is unavailable use closest romanized version of it"
)


class SpeechToTextService:
    """Service for transcribing audio files using various AI providers."""

    def __init__(
        self, openai_api_key: str | None = None, gemini_api_key: str | None = None
    ):
        """Initialize the speech-to-text service.

        Args:
            openai_api_key: OpenAI API key (optional)
            gemini_api_key: Gemini API key (optional)
        """
        self.openai_client = OpenAI(api_key=openai_api_key) if openai_api_key else None
        self.gemini_client = (
            genai.Client(api_key=gemini_api_key) if gemini_api_key else genai.Client()
        )

    def transcribe_with_openai(
        self,
        audio_file: BinaryIO | str,
        model: str = "gpt-4o-transcribe",
        prompt: str | None = None,
        response_format: Literal["json", "text", "srt", "verbose_json", "vtt"] = "text",
    ):
        """Transcribe audio using OpenAI's Whisper API.

        Args:
            audio_file: Binary file object or file path to the audio file
            model: OpenAI model to use (default: "whisper-1")
            prompt: Optional prompt to guide transcription
            response_format: Format of the response (default: "text")

        Returns:
            Transcribed text

        Raises:
            Exception: If OpenAI client is not initialized or transcription fails
        """
        if not self.openai_client:
            raise Exception("OpenAI client not initialized. Please provide an API key.")

        try:
            # Handle file path vs file object
            if isinstance(audio_file, str):
                audio_file = open(audio_file, "rb")

            transcription = self.openai_client.audio.transcriptions.create(
                model=model,
                file=audio_file,
                response_format=response_format,
                prompt=prompt or DEFAULT_PROMPT,
            )

            logger.info(f"Successfully transcribed audio using OpenAI model: {model}")
            return (
                transcription if isinstance(transcription, str) else transcription.text
            )

        except Exception as e:
            logger.error(f"OpenAI transcription failed: {str(e)}", exc_info=True)
            raise

    def transcribe_with_gemini(
        self,
        audio_file_path: str,
        model: str = "gemini-2.5-flash",
        prompt: str | None = None,
    ):
        """Transcribe audio using Google Gemini API.

        Args:
            audio_file_path: Path to the audio file
            model: Gemini model to use (default: "gemini-2.0-flash-exp")
            prompt: Optional prompt to guide transcription

        Returns:
            Transcribed text

        Raises:
            Exception: If transcription fails
        """
        try:
            # Upload file to Geminic
            gemini_file = self.gemini_client.files.upload(file=audio_file_path)
            logger.info(f"Uploaded file to Gemini: {gemini_file.name}")

            # Generate transcription
            response = self.gemini_client.models.generate_content(
                model=model,
                contents=[prompt or DEFAULT_PROMPT, gemini_file],
            )

            logger.info(f"Successfully transcribed audio using Gemini model: {model}")
            return response.text or None

        except Exception as e:
            logger.error(f"Gemini transcription failed: {str(e)}", exc_info=True)
            raise

    def transcribe(
        self,
        audio_file: BinaryIO | str,
        provider: Literal["openai", "gemini"] = "openai",
        model: str | None = None,
        prompt: str | None = None,
    ):
        """Transcribe audio using the specified provider.

        Args:
            audio_file: Binary file object or file path to the audio file
            provider: AI provider to use ("openai" or "gemini")
            model: Model to use (provider-specific, optional)
            prompt: Optional prompt to guide transcription

        Returns:
            Transcribed text

        Raises:
            ValueError: If provider is not supported
            Exception: If transcription fails
        """
        if provider == "openai":
            return self.transcribe_with_openai(
                audio_file=audio_file,
                model=model or "gpt-4o-transcribe",
                prompt=prompt,
            )
        elif provider == "gemini":
            # Gemini requires file path, not file object
            file_path = audio_file if isinstance(audio_file, str) else audio_file.name
            return self.transcribe_with_gemini(
                audio_file_path=file_path,
                model=model or "gemini-2.5-flash",
                prompt=prompt,
            )
        else:
            raise ValueError(
                f"Unsupported provider: {provider}. Use 'openai' or 'gemini'."
            )


# util functions for direct usage
def transcribe_audio(
    audio_file: BinaryIO | str,
    provider: Literal["openai", "gemini"] = "openai",
    openai_api_key: str | None = None,
    gemini_api_key: str | None = None,
    model: str | None = None,
    prompt: str | None = None,
):
    """Convenience function to transcribe audio without creating a service instance.

    Args:
        audio_file: Binary file object or file path to the audio file
        provider: AI provider to use ("openai" or "gemini")
        openai_api_key: OpenAI API key (optional)
        gemini_api_key: Gemini API key (optional)
        model: Model to use (provider-specific, optional)
        prompt: Optional prompt to guide transcription

    Returns:
        Transcribed text
    """
    service = SpeechToTextService(
        openai_api_key=openai_api_key,
        gemini_api_key=gemini_api_key,
    )
    return service.transcribe(
        audio_file=audio_file,
        provider=provider,
        model=model,
        prompt=prompt,
    )
