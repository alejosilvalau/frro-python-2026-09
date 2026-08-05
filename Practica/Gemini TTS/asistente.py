import os
import sys
import signal
import tempfile
import numpy as np
import pygame
import speech_recognition as sr
import google.generativeai as genai
from gtts import gTTS
from dotenv import load_dotenv
from resemblyzer import VoiceEncoder, preprocess_wav

load_dotenv()

WAKE_WORDS = ["guatemala"]
LANG_STT = "es-AR"
LANG_TTS = "es"
MODEL = "gemini-flash-latest"
PROFILE_PATH = "voice_profile.npy"
SIMILARITY_THRESHOLD = 0.75
N_MUESTRAS = 3
DURACION_MUESTRA = 5
SYSTEM_PROMPT = (
    "Sos un asistente de voz. Respondé de forma concisa y clara, "
    "en no más de 3 oraciones. Sin listas ni markdown."
)


def setup_gemini():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "Variable de entorno GEMINI_API_KEY no encontrada.\n"
            "Revisá tu archivo .env"
        )
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(MODEL, system_instruction=SYSTEM_PROMPT)


def reproducir(texto):
    tts = gTTS(text=texto, lang=LANG_TTS)
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        tts.save(tmp_path)
        pygame.mixer.music.load(tmp_path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
    finally:
        pygame.mixer.music.unload()
        os.remove(tmp_path)


def audio_a_numpy(audio_data):
    wav_bytes = audio_data.get_wav_data(convert_rate=16000, convert_width=2)
    return np.frombuffer(wav_bytes, dtype=np.int16).astype(np.float32) / 32768.0


def verificar_voz(audio_data, encoder, perfil):
    try:
        wav = preprocess_wav(audio_a_numpy(audio_data), source_sr=16000)
        embedding = encoder.embed_utterance(wav)
        similitud = np.dot(embedding, perfil) / (
            np.linalg.norm(embedding) * np.linalg.norm(perfil)
        )
        print(f"Similitud de voz: {similitud:.2f} (umbral: {SIMILARITY_THRESHOLD})")
        return similitud >= SIMILARITY_THRESHOLD
    except Exception as e:
        print(f"Error en verificación: {e}")
        return True


def escuchar(recognizer, source, timeout=10, phrase_limit=8):
    try:
        audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_limit)
        texto = recognizer.recognize_google(audio, language=LANG_STT)
        return texto, audio
    except sr.WaitTimeoutError:
        return None, None
    except sr.UnknownValueError:
        return None, None
    except sr.RequestError as e:
        print(f"Error de reconocimiento: {e}")
        return None, None


def contiene_wake_word(texto):
    return any(w in texto.lower() for w in WAKE_WORDS)


def onboarding(r, source, encoder):
    reproducir("Hola, ¿quién eres?")

    texto, _ = escuchar(r, source, timeout=10, phrase_limit=5)
    nombre = texto.split()[0].capitalize() if texto else "usuario"

    reproducir(
        f"Hola {nombre}! Voy a registrar tu voz en {N_MUESTRAS} muestras. "
        f"Hablá naturalmente durante {DURACION_MUESTRA} segundos cada vez que te lo indique."
    )

    embeddings = []
    for i in range(N_MUESTRAS):
        reproducir(f"Muestra {i + 1} de {N_MUESTRAS}. Empezá a hablar.")
        print(f"Grabando muestra {i + 1}/{N_MUESTRAS}...")
        audio = r.record(source, duration=DURACION_MUESTRA)
        wav = preprocess_wav(audio_a_numpy(audio), source_sr=16000)
        embeddings.append(encoder.embed_utterance(wav))
        if i < N_MUESTRAS - 1:
            reproducir("Bien, siguiente.")

    perfil = np.mean(embeddings, axis=0)
    np.save(PROFILE_PATH, perfil)

    reproducir(
        f"Listo {nombre}! Ya te reconozco. "
        f"Decí 'guatemala' cuando quieras activarme."
    )
    print(f"Perfil guardado como '{PROFILE_PATH}'.\n")
    return perfil


def main():
    signal.signal(signal.SIGINT, lambda *_: (pygame.mixer.quit(), sys.exit(0)))

    print("=== Gemini Voice Assistant ===")
    print("Presioná Ctrl+C para salir.\n")

    try:
        model = setup_gemini()
    except EnvironmentError as e:
        print(f"Error: {e}")
        return

    print("Cargando modelo de voz...")
    encoder = VoiceEncoder()

    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
    r = sr.Recognizer()
    r.dynamic_energy_threshold = True

    try:
        with sr.Microphone() as source:
            print("Calibrando ruido ambiente...")
            r.adjust_for_ambient_noise(source, duration=2)

            if not os.path.exists(PROFILE_PATH):
                perfil = onboarding(r, source, encoder)
            else:
                perfil = np.load(PROFILE_PATH)
                reproducir("Bienvenido de vuelta. Decí 'guatemala' para activarme.")
                print("Listo. Decí 'guatemala' para activar.\n")

            while True:
                print("Escuchando wake word...", end="\r")
                texto, _ = escuchar(r, source, timeout=15, phrase_limit=5)

                if not texto:
                    continue

                print(f"Escuché: '{texto}'")

                if not contiene_wake_word(texto):
                    continue

                print("\nActivado!")
                reproducir("Te escucho")

                print("Esperando consulta...")
                consulta, audio_consulta = escuchar(r, source, timeout=8, phrase_limit=12)

                if not consulta:
                    print("No escuché la consulta.")
                    reproducir("No escuché tu consulta. Intentá de nuevo.")
                    continue

                if not verificar_voz(audio_consulta, encoder, perfil):
                    print("Voz no reconocida.")
                    reproducir("No reconocí tu voz. Solo respondo al usuario registrado.")
                    continue

                print(f"Vos: {consulta}")

                try:
                    respuesta = model.generate_content(consulta).text
                    print(f"Gemini: {respuesta}\n")
                    reproducir(respuesta)
                except Exception as e:
                    print(f"Error al consultar Gemini: {e}")
                    reproducir("Hubo un error. Intentá de nuevo.")

    except KeyboardInterrupt:
        print("\n¡Hasta luego!")
    finally:
        pygame.mixer.quit()


if __name__ == "__main__":
    main()
