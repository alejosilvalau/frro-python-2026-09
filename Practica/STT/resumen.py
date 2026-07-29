import re
from collections import Counter

def resumir(texto, cantidad_oraciones=3):
    oraciones = re.split(r'(?<=[.!?])\s+', texto.strip())
    if len(oraciones) <= cantidad_oraciones:
        return texto

    palabras = re.findall(r'\w+', texto.lower())
    frecuencias = Counter(palabras)

    puntajes = []
    for oracion in oraciones:
        palabras_oracion = re.findall(r'\w+', oracion.lower())
        puntaje = sum(frecuencias[p] for p in palabras_oracion)
        puntajes.append((puntaje, oracion))

    mejores = sorted(puntajes, key=lambda x: x[0], reverse=True)[:cantidad_oraciones]
    orden_original = [o for _, o in sorted(mejores, key=lambda x: oraciones.index(x[1]))]
    return " ".join(orden_original)
