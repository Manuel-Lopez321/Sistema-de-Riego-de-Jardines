import network
import umail
from machine import Pin, ADC
import time
import os
from umqtt.simple import MQTTClient

# Pines
sensor_humedad = ADC(Pin(34))
sensor_humedad.atten(ADC.ATTN_11DB)
sensor_flujo = Pin(25, Pin.IN)
in1 = Pin(5, Pin.OUT)
in2 = Pin(18, Pin.OUT)

def activarBomba():
    in1.on()
    in2.off()

def apagarBomba():
    in1.off()
    in2.off()

# Wi-Fi
ssid = 'INFINITUM0593'
password = 'XhSN23Gn2h'

# MQTT
MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883
MQTT_USER = ""
MQTT_PASSWORD = ""
MQTT_CLIENT_ID = "esp32_jardin"
MQTT_TOPIC = "jardin/datos"

# Correo
smtp_server = "smtp.gmail.com"
smtp_port = 465
smtp_user = "luismanuel141205@gmail.com"
smtp_password = "wylc bssq wajd xvjs"
destinatario = "luismanuel141205@gmail.com"

# Variables
conteo_pulsos = 0
factor_calibracion = 7.5
client = None

def contar_pulsos(pin):
    global conteo_pulsos
    conteo_pulsos += 1

sensor_flujo.irq(trigger=Pin.IRQ_FALLING, handler=contar_pulsos)

def conectar_wifi():
    print("Conectando a WiFi...", end="")
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(ssid, password)
    while not wlan.isconnected():
        print(".", end="")
        time.sleep(0.3)
    print("\n✅ WiFi Conectada:", wlan.ifconfig())

def enviar_correo(humedad_percent, litros_regados):
    asunto = "🌿💧 Reporte de Riego del Jardín Vertical 💧🌿"
    barra_humedad = f"""<div style="width: 100%; background-color: #eee;"><div style="width: {humedad_percent}%; background: #4CAF50; color: white; text-align: center;">{humedad_percent}%</div></div>"""
    barra_agua = f"""<div style="width: 100%; background-color: #eee;"><div style="width: {min(int(litros_regados * 100),100)}%; background: #2196F3; color: white; text-align: center;">{litros_regados:.2f} L</div></div>"""
    cuerpo_html = f"""<html><body><h1>Sistema de Riego Inteligente</h1><p>Humedad:</p>{barra_humedad}<p>Agua:</p>{barra_agua}</body></html>"""
    mensaje = f"From: {smtp_user}\r\nTo: {destinatario}\r\nSubject: {asunto}\r\nContent-Type: text/html\r\n\r\n{cuerpo_html}"
    server = umail.SMTP(smtp_server, smtp_port, ssl=True)
    server.login(smtp_user, smtp_password)
    server.to(destinatario)
    server.write(mensaje)
    server.send()
    server.quit()
    print("📧 Correo enviado ✅")

def llegada_mensaje(topic, msg):
    mensaje = msg.decode("utf-8")
    print("📥 MQTT recibido:", mensaje)
    if mensaje == "ON":
        activarBomba()
        print("🟢 Bomba encendida")
    elif mensaje == "OFF":
        apagarBomba()
        print("🔴 Bomba apagada")

def guardar_registro(humedad_percent, litros_regados):
    fecha = "{:02d}/{:02d}/{:4d} {:02d}:{:02d}:{:02d}".format(*time.localtime()[:6])
    registro = f"{fecha} - Humedad: {humedad_percent}% - Agua: {litros_regados:.2f} L\n"
    try:
        with open("datos_riego.txt", "a") as f:
            f.write(registro)
        print("📝 Registro guardado")
    except Exception as e:
        print("⚠️ Error al guardar:", e)

def subscribir():
    global client
    try:
        client = MQTTClient(MQTT_CLIENT_ID, MQTT_BROKER, port=MQTT_PORT)
        client.set_callback(llegada_mensaje)
        client.connect()
        client.subscribe(MQTT_TOPIC)
        print(f"🔗 Conectado a MQTT {MQTT_BROKER}, tópico {MQTT_TOPIC}")
    except Exception as e:
        print("❌ Error al conectar al broker MQTT:", e)

def principal():
    conectar_wifi()
    subscribir()
    global conteo_pulsos
    apagarBomba()

    while True:
        try:
            client.check_msg()

            humedad_valor = sensor_humedad.read()
            humedad_percent = int((4095 - humedad_valor) * 100 / 4095)
            print("🌡️ Humedad:", humedad_percent, "%")

            if humedad_percent < 40:
                print("🌱 Suelo seco, encendiendo bomba")
                conteo_pulsos = 0
                activarBomba()
                inicio = time.time()
                tiempo_riego = 20
                while time.time() - inicio < tiempo_riego:
                    time.sleep(0.1)
                apagarBomba()

                frecuencia = conteo_pulsos / tiempo_riego
                caudal = frecuencia / factor_calibracion
                litros = (caudal / 60) * tiempo_riego

                print(f"💧 Agua regada: {litros:.2f} L")

                enviar_correo(humedad_percent, litros)
                guardar_registro(humedad_percent, litros)

                mensaje = f"Humedad: {humedad_percent}% - Agua: {litros:.2f}L"
                client.publish(MQTT_TOPIC, mensaje)
                print(f"📤 Datos enviados a MQTT: {mensaje}")
            else:
                print("🌿 Suelo húmedo, bomba apagada")

            time.sleep(5)
        except Exception as e:
            print("⚠️ Error en el loop principal:", e)
            time.sleep(5)

# Ejecutar
if __name__ == "__main__":
    principal()
