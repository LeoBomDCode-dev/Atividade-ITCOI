"""API REST + consumidor MQTT. Rode no Raspberry Pi: python3 app.py"""
import json, os, sqlite3, threading, time
from datetime import datetime

import paho.mqtt.client as mqtt
from flask import Flask, jsonify, request, send_from_directory

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, "enchente.db")
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
T_LEITURA = "enchente/leitura"
T_COMANDO = "enchente/comando"
INTERVALO_GRAVACAO = 5          # segundos entre gravações (grava na hora se o nível mudar)
DISPOSITIVO_PADRAO = 1
NIVEIS = {"SEGURO": 1, "ALERTA": 2, "PERIGO": 3}

app = Flask(__name__, static_folder=os.path.join(BASE, "static"))
lock = threading.Lock()
estado = {"nivel": {}, "gravacao": {}, "atual": {}}


# ---------- banco ----------
def db():
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def consultar(sql, args=()):
    con = db()
    try:
        return [dict(r) for r in con.execute(sql, args).fetchall()]
    finally:
        con.close()


def executar(sql, args=()):
    con = db()
    try:
        cur = con.execute(sql, args)
        con.commit()
        return cur.lastrowid
    finally:
        con.close()


def iniciar_banco():
    con = db()
    try:
        for arq in ("schema.sql", "dados.sql"):
            with open(os.path.join(BASE, arq), encoding="utf-8") as f:
                con.executescript(f.read())
    finally:
        con.close()


def registrar_log(tipo, mensagem, disp=DISPOSITIVO_PADRAO):
    executar("INSERT INTO log_evento (dispositivo_id, tipo, mensagem) VALUES (?,?,?)",
             (disp, tipo, mensagem))


# ---------- MQTT ----------
def ao_conectar(client, userdata, flags, reason_code, properties=None):
    print("on_connect:", reason_code, flush=True)
    if reason_code.is_failure:
        registrar_log("ERRO", f"Broker recusou a conexão: {reason_code}")
        return
    client.subscribe(T_LEITURA)
    registrar_log("SISTEMA", "Conectado ao broker MQTT", None)


def ao_receber(client, userdata, msg):
    bruto = msg.payload.decode(errors="replace")
    try:
        d = json.loads(bruto)
        dist = float(d["dist"])
        limite = float(d["perigo"])
        nivel = d["nivel"]
        if nivel not in NIVEIS or dist < 0:
            raise ValueError("valores fora do esperado")
    except (ValueError, KeyError, TypeError):
        registrar_log("ERRO", "Payload inválido: " + bruto[:200])
        return

    disp, agora = DISPOSITIVO_PADRAO, time.time()
    with lock:
        anterior = estado["nivel"].get(disp)
        mudou = anterior != nivel
        gravar = mudou or agora - estado["gravacao"].get(disp, 0) >= INTERVALO_GRAVACAO
        estado["nivel"][disp] = nivel
        if gravar:
            estado["gravacao"][disp] = agora
        estado["atual"][disp] = {**d, "dist": dist, "recebido_ts": agora,
                                 "recebido_em": datetime.now().isoformat(timespec="seconds")}
    if gravar:
        executar("INSERT INTO leitura (dispositivo_id, nivel_alerta_id, distancia_cm, limite_perigo_cm)"
                 " VALUES (?,?,?,?)", (disp, NIVEIS[nivel], dist, limite))
    if mudou and anterior is not None:
        registrar_log("MUDANCA_NIVEL", f"Nível mudou de {anterior} para {nivel} ({dist:.1f} cm)")


mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqtt_client.on_connect = ao_conectar
mqtt_client.on_message = ao_receber


# ---------- utilidades ----------
def arg_int(nome, padrao, minimo, maximo):
    valor = request.args.get(nome, padrao, type=int)
    return max(minimo, min(maximo, valor))


# ---------- rotas ----------
@app.get("/")
def pagina():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/leitura/atual")
def leitura_atual():
    disp = request.args.get("dispositivo_id", DISPOSITIVO_PADRAO, type=int)
    with lock:
        atual = estado["atual"].get(disp)
    if not atual:
        return jsonify({"online": False})
    online = time.time() - atual["recebido_ts"] < 5
    return jsonify({**{k: v for k, v in atual.items() if k != "recebido_ts"}, "online": online})


