import time
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from transcriptor import transcribir
from resumen import resumir

CARPETA_AUDIOS = "audios"
CARPETA_SALIDAS = "audios/salidas"
EXTENSIONES_VALIDAS = (".ogg", ".opus", ".mp3", ".m4a", ".wav")

class ManejadorAudios(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        if not event.src_path.lower().endswith(EXTENSIONES_VALIDAS):
            return

        time.sleep(1)  # esperar a que termine de copiarse el archivo

        nombre = os.path.splitext(os.path.basename(event.src_path))[0]
        print(f"Procesando {nombre}...")

        texto = transcribir(event.src_path)
        resumen = resumir(texto)

        salida = os.path.join(CARPETA_SALIDAS, f"{nombre}.txt")
        with open(salida, "w", encoding="utf-8") as f:
            f.write("=== TRANSCRIPCIÓN ===\n")
            f.write(texto + "\n\n")
            f.write("=== RESUMEN ===\n")
            f.write(resumen + "\n")

        print(f"Listo: {salida}")

if __name__ == "__main__":
    os.makedirs(CARPETA_SALIDAS, exist_ok=True)
    observer = Observer()
    observer.schedule(ManejadorAudios(), CARPETA_AUDIOS, recursive=False)
    observer.start()
    print(f"Vigilando {CARPETA_AUDIOS}/... (Ctrl+C para salir)")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
