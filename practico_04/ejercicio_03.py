"""Base de Datos SQL - Baja"""

import datetime

from ejercicio_01 import reset_tabla
from ejercicio_02 import agregar_persona

import sqlite3
from contextlib import closing


def borrar_persona(id_persona):
    """Implementar la funcion borrar_persona, que elimina un registro en la
    tabla Persona. Devuelve un booleano en base a si encontro el registro y lo
    borro o no."""
    conexion = sqlite3.connect('practico.db')

    with closing(conexion), conexion:
        cursor = conexion.execute(
            "DELETE FROM Persona WHERE IdPersona = ?",
            (id_persona,)
        )
        return cursor.rowcount > 0


# NO MODIFICAR - INICIO
@reset_tabla
def pruebas():
    assert borrar_persona(agregar_persona('juan perez', datetime.datetime(1988, 5, 15), 32165498, 180))
    assert borrar_persona(12345) is False

if __name__ == '__main__':
    pruebas()
# NO MODIFICAR - FIN
