import os
from flask import Flask, render_template, session, redirect, url_for
import psycopg2
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
# MESMA CHAVE DO APP.PY
app.secret_key = "fireplay_secret_shared_key"

app.config.update(
    SESSION_COOKIE_NAME='fireplay_session', # MESMO NOME
    SESSION_COOKIE_DOMAIN=None,
    SESSION_COOKIE_PATH='/',
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=False
)

DB_URI = os.getenv("DATABASE_URL")

def get_db_connection():
    return psycopg2.connect(DB_URI, sslmode="require")

# MANTIDAS SUAS REGRAS DE NEGÓCIO
VALOR_PLANO_MENSAL = 350
DIVIDIDO_ENTRE = 4
TABELA_PRECOS_REVENDA = [(10, 29, 5.0), (30, 69, 4.5), (70, 149, 4.0), (150, 299, 3.7), (300, 9999, 3.5)]

@app.route("/")
def painel():
    # Se der erro aqui, é porque a sessão não foi compartilhada
    user_id = session.get("user_id")
    if not user_id:
        return redirect("http://127.0.0.1:5000/login")

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Buscas no banco (settings, sales, etc)
        cursor.execute("SELECT value FROM settings WHERE key='total_credits'")
        res = cursor.fetchone()
        limite_total = int(res[0]) if res else 0

        cursor.execute("SELECT SUM(quantidade) FROM sales WHERE user_id=%s", (user_id,))
        usado = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT SUM(lucro) FROM sales WHERE user_id=%s", (user_id,))
        lucro_m = cursor.fetchone()[0] or 0

        cursor.execute("SELECT data, cliente, quantidade, lucro FROM sales WHERE user_id=%s ORDER BY id DESC LIMIT 10", (user_id,))
        historico = cursor.fetchall()

        disponivel = limite_total - usado

        return render_template("dashboard.html", 
                               lucro_m=lucro_m, 
                               disponivel=disponivel, 
                               usado=usado, 
                               historico=historico)
    except Exception as e:
        return f"Erro no banco: {str(e)}"
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    app.run(port=5001, debug=True)