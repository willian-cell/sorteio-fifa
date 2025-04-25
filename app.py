# app.py
from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3, random

app = Flask(__name__)
app.secret_key = 'chave-super-secreta'
DB = 'jogadores.db'

def init_db():
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS jogadores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT UNIQUE,
                time TEXT,
                ordem_escolha INTEGER
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS confrontos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fase TEXT,
                jogador_casa TEXT,
                jogador_visitante TEXT,
                vencedor TEXT
            )
        ''')
        conn.commit()

@app.route('/')
def index():
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM jogadores ORDER BY nome')
        jogadores = c.fetchall()
    return render_template('index.html', jogadores=jogadores)

@app.route('/cadastrar', methods=['POST'])
def cadastrar():
    nome = request.form['nome'].strip()
    if not nome:
        return redirect('/')
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM jogadores WHERE LOWER(nome) = LOWER(?)', (nome,))
        if c.fetchone()[0] == 0:
            c.execute('INSERT INTO jogadores (nome) VALUES (?)', (nome,))
            conn.commit()
    return redirect('/')

@app.route('/sortear_ordem')
def sortear_ordem():
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute('SELECT id FROM jogadores')
        jogadores = [j[0] for j in c.fetchall()]
        random.shuffle(jogadores)
        for ordem, jid in enumerate(jogadores, 1):
            c.execute('UPDATE jogadores SET ordem_escolha = ? WHERE id = ?', (ordem, jid))
        conn.commit()
    return redirect('/')

@app.route('/sortear_times')
def sortear_times():
    times_fifa = [
        "Real Madrid", "Barcelona", "Manchester City", "Manchester United",
        "Liverpool", "Chelsea", "Arsenal", "Bayern de Munique", "Borussia Dortmund",
        "PSG", "Juventus", "Inter de Milão", "Milan", "Napoli", "Roma",
        "Atlético de Madrid", "Ajax", "Porto", "Benfica", "Sporting",
        "Flamengo", "Palmeiras", "São Paulo", "Corinthians", "Grêmio",
        "Internacional", "River Plate", "Boca Juniors", "Al Nassr", "Al Hilal"
    ]
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute('SELECT id FROM jogadores ORDER BY ordem_escolha')
        jogadores = [j[0] for j in c.fetchall()]

        if len(jogadores) > len(times_fifa):
            return "⚠️ Não há times suficientes para todos os jogadores."

        random.shuffle(times_fifa)
        for jid, time in zip(jogadores, times_fifa):
            c.execute('UPDATE jogadores SET time = ? WHERE id = ?', (time, jid))
        conn.commit()
    return redirect('/')


@app.route('/salvar/<int:id>', methods=['POST'])
def salvar(id):
    nome = request.form.get(f'nome_{id}', '').strip()
    time = request.form.get(f'time_{id}', '').strip()
    ordem = request.form.get(f'ordem_{id}', '').strip()

    if not nome:
        return redirect('/')  # Ou renderizar uma mensagem de erro

    try:
        ordem_valor = int(ordem) if ordem else None
    except ValueError:
        ordem_valor = None  # Ignora ordem inválida

    with sqlite3.connect(DB) as conn:
        c = conn.cursor()

        # Verifica se o nome já existe para outro ID (evita duplicação de nome)
        c.execute('SELECT id FROM jogadores WHERE LOWER(nome) = LOWER(?) AND id != ?', (nome, id))
        if c.fetchone():
            return redirect('/')  # Nome duplicado – pode exibir uma mensagem específica se quiser

        c.execute('''
            UPDATE jogadores
            SET nome = ?, time = ?, ordem_escolha = ?
            WHERE id = ?
        ''', (nome, time or None, ordem_valor, id))
        conn.commit()

    return redirect('/')


@app.route('/remover/<int:id>', methods=['POST'])
def remover(id):
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()

        # Opcional: remover confrontos onde o jogador está envolvido
        c.execute('''
            DELETE FROM confrontos
            WHERE jogador_casa = (SELECT nome FROM jogadores WHERE id = ?)
               OR jogador_visitante = (SELECT nome FROM jogadores WHERE id = ?)
        ''', (id, id))

        # Remove o jogador
        c.execute('DELETE FROM jogadores WHERE id = ?', (id,))
        conn.commit()

    return redirect('/')



@app.route('/gerar_confrontos')
def gerar_confrontos():
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute('DELETE FROM confrontos')
        c.execute('SELECT nome FROM jogadores ORDER BY ordem_escolha')
        nomes = [row[0] for row in c.fetchall()]

        if len(nomes) % 2 != 0:
            return "Número de jogadores deve ser par."

        random.shuffle(nomes)
        for i in range(0, len(nomes), 2):
            c.execute('INSERT INTO confrontos (fase, jogador_casa, jogador_visitante) VALUES (?, ?, ?)',
                      ('Fase 1', nomes[i], nomes[i+1]))
        conn.commit()
        session['campeao'] = None
    return redirect('/chaveamento')



@app.route('/vencedor/<int:id>', methods=['POST'])
def vencedor(id):
    vencedor = request.form.get('vencedor', '').strip()
    if not vencedor:
        return redirect('/chaveamento')

    with sqlite3.connect(DB) as conn:
        c = conn.cursor()

        # Atualiza o vencedor do confronto atual
        c.execute('UPDATE confrontos SET vencedor = ? WHERE id = ?', (vencedor, id))
        conn.commit()

        # Recupera a fase atual
        c.execute('SELECT fase FROM confrontos WHERE id = ?', (id,))
        fase_atual = c.fetchone()[0]

        # Verifica se todos os confrontos da fase atual já têm vencedor
        c.execute('SELECT vencedor FROM confrontos WHERE fase = ?', (fase_atual,))
        vencedores = [v[0] for v in c.fetchall() if v[0]]

        c.execute('SELECT COUNT(*) FROM confrontos WHERE fase = ?', (fase_atual,))
        total_confrontos = c.fetchone()[0]

        # Se ainda há confrontos sem vencedor, não avança
        if len(vencedores) < total_confrontos:
            return redirect('/chaveamento')

        # Se apenas um vencedor, é o campeão
        if len(vencedores) == 1:
            session['campeao'] = vencedores[0]
            return redirect('/chaveamento')

        # Cria nova fase, evitando duplicações
        numero_fase_atual = int(fase_atual.split()[-1])
        nova_fase = f'Fase {numero_fase_atual + 1}'

        c.execute('SELECT COUNT(*) FROM confrontos WHERE fase = ?', (nova_fase,))
        if c.fetchone()[0] > 0:
            return redirect('/chaveamento')  # Já gerada anteriormente

        # Embaralha os vencedores e monta novos confrontos
        random.shuffle(vencedores)
        for i in range(0, len(vencedores) - 1, 2):
            c.execute('''
                INSERT INTO confrontos (fase, jogador_casa, jogador_visitante)
                VALUES (?, ?, ?)
            ''', (nova_fase, vencedores[i], vencedores[i + 1]))

        conn.commit()
    return redirect('/chaveamento')


@app.route('/chaveamento')
def chaveamento():
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM confrontos ORDER BY fase, id')
        dados = c.fetchall()

    fases = {}
    for id, fase, casa, visitante, vencedor in dados:
        fases.setdefault(fase, []).append({
            'id': id,
            'jogador_casa': casa,
            'jogador_visitante': visitante,
            'vencedor': vencedor
        })

    campeao = session.get('campeao')
    return render_template('chaveamento.html', fases=fases, campeao=campeao)



@app.route('/reset')
def reset():
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute('DELETE FROM jogadores')
        c.execute('DELETE FROM confrontos')
        conn.commit()
    session.clear()
    return redirect('/')

if __name__ == '__main__':
    init_db()
    app.run(debug=True)