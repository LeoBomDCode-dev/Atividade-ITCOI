#include <Servo.h>

// PINOS
const int TRIG = 9, ECHO = 10;
const int LED_VERDE = 5, LED_AMARELO = 6, LED_VERMELHO = 7;
const int BUZZER = 8, BOTAO = 2, POT = A0, SERVO_PIN = 3;
const float DIST_MIN = 7.0;

Servo comporta;
float distancia = 400.0;
unsigned long tLeitura = 0, tBip = 0, tEnvio = 0, tBotao = 0;
bool bipLigado = false, silenciado = false, botaoAnterior = HIGH;
bool comportaManual = false;
int anguloManual = 0, posicaoServo = -1, freqAtual = 0;
String entrada = "";

void somLigar(int f) { if (f != freqAtual) { tone(BUZZER, f); freqAtual = f; } }
void somDesligar()   { if (freqAtual != 0) { noTone(BUZZER); freqAtual = 0; } }

void moverComporta(int a) {
  if (a != posicaoServo) { comporta.write(a); posicaoServo = a; }
}

float lerDistancia() {
  digitalWrite(TRIG, LOW);  delayMicroseconds(2);
  digitalWrite(TRIG, HIGH); delayMicroseconds(10);
  digitalWrite(TRIG, LOW);
  unsigned long dur = pulseIn(ECHO, HIGH, 30000);
  if (dur == 0) return 400.0;              // sem eco = longe
  return min(400.0, dur * 0.0343 / 2.0);
}

void processar(String c) {
  if (c == "SILENCIAR")        silenciado = true;
  else if (c == "ATIVAR_SOM")  silenciado = false;
  else if (c == "AUTO")        comportaManual = false;
  else if (c.startsWith("COMPORTA:")) {
    anguloManual = constrain(c.substring(9).toInt(), 0, 180);
    comportaManual = true;
  }
}

void lerComandos() {
  while (Serial.available()) {
    char ch = Serial.read();
    if (ch == '\n') { entrada.trim(); processar(entrada); entrada = ""; }
    else if (ch != '\r' && entrada.length() < 30) entrada += ch;
  }
}

void setup() {
  pinMode(LED_VERDE, OUTPUT); pinMode(LED_AMARELO, OUTPUT); pinMode(LED_VERMELHO, OUTPUT);
  pinMode(BUZZER, OUTPUT); pinMode(TRIG, OUTPUT); pinMode(ECHO, INPUT);
  pinMode(BOTAO, INPUT_PULLUP);
  comporta.attach(SERVO_PIN);
  moverComporta(0);
  Serial.begin(9600);
  tone(BUZZER, 1500); delay(300); noTone(BUZZER);   // bipe de teste
}

void loop() {
  unsigned long agora = millis();
  lerComandos();

  // Limites ajustados pelo potenciômetro (perigo: 30 a 200 cm)
  float distPerigo = 15;
  float distAlerta = 25;
  float distMax    = 25;

  // Botão físico: alterna silêncio
  bool botao = digitalRead(BOTAO);
  if (botao == LOW && botaoAnterior == HIGH && agora - tBotao > 200) {
    silenciado = !silenciado; tBotao = agora;
  }
  botaoAnterior = botao;

  // Leitura a cada 60 ms
  if (agora - tLeitura >= 60) { tLeitura = agora; distancia = lerDistancia(); }

  const char* nivel = "SEGURO";
  if (distancia <= distPerigo) nivel = "PERIGO";
  else if (distancia <= distAlerta) nivel = "ALERTA";

  digitalWrite(LED_VERDE,    nivel[0] == 'S');
  digitalWrite(LED_AMARELO,  nivel[0] == 'A');
  digitalWrite(LED_VERMELHO, nivel[0] == 'P');

  // Comporta: automática (fecha em PERIGO) ou comando remoto
  moverComporta(comportaManual ? anguloManual : (nivel[0] == 'P' ? 90 : 0));

  // Telemetria em JSON a cada 500 ms
  if (agora - tEnvio >= 500) {
    tEnvio = agora;
    Serial.print("{\"dist\":");        Serial.print(distancia, 1);
    Serial.print(",\"perigo\":");      Serial.print(distPerigo, 0);
    Serial.print(",\"nivel\":\"");     Serial.print(nivel);
    Serial.print("\",\"silenciado\":"); Serial.print(silenciado ? 1 : 0);
    Serial.print(",\"comporta\":");    Serial.print(posicaoServo);
    Serial.print(",\"modo\":\"");      Serial.print(comportaManual ? "MANUAL" : "AUTO");
    Serial.println("\"}");
  }

  // Som dinâmico
  if (distancia > distMax || silenciado) { somDesligar(); return; }

  float d = constrain(distancia, DIST_MIN, distMax);
  int freq = map((long)d, (long)distMax, (long)DIST_MIN, 500, 2500);
  freq = (freq / 100) * 100;
  int intervalo = map((long)d, (long)distMax, (long)DIST_MIN, 500, 0);

  if (intervalo < 40) somLigar(freq);
  else {
    if (agora - tBip >= (unsigned long)intervalo) { tBip = agora; bipLigado = !bipLigado; }
    if (bipLigado) somLigar(freq); else somDesligar();
  }
}
