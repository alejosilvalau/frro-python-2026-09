# Resumidor de audios de WhatsApp con Whisper

Transcribe y resume automáticamente audios de WhatsApp usando Whisper de OpenAI. Detecta archivos nuevos en la carpeta `audios/` y genera un `.txt` con la transcripción y el resumen.

## Requisitos

- Python 3.10+
- ffmpeg instalado en el sistema

```bash
brew install ffmpeg
```

## Instalación

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Uso

1. Activá el entorno virtual e iniciá el watcher:

```bash
source venv/bin/activate
python watcher.py
```

1. Copiá un audio a la carpeta `audios/` (ver instrucciones en `audios/README.md`).

1. El script lo detecta solo y en unos segundos genera el resultado en `audios/salidas/<nombre>.txt`.

1. Para detenerlo: `Ctrl+C`.

## Estructura

```text
STT/
├── watcher.py        <- vigila audios/ y procesa automáticamente
├── transcriptor.py   <- transcribe con Whisper (modelo small, español rioplatense)
├── resumen.py        <- resumen extractivo por frecuencia de palabras
└── audios/
    ├── README.md     <- instrucciones para bajar audios de WhatsApp
    └── salidas/      <- transcripciones y resúmenes generados
```

## Formatos de audio soportados

`.ogg` `.opus` `.mp3` `.m4a` `.wav`

## Notas

- El modelo `small` tarda más que `base` pero reconoce mejor el acento argentino.
- Para audios muy largos (20+ min) se puede usar `medium`, aunque requiere más RAM.
- El resumen es extractivo: elige las oraciones más representativas del texto original, no genera texto nuevo.
