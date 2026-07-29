import json
import os
import base64
from gtts import gTTS

CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "phrase_cache.json")

PHRASES_ES = [
    "¡Más arriba!",
    "¡Más abajo!",
    "¡Izquierda!",
    "¡Derecha!",
    "¡Casi lo logras!",
    "¡No te rindas!",
    "¡Un poco más!",
    "¡Tú puedes!",
    "¡Sigue así!",
    "¡Muy bien!",
    "¡Excelente!",
    "¡Justo ahí!",
    "¡Cerca de la llave!",
    "¡Perfecto!",
    "¡Lo lograste!",
]

SUPPORTED_LANGUAGES = {
    "es": "Spanish",
    "en": "English",
    "pt": "Portuguese",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
    "ru": "Russian",
    "ar": "Arabic",
}


def _load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def _generate_audio(text, lang):
    tts = gTTS(text=text, lang=lang)
    tmp_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_tmp_phrase.mp3")
    tts.save(tmp_path)
    with open(tmp_path, "rb") as f:
        audio_b64 = base64.b64encode(f.read()).decode("utf-8")
    os.remove(tmp_path)
    return audio_b64


def get_phrases(language):
    cache = _load_cache()
    if language not in cache:
        cache[language] = {}

    phrases_b64 = {}
    for phrase in PHRASES_ES:
        if phrase in cache[language]:
            phrases_b64[phrase] = cache[language][phrase]
        else:
            audio_b64 = _generate_audio(phrase, language)
            cache[language][phrase] = audio_b64
            phrases_b64[phrase] = audio_b64

    _save_cache(cache)
    return phrases_b64


def get_random_phrase(phrases_dict):
    import random
    return random.choice(list(phrases_dict.keys()))


def decode_audio(audio_b64):
    return base64.b64decode(audio_b64)
