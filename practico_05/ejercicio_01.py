"""Base de Datos - Creación de Clase en ORM"""

from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Socio(Base):
    """Implementar un modelo Socio a traves de Alchemy que cuente con los siguientes campos:
    - id_socio: entero (clave primaria, auto-incremental, unico)
    - dni: entero (unico)
    - nombre: string (longitud 250)
    - apellido: string (longitud 250)
    """

    __tablename__ = "socios"
    id: Mapped[int] = mapped_column(
        "id_socio", primary_key=True, autoincrement=True, unique=True
    )
    dni: Mapped[int] = mapped_column(unique=True)
    nombre: Mapped[str] = mapped_column(String(250))
    apellido: Mapped[str] = mapped_column(String(250))
