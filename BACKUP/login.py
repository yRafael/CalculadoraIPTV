from flask import Flask, render_template_string, request, redirect, session, flash
import psycopg2
import os
from werkzeug.security import check_password_hash
from datetime import timedelta

app = Flask(__name__)

# 🔐 Segurança
app.secret_key = os.getenv("SECRET_KEY", "dev_secret_temporaria")

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=False  # Quando subir online com HTTPS, mudar para True
)

app.permanent_session_lifetime = timedelta(hours=6)

DB_URI = os.getenv("DATABASE_URL")

def get_db_connection():
    return psycopg2.connect(DB_URI)

HTML_LOGIN = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;900&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', sans-serif; background: #050505; color: white; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
        .login-card { background: #0c0c0c; padding: 40px; border-radius: 20px; border: 1px solid #1a1a1a; width: 100%; max-width: 350px; text-align: center; }
        .logo { font-weight: 900; font-size: 30px; margin-bottom: 30px; color: white; }
        .logo span { color: #ff0000; }
        input { width: 100%; padding: 15px; margin-bottom: 15px; border-radius: 8px; border: 1px solid #1a1a1a; background: #000; color: white; box-sizing: border-box; }
        button { width: 100%; padding: 15px; border-radius: 8px; border: none; background: #ff0000; color: white; font-weight: 900; cursor: pointer; }
        .msg { color: #ff0000; font-size: 12px; margin-bottom: 15px; }
    </style>
</head>
<body>
    <div class="login-card">
        <div class="logo">FIRE<span>PLAY</span></div>
        {% with messages = get_flashed_messages() %}{% if messages %}{% for m in messages %}<div class="msg">{{ m }}</div>{% endfor %}{% endif %}{% endwith %}
        <form method="POST">
            <input name="username" placeholder="Usuário" required autofocus>
            <input name="password" type="password" placeholder="Senha" required>
            <button type="submit">ENTRAR NO SISTEMA</button>
        </form>
    </div>
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form["username"]
        p = request.form["password"]

        conn = get_db_connection()
        cursor = conn.cursor()

        # 🔐 Agora busca senha hash
        cursor.execute("SELECT id, username, password, role FROM users WHERE username=%s", (u,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user[2], p):
            session.permanent = True
            session["user_id"] = user[0]
            session["username"] = user[1]
            session["role"] = user[3]
            return redirect("http://localhost:5001/")

        flash("Usuário ou senha inválidos!")

    return render_template_string(HTML_LOGIN)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)