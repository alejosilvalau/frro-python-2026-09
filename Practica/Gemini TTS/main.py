import os
import tempfile
import pygame
import google.generativeai as genai
from gtts import gTTS
from dotenv import load_dotenv

load_dotenv()

LANG = "es"
MODEL = "gemini-flash-latest"
EXIT_COMMANDS = {"salir", "exit", "quit"}


def setup_gemini():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "Variable de entorno GEMINI_API_KEY no encontrada.\n"
            "Obtené tu key gratis en https://aistudio.google.com/app/apikey\n"
            "Luego ejecutá: export GEMINI_API_KEY=tu_key"
        )
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(MODEL)


def consultar_gemini(model, consulta):
    response = model.generate_content(consulta)
    return response.text


def reproducir_texto(texto):
    tts = gTTS(text=texto, lang=LANG)
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


def main():
    print("=== Gemini TTS ===")
    print(f"Modelo: {MODEL} | Idioma: {LANG}")
    print("Escribí 'salir' para terminar.\n")

    try:
        model = setup_gemini()
    except EnvironmentError as e:
        print(f"Error: {e}")
        return

    pygame.mixer.init()

    try:
        while True:
            try:
                consulta = input("Vos: ").strip()
            except EOFError:
                break

            if not consulta:
                continue

            if consulta.lower() in EXIT_COMMANDS:
                print("¡Hasta luego!")
                break

            print("Gemini: ", end="", flush=True)
            try:
                respuesta = consultar_gemini(model, consulta)
            except Exception as e:
                print(f"\nError al consultar Gemini: {e}")
                continue

            print(respuesta)

            try:
                reproducir_texto(respuesta)
            except Exception as e:
                print(f"Error al reproducir audio: {e}")

    except KeyboardInterrupt:
        print("\n¡Hasta luego!")
    finally:
        pygame.mixer.quit()


if __name__ == "__main__":
    main()
