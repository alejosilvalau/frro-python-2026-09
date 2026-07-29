import whisper

modelo = whisper.load_model("small")

def transcribir(ruta_audio):
    resultado = modelo.transcribe(
        ruta_audio,
        language="es",
        initial_prompt="Transcripción en español rioplatense argentino. Se usa 'vos', 'che', 'boludo', 'posta', 'laburo', 'pibe'.",
    )
    return resultado["text"]
