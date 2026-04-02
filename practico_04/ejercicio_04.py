"""Base de Datos SQL - Búsqueda"""

import datetime

from practico_04.ejercicio_01 import reset_tabla
from practico_04.ejercicio_02 import agregar_persona

import sqlite3
from contextlib import closing

def buscar_persona(id_persona):
    """Implementar la funcion buscar_persona, que devuelve el registro de una 
    persona basado en su id. El return es una tupla que contiene sus campos: 
    id, nombre, nacimiento, dni y altura. Si no encuentra ningun registro, 
    devuelve False."""
    conexion = sqlite3.connect('practico.db')
    
    with closing(conexion), conexion:
        cursor = conexion.execute(
            "SELECT * FROM Persona WHERE IdPersona = ?",
            (id_persona,)
        )
        resultado = cursor.fetchone()
        if resultado:  
            fecha_texto = resultado['FechaNacimiento']
            fecha_obj = datetime.datetime.strptime(fecha_texto, "%Y-%m-%d %H:%M:%S")
            return (
                resultado['IdPersona'], 
                resultado['Nombre'], 
                fecha_obj,
                resultado['DNI'], 
                resultado['Altura']
            )
        else:
            return False


# NO MODIFICAR - INICIO
@reset_tabla
def pruebas():
    juan = buscar_persona(agregar_persona('juan perez', datetime.datetime(1988, 5, 15), 32165498, 180))
    assert juan == (1, 'juan perez', datetime.datetime(1988, 5, 15), 32165498, 180)
    assert buscar_persona(12345) is False

if __name__ == '__main__':
    pruebas()
# NO MODIFICAR - FIN
