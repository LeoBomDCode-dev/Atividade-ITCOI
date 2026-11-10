"""Ponte Arduino <-> MQTT. Uso: python3 ponte_serial.py /dev/ttyACM0"""
import json, sys, time
import paho.mqtt.client as mqtt
import serial

PORTA = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyACM0"
MQTT_HOST = "localhost"
T_LEITURA = "enchente/leitura"
T_COMANDO = "enchente/comando"

# comando da API -> linha enviada ao Arduino
COMANDOS = {
    "SILENCIAR": "SILENCIAR",
    "ATIVAR_SOM": "ATIVAR_SOM",
    "COMPORTA_ABRIR": "COMPORTA:0",
    "COMPORTA_FECHAR": "COMPORTA:90",
    "MODO_AUTO": "AUTO",
}

ser = serial.Serial(PORTA, 9600, timeout=1)
time.sleep(2)  # o Uno reinicia ao abrir a serial


def ao_conectar(client, userdata, flags, reason_code, properties=None):
    client.subscribe(T_COMANDO)


def ao_receber(client, userdata, msg):
    try:
        linha = COMANDOS.get(json.loads(msg.payload)["cmd"])
    except (ValueError, KeyError, TypeError):
        return
    if linha:
        ser.write((linha + "\n").encode())


cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
cliente.on_connect = ao_conectar
cliente.on_message = ao_receber
cliente.connect(MQTT_HOST, 1883)
cliente.loop_start()

while True:
    bruto = ser.readline().decode(errors="ignore").strip()
    if bruto.startswith("{"):
        try:
            json.loads(bruto)               # só publica JSON válido
            cliente.publish(T_LEITURA, bruto)
        except ValueError:
            pass
