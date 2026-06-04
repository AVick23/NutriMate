"""
Бесплатный распознаватель голоса через Google Web Speech API.
"""
import io
import logging
from typing import Optional
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

try:
    import speech_recognition as sr
    HAS_SPEECH_RECOGNITION = True
except ImportError:
    HAS_SPEECH_RECOGNITION = False
    sr = None
    logger.error("SpeechRecognition не установлен! Установи: pip install SpeechRecognition")


class VoiceRecognizer:
    """Бесплатный распознаватель голосовых сообщений."""

    def __init__(self):
        if HAS_SPEECH_RECOGNITION:
            self.recognizer = sr.Recognizer()
            self.recognizer.energy_threshold = 300
            logger.info("✅ Google Speech Recognition инициализирован")
        else:
            self.recognizer = None

    async def recognize(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> Optional[str]:
        """
        Распознаёт голосовое сообщение через Google Web Speech API.
        Бесплатно, без API ключей.
        """
        if not self.recognizer:
            logger.error("SpeechRecognition недоступен")
            return None

        if not update.message or not update.message.voice:
            return None

        try:
            # Скачиваем аудио
            voice = update.message.voice
            file = await context.bot.get_file(voice.file_id)
            file_bytes = await file.download_as_bytearray()

            # Конвертируем OGG → WAV (нужно для Google Speech)
            wav_bytes = await self._convert_ogg_to_wav(file_bytes)
            if not wav_bytes:
                return None

            # Распознаём
            return await self._recognize_with_google(wav_bytes)

        except Exception as e:
            logger.error(f"Ошибка распознавания: {e}")
            return None

    async def _convert_ogg_to_wav(self, ogg_bytes: bytearray) -> Optional[bytes]:
        """Конвертирует OGG в WAV через pydub."""
        try:
            from pydub import AudioSegment
        except ImportError:
            logger.error("pydub не установлен! Установи: pip install pydub")
            return None

        try:
            audio_io = io.BytesIO(ogg_bytes)
            audio = AudioSegment.from_file(audio_io, format="ogg")
            
            wav_io = io.BytesIO()
            audio.export(wav_io, format="wav")
            wav_io.seek(0)
            
            return wav_io.getvalue()
        except Exception as e:
            logger.error(f"Ошибка конвертации OGG → WAV: {e}")
            return None

    async def _recognize_with_google(self, wav_bytes: bytes) -> Optional[str]:
        """Распознавание через Google Web Speech API."""
        try:
            wav_io = io.BytesIO(wav_bytes)
            
            with sr.AudioFile(wav_io) as source:
                audio_data = self.recognizer.record(source)

            try:
                text = self.recognizer.recognize_google(
                    audio_data,
                    language="ru-RU"
                )
                return text.strip()
            except sr.UnknownValueError:
                logger.warning("Google Speech не смог распознать")
                return None
            except sr.RequestError as e:
                logger.error(f"Google Speech API недоступен: {e}")
                return None

        except Exception as e:
            logger.error(f"Google Speech ошибка: {e}")
            return None