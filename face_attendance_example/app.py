from flask import Flask, render_template
from config import SECRET_KEY, MAX_CONTENT_LENGTH
from database.database import init_db
from routes.students import students_bp
from routes.sessions import sessions_bp
from routes.attendance import attendance_bp

def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = SECRET_KEY
    app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

    init_db()

    app.register_blueprint(students_bp)
    app.register_blueprint(sessions_bp)
    app.register_blueprint(attendance_bp)

    @app.get("/")
    def dashboard():
        return render_template("dashboard.html")

    @app.errorhandler(413)
    def too_large(_):
        return {"error": "Ảnh tải lên quá lớn."}, 413

    return app

app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
