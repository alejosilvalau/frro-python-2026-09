import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from flask import Flask, render_template, request, redirect, url_for
from practico_05.ejercicio_01 import Socio
from practico_06.capa_negocio import NegocioSocio, DniRepetido, LongitudInvalida, MaximoAlcanzado

app = Flask(__name__)
negocio = NegocioSocio()


@app.route('/')
def index():
    socios = negocio.todos()
    return render_template('socios.html', socios=socios)


@app.route('/alta', methods=['GET', 'POST'])
def alta():
    if request.method == 'POST':
        dni = request.form['dni']
        nombre = request.form['nombre']
        apellido = request.form['apellido']

        socio = Socio(dni=int(dni), nombre=nombre, apellido=apellido)
        try:
            negocio.alta(socio)
            return redirect(url_for('index'))
        except DniRepetido:
            return render_template('socio_form.html', error='DNI ya registrado')
        except LongitudInvalida:
            return render_template('socio_form.html', error='Nombre y apellido deben tener entre 3 y 15 caracteres')
        except MaximoAlcanzado:
            return render_template('socio_form.html', error='Se alcanzó el máximo de socios')

    return render_template('socio_form.html')


@app.route('/baja/<int:id>', methods=['POST'])
def baja(id):
    negocio.baja(id)
    return redirect(url_for('index'))


@app.route('/modificar/<int:id>', methods=['GET', 'POST'])
def modificar(id):
    if request.method == 'POST':
        dni = request.form['dni']
        nombre = request.form['nombre']
        apellido = request.form['apellido']

        socio = Socio(id_socio=id, dni=int(dni), nombre=nombre, apellido=apellido)
        try:
            negocio.modificacion(socio)
            return redirect(url_for('index'))
        except LongitudInvalida:
            socio = negocio.buscar(id)
            return render_template('socio_form.html', socio=socio, modificar=True, error='Nombre y apellido deben tener entre 3 y 15 caracteres')

    socio = negocio.buscar(id)
    return render_template('socio_form.html', socio=socio, modificar=True)


if __name__ == '__main__':
    app.run(debug=True)
