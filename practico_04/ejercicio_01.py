"""Base de Datos SQL - Crear y Borrar Tablas"""

import sqlite3
from contextlib import closing, suppress
def crear_tabla():
    """Implementar la funcion crear_tabla, que cree una tabla Persona con:
        - IdPersona: Int() (autoincremental)
        - Nombre: Char(30)
        - FechaNacimiento: Date()
        - DNI: Int()
        - Altura: Int()
    """
    conexion = sqlite3.connect('practico.db')
    with suppress(sqlite3.OperationalError), closing(conexion), conexion:
        conexion.execute("""
            CREATE TABLE IF NOT EXISTS Persona (
                IdPersona INTEGER PRIMARY KEY AUTOINCREMENT,
                Nombre VARCHAR(30),
                FechaNacimiento DATE,
                DNI INTEGER,
                Altura INTEGER
            )
        """)


def borrar_tabla():
    """Implementar la funcion borrar_tabla, que borra la tabla creada 
    anteriormente."""
    conexion = sqlite3.connect('practico.db')
    with suppress(sqlite3.OperationalError), closing(conexion), conexion:
        conexion.execute("DROP TABLE IF EXISTS Persona")


# NO MODIFICAR - INICIO
def reset_tabla(func):
    def func_wrapper():
        crear_tabla()
        func()
        borrar_tabla()
    return func_wrapper
# NO MODIFICAR - FIN
