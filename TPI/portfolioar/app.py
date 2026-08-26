#!/usr/bin/env python
import os
import sys


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'portfolioar.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "No se pudo importar Django. Verificá que esté instalado y "
            "que el entorno virtual esté activado."
        ) from exc
    args = sys.argv if len(sys.argv) > 1 else [sys.argv[0], 'runserver']
    execute_from_command_line(args)


if __name__ == '__main__':
    main()
