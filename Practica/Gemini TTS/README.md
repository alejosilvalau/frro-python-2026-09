# Gemini Voice Assistant

Asistente de voz con IA. Escucha una palabra clave, transcribe la consulta, la envía a Gemini y responde en voz alta. Incluye verificación de hablante: solo responde a la voz registrada.

## Requisitos

- Python 3.10+
- portaudio instalado en el sistema

```bash
brew install portaudio
```

- API Key gratuita de Gemini → [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)

## Instalación

```bash
cd "Practica/Gemini TTS"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> **Python 3.12 en macOS**: `resemblyzer` depende de `webrtcvad` que falla en Python 3.12. Después de instalar las dependencias, ejecutá:
>
> ```bash
> pip uninstall webrtcvad -y && pip install webrtcvad-wheels
> ```

## Configuración

Copiá `.env.example` a `.env` y agregá tu API key:

```bash
cp .env.example .env
```

```env
GEMINI_API_KEY=tu_api_key_aqui
```

## Uso

### Modo texto (main.py)

Escribís la consulta, Gemini responde en voz y en texto.

```bash
source .venv/bin/activate
python main.py
```

- Escribí tu consulta y presioná Enter
- Para salir: escribí `salir`

### Modo voz — Asistente (asistente.py)

```bash
source .venv/bin/activate
python asistente.py
```

#### Primera vez (registro de voz)

1. La app pregunta **"Hola, ¿quién eres?"** → decí tu nombre
2. Graba **3 muestras** de tu voz (5 segundos cada una), hablando naturalmente
3. Guarda tu perfil en `voice_profile.npy`
4. Queda lista para usarse

#### Uso normal

1. La app calibra el ruido ambiente (2 segundos)
2. Decí **"guatemala"** para activar el asistente
3. Esperá el audio de confirmación ("Te escucho")
4. Decí tu consulta
5. Gemini responde en voz alta — solo si reconoce tu voz
6. Vuelve a escuchar la palabra clave

Para salir: `Ctrl+C`

#### Re-registrar la voz

```bash
rm voice_profile.npy
python asistente.py
```

## Estructura

```text
Gemini TTS/
├── main.py          <- modo texto: input por teclado, respuesta en voz
├── asistente.py     <- modo voz: wake word + STT + verificación + Gemini + TTS
├── requirements.txt
├── .env             <- API key (no subir al repo)
└── .env.example     <- plantilla de configuración
```

## Stack

| Componente | Tecnología | Notas |
| --- | --- | --- |
| Wake word | `SpeechRecognition` | Detecta "guatemala" en la transcripción |
| STT | Google Web Speech API | Gratis, sin key requerida |
| Verificación de voz | `resemblyzer` | Embeddings de voz, umbral de similitud 0.75 |
| LLM | Gemini (`gemini-flash-latest`) | Requiere API key gratuita |
| TTS | Google Translate TTS (`gTTS`) | Gratis, sin key requerida |
| Audio | `pygame` | Playback del MP3 generado |

## Notas

- El modelo Gemini responde en máximo 3 oraciones para que sea cómodo de escuchar.
- La verificación de voz se aplica a la consulta (no al wake word). Si la similitud es menor a 0.75, el asistente ignora la consulta.
- El `.env` y `voice_profile.npy` no se suben al repositorio.
- En Windows: reemplazá `source .venv/bin/activate` por `.venv\Scripts\activate`.
