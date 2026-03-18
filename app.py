import os
import psycopg2
import urllib.parse
from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime
from dotenv import load_dotenv
from functools import wraps
from decimal import Decimal

load_dotenv(override=True)
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "fire_ultra_secret_2026")


def get_db_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"), sslmode="require")


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session: return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated_function


# --- ROTA DE LOGIN (RAIZ) ---
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u, p = request.form.get("username"), request.form.get("password")
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, username FROM users WHERE username=%s AND password=%s", (u, p))
        user = cur.fetchone()
        conn.close()
        if user:
            session["user_id"], session["username"] = user[0], user[1]
            return redirect(url_for("dashboard"))
        else:
            flash("Usuário ou senha incorretos!")
    return render_template("login.html")


# --- ROTA DE REGISTRO ---
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        u = request.form.get("username")
        p = request.form.get("password")

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT id FROM users WHERE username = %s", (u,))
        if cur.fetchone():
            conn.close()
            flash("Este usuário já existe!")
            return redirect(url_for("register"))

        # Cria o usuário com custo inicial limpo (0.00)
        cur.execute(
            "INSERT INTO users (username, password, pix_key, custo_unitario, estoque_inicial) VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (u, p, "CADASTRAR PIX", 0.00, 750)
        )
        new_user_id = cur.fetchone()[0]

        # Insere uma regra neutra para evitar erro no orçamento inicial
        cur.execute(
            "INSERT INTO pricing_rules (user_id, min_qtd, max_qtd, valor_unitario) VALUES (%s, %s, %s, %s)",
            (new_user_id, 1, 9999, 0.00)
        )

        conn.commit()
        conn.close()
        flash("Conta criada com sucesso!")
        return redirect(url_for("login"))

    return render_template("register.html")


# --- ROTA DE LOGOUT ---
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# --- DASHBOARD (SISTEMA FIRE PLAY COMPLETO) ---
@app.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    conn = get_db_connection()
    cur = conn.cursor()
    user_id = session["user_id"]
    orcamento_view = None

    # Busca informações do usuário
    cur.execute("SELECT pix_key, custo_unitario, estoque_inicial FROM users WHERE id=%s", (user_id,))
    u_info = cur.fetchone() or ("CADASTRAR PIX", 0.00, 750)

    # Simplificação visual: garantimos que o custo_unit use apenas 2 casas decimais
    pix_atual = u_info[0]
    custo_unit = Decimal(str(u_info[1])).quantize(Decimal("0.00"))
    estoque_max = u_info[2]

    if request.method == "POST":
        tipo = request.form.get("tipo_form")

        # FUNÇÃO: Adicionar Regra
        if tipo == "add_rule":
            cur.execute("INSERT INTO pricing_rules (user_id, min_qtd, max_qtd, valor_unitario) VALUES (%s,%s,%s,%s)",
                        (user_id, request.form.get("min"), request.form.get("max"), request.form.get("val")))
            conn.commit()

        # FUNÇÃO: Deletar Regra
        elif tipo == "del_rule":
            cur.execute("DELETE FROM pricing_rules WHERE id=%s AND user_id=%s", (request.form.get("rule_id"), user_id))
            conn.commit()

        # FUNÇÃO: Salvar Ajustes Gerais (Simplificado para 2 casas)
        elif tipo == "save_config":
            novo_custo = Decimal(str(request.form.get("p_custo"))).quantize(Decimal("0.00"))
            cur.execute("UPDATE users SET pix_key=%s, custo_unitario=%s, estoque_inicial=%s WHERE id=%s",
                        (request.form.get("p_pix"), novo_custo, request.form.get("p_estoque"), user_id))
            conn.commit()
            custo_unit, pix_atual, estoque_max = novo_custo, request.form.get("p_pix"), int(
                request.form.get("p_estoque"))

        # FUNÇÃO: Gerar Orçamento
        elif tipo == "gerar_orcamento":
            qtd = int(request.form.get("qtd", 0))
            nome = request.form.get("cliente_nome").upper()
            cur.execute("SELECT valor_unitario FROM pricing_rules WHERE user_id=%s AND %s BETWEEN min_qtd AND max_qtd",
                        (user_id, qtd))
            regra = cur.fetchone()
            v_unit = Decimal(str(regra[0])).quantize(Decimal("0.00")) if regra else Decimal("0.00")

            if v_unit > 0:
                total, lucro = qtd * v_unit, (qtd * v_unit) - (custo_unit * qtd)
                msg = (
                    f"🚀 *FIRE PLAY - FATURA DIGITAL*\n━━━━━━━━━━━━━━━━━━━━\n👤 *CLIENTE:* {nome}\n📦 *PEDIDO:* {qtd} CRÉDITOS\n💰 *VALOR UNIT:* R$ {v_unit:.2f}\n💳 *TOTAL:* R$ {total:.2f}\n━━━━━━━━━━━━━━━━━━━━\n🔑 *PIX:* `{pix_atual}`")
                orcamento_view = {"msg": urllib.parse.quote(msg), "nome": nome, "qtd": qtd, "total": total,
                                  "lucro": lucro}

        # FUNÇÃO: Confirmar Venda
        elif tipo == "confirmar_venda":
            cur.execute("INSERT INTO sales (user_id, cliente, quantidade, valor_total, lucro) VALUES (%s,%s,%s,%s,%s)",
                        (user_id, f"REV: {request.form.get('c_nome')}", request.form.get('c_qtd'),
                         request.form.get('c_total'), request.form.get('c_lucro')))
            conn.commit()

    # Carregamento de dados para o painel
    cur.execute("SELECT id, min_qtd, max_qtd, valor_unitario FROM pricing_rules WHERE user_id=%s ORDER BY min_qtd ASC",
                (user_id,))
    regras = cur.fetchall()

    cur.execute("SELECT data, cliente, quantidade, valor_total, lucro FROM sales WHERE user_id=%s ORDER BY id DESC",
                (user_id,))
    historico = cur.fetchall()

    cur.execute("SELECT COALESCE(SUM(quantidade), 0), COALESCE(SUM(lucro), 0) FROM sales WHERE user_id=%s", (user_id,))
    vendidos, lucro_total = cur.fetchone()

    estoque_atual = estoque_max - vendidos
    pct = (estoque_atual / estoque_max * 100) if estoque_max > 0 else 0
    conn.close()

    return render_template("dashboard.html", historico=historico, lucro_total=lucro_total,
                           pix_atual=pix_atual, custo_real=custo_unit, regras=regras,
                           orcamento=orcamento_view, estoque_atual=estoque_atual,
                           estoque_max=estoque_max, pct=pct)


if __name__ == "__main__":
    app.run(debug=True)