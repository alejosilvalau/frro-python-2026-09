from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import Mapped, relationship

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///university.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


class Student(db.Model):
    id: Mapped[int] = db.Column(db.Integer, primary_key=True)
    name: Mapped[str] = db.Column(db.String(100), nullable=False)
    email: Mapped[str] = db.Column(db.String(120), unique=True, nullable=False)
    grades: Mapped[list["Grade"]] = relationship(back_populates="student", lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {"id": self.id, "name": self.name, "email": self.email}


class Subject(db.Model):
    id: Mapped[int] = db.Column(db.Integer, primary_key=True)
    name: Mapped[str] = db.Column(db.String(100), nullable=False)
    code: Mapped[str] = db.Column(db.String(20), unique=True, nullable=False)
    grades: Mapped[list["Grade"]] = relationship(back_populates="subject", lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {"id": self.id, "name": self.name, "code": self.code}


class Grade(db.Model):
    id: Mapped[int] = db.Column(db.Integer, primary_key=True)
    value: Mapped[float] = db.Column(db.Float, nullable=False)
    student_id: Mapped[int] = db.Column(db.Integer, db.ForeignKey("student.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)
    subject_id: Mapped[int] = db.Column(db.Integer, db.ForeignKey("subject.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)
    
    student: Mapped["Student"] = relationship(back_populates="grades")
    subject: Mapped["Subject"] = relationship(back_populates="grades")

    def to_dict(self):
        return {
            "id": self.id,
            "value": self.value,
            "student_id": self.student_id,
            "subject_id": self.subject_id,
            "student_name": self.student.name,
            "subject_name": self.subject.name,
        }


with app.app_context():
    db.create_all()


@app.route("/")
def hub():
    return render_template("hub.html")


# ── Students ──────────────────────────────────────────────
@app.route("/students")
def students_page():
    return render_template("students.html")


@app.route("/api/students", methods=["GET"])
def get_students():
    students = Student.query.all()
    return jsonify([s.to_dict() for s in students])


@app.route("/api/students/<int:id>", methods=["GET"])
def get_student(id):
    s = Student.query.get_or_404(id)
    return jsonify(s.to_dict())


@app.route("/api/students", methods=["POST"])
def create_student():
    data = request.get_json()
    s = Student(name=data["name"], email=data["email"])
    db.session.add(s)
    db.session.commit()
    return jsonify(s.to_dict()), 201


@app.route("/api/students/<int:id>", methods=["PUT"])
def update_student(id):
    s = Student.query.get_or_404(id)
    data = request.get_json()
    s.name = data.get("name", s.name)
    s.email = data.get("email", s.email)
    db.session.commit()
    return jsonify(s.to_dict())


@app.route("/api/students/<int:id>", methods=["DELETE"])
def delete_student(id):
    s = Student.query.get_or_404(id)
    db.session.delete(s)
    db.session.commit()
    return "", 204


# ── Subjects ──────────────────────────────────────────────
@app.route("/subjects")
def subjects_page():
    return render_template("subjects.html")


@app.route("/api/subjects", methods=["GET"])
def get_subjects():
    subjects = Subject.query.all()
    return jsonify([s.to_dict() for s in subjects])


@app.route("/api/subjects/<int:id>", methods=["GET"])
def get_subject(id):
    s = Subject.query.get_or_404(id)
    return jsonify(s.to_dict())


@app.route("/api/subjects", methods=["POST"])
def create_subject():
    data = request.get_json()
    s = Subject(name=data["name"], code=data["code"])
    db.session.add(s)
    db.session.commit()
    return jsonify(s.to_dict()), 201


@app.route("/api/subjects/<int:id>", methods=["PUT"])
def update_subject(id):
    s = Subject.query.get_or_404(id)
    data = request.get_json()
    s.name = data.get("name", s.name)
    s.code = data.get("code", s.code)
    db.session.commit()
    return jsonify(s.to_dict())


@app.route("/api/subjects/<int:id>", methods=["DELETE"])
def delete_subject(id):
    s = Subject.query.get_or_404(id)
    db.session.delete(s)
    db.session.commit()
    return "", 204


# ── Grades ────────────────────────────────────────────────
@app.route("/grades")
def grades_page():
    return render_template("grades.html")


@app.route("/api/grades", methods=["GET"])
def get_grades():
    grades = Grade.query.all()
    return jsonify([g.to_dict() for g in grades])


@app.route("/api/grades/<int:id>", methods=["GET"])
def get_grade(id):
    g = Grade.query.get_or_404(id)
    return jsonify(g.to_dict())


@app.route("/api/grades", methods=["POST"])
def create_grade():
    data = request.get_json()
    g = Grade(value=data["value"], student_id=data["student_id"], subject_id=data["subject_id"])
    db.session.add(g)
    db.session.commit()
    return jsonify(g.to_dict()), 201


@app.route("/api/grades/<int:id>", methods=["PUT"])
def update_grade(id):
    g = Grade.query.get_or_404(id)
    data = request.get_json()
    g.value = data.get("value", g.value)
    g.student_id = data.get("student_id", g.student_id)
    g.subject_id = data.get("subject_id", g.subject_id)
    db.session.commit()
    return jsonify(g.to_dict())


@app.route("/api/grades/<int:id>", methods=["DELETE"])
def delete_grade(id):
    g = Grade.query.get_or_404(id)
    db.session.delete(g)
    db.session.commit()
    return "", 204


if __name__ == "__main__":
    app.run(debug=True, port=5000)
