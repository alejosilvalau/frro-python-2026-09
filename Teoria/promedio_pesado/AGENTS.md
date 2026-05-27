# agents.md — Reglas para generación de código

## Objetivo
La idea es producir codigo claro y simple sin OOP, y buscando un codigo minimalista y simple de leer con la menor cantidad de lineas posibles de codigo para resolver los problemas.

## Que conocimientos tenemos hasta ahora
Para esta altura del curso ya vimos librerias basicas, random, math, strings, operaciones basicas numericas y slicing, listas, tuplas y diccionarios. Tambien vimos instalacion de entornos virtuales y uso de pip para agregar paquetes, vimos paquetes mas utilizados en nuestros casos de uso tipicos como son:

### MANIPULACIÓN DE DATOS
- numpy: Cómputo numérico, matrices, algebra lineal
- pandas: Manipulación y análisis de datos (DataFrames)

### VISUALIZACIÓN
- matplotlib: Dataviz, gráficos (todo tipo de charts)

### WEB Y APIs
- requests: Peticiones web y a APIs
- bs4: Extraer datos de paginas web (web scraping)
- yfinance: Descargar datos históricos de Yahoo Finance
- pyrofex: Descargar datos de mercado de agropecuarios

### LECTURA DE ARCHIVOS
- python-dotenv: Carga variables de entorno desde .env
- openpyxl: Lectura y escritura de archivos Excel .xlsx
- pymupdf: Lectura rápida de archivos PDF

### CIENCIA DE DATOS Y MACHINE LEARNING
- scipy: Optimización, estadística, interpolación
- scikit-learn: Machine learning (regresión, clasificación, clustering)


Desde el punto de vista teorico estamos aprendiendo conceptos de pseudoaleatoriedad y semillas para calculo y montecarlo aplicado a temas financieros.



## Principios generales
- El código debe ser lo más simple posible
- Resolver el problema con la menor cantidad de conceptos y lineas de codigo
- Evitar cualquier complejidad innecesaria
- Priorizar legibilidad por sobre eficiencia o performance


## Restricciones estrictas

### Prohibido usar:
- Programación orientada a objetos (class)
- Funciones anónimas (lambda)
- Decoradores
- Manejo avanzado de errores (try/except salvo que sea imprescindible)
- Imports innecesarios
- No instalar nunca nada que no se pida explicitamente


### Evitar en lo posible:
- Funciones (usar solo si es didácticamente necesario o si se pide en el ejercicio)
- Anidamientos profundos
- Expresiones compactas difíciles de leer


## Estilo de código
- Es preferible siempre menos lineas de codigo a mas
- Con comentarios en el código
- Nombres de variables descriptivos pero simples
- Espaciado claro pero no exagerar en codigo multilinea innecesario
- Al final del script crea un comentario multilinea con la justificacion de por que resolviste asi lo pedido
- Finalmente, Terminar siempre los scripts con un comentario final: # Agents.md rules applied successfully

## Tipos de soluciones esperadas

- Uso de `print` para mostrar resultados
- Uso de `input` cuando haya interacción
- Uso de estructuras básicas:
  - if / else
  - for
- Uso de tipos básicos:
  - int
  - float
  - str
  - bool
  - list
  - dict
- Al final del script crea un comentario multilinea con la justificacion de por que resolviste asi lo pedido
- Terminar siempre los scripts con un comentario final: # Agents.md rules applied successfully


## Casos especiales de uso mios como alumno

Soy contador y quiero aprovechar el curso para aprender a automatizar tareas repetitivas de mi estudio y clientes, tengo clientes empresariales, autonomos e inversores.