@app.get("/api/leituras")
def leituras():
    disp = request.args.get("dispositivo_id", DISPOSITIVO_PADRAO, type=int)
    horas = arg_int("horas", 24, 1, 720)
    limite = arg_int("limite", 200, 1, 2000)
    return jsonify(consultar(
        "SELECT l.id, l.distancia_cm, l.limite_perigo_cm, n.nome AS nivel, l.criado_em "
        "FROM leitura l JOIN nivel_alerta n ON n.id = l.nivel_alerta_id "
        "WHERE l.dispositivo_id = ? AND l.criado_em >= datetime('now','localtime', ?) "
        "ORDER BY l.id DESC LIMIT ?", (disp, f"-{horas} hours", limite)))


@app.get("/api/logs")
def logs():
    return jsonify(consultar("SELECT id, tipo, mensagem, criado_em FROM log_evento "
                             "ORDER BY id DESC LIMIT ?", (arg_int("limite", 50, 1, 500),)))


@app.get("/api/comandos")
def listar_comandos():
    return jsonify(consultar(
        "SELECT c.id, t.codigo AS tipo, c.status, c.criado_em FROM comando c "
        "JOIN tipo_comando t ON t.id = c.tipo_comando_id ORDER BY c.id DESC LIMIT ?",
        (arg_int("limite", 20, 1, 200),)))


@app.post("/api/comandos")
def enviar_comando():
    tipo = (request.get_json(silent=True) or {}).get("tipo", "")
    achado = consultar("SELECT id FROM tipo_comando WHERE codigo = ?", (tipo,))
    if not achado:
        return jsonify({"erro": "Comando desconhecido"}), 400
    enviado = False
    if mqtt_client.is_connected():
        enviado = mqtt_client.publish(T_COMANDO, json.dumps({"cmd": tipo})).rc == mqtt.MQTT_ERR_SUCCESS
    status = "ENVIADO" if enviado else "FALHA"
    executar("INSERT INTO comando (dispositivo_id, tipo_comando_id, status) VALUES (?,?,?)",
             (DISPOSITIVO_PADRAO, achado[0]["id"], status))
    registrar_log("COMANDO", f"{tipo}: {status}")
    if not enviado:
        return jsonify({"erro": "Broker MQTT indisponível"}), 503
    return jsonify({"tipo": tipo, "status": status}), 201


@app.route("/api/locais", methods=["GET", "POST"])
def locais():
    if request.method == "GET":
        return jsonify(consultar("SELECT * FROM local ORDER BY nome"))
    d = request.get_json(silent=True) or {}
    if not d.get("nome"):
        return jsonify({"erro": "Informe o nome"}), 400
    try:
        novo = executar("INSERT INTO local (nome, descricao) VALUES (?,?)", (d["nome"], d.get("descricao")))
    except sqlite3.IntegrityError:
        return jsonify({"erro": "Local já cadastrado"}), 409
    return jsonify({"id": novo}), 201


@app.route("/api/dispositivos", methods=["GET", "POST"])
def dispositivos():
    if request.method == "GET":
        return jsonify(consultar("SELECT d.*, l.nome AS local FROM dispositivo d "
                                 "JOIN local l ON l.id = d.local_id ORDER BY d.nome"))
    d = request.get_json(silent=True) or {}
    try:
        novo = executar("INSERT INTO dispositivo (nome, local_id, altura_sensor_cm) VALUES (?,?,?)",
                        (d["nome"], d["local_id"], d.get("altura_sensor_cm", 400)))
    except (KeyError, sqlite3.IntegrityError):
        return jsonify({"erro": "Dados inválidos ou dispositivo já cadastrado"}), 400
    return jsonify({"id": novo}), 201


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    mqtt_client.enable_logger()
    print(f"Conectando ao broker em {MQTT_HOST}:{MQTT_PORT}", flush=True)
    iniciar_banco()
    mqtt_client.connect_async(MQTT_HOST, MQTT_PORT)
    mqtt_client.loop_start()
    app.run(host="0.0.0.0", port=5000, debug=False)
