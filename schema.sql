-- DDL: modelo relacional normalizado (SQLite). Em MySQL: troque AUTOINCREMENT por AUTO_INCREMENT
-- e datetime('now','localtime') por CURRENT_TIMESTAMP.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS local (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  nome      TEXT NOT NULL UNIQUE,
  descricao TEXT
);

CREATE TABLE IF NOT EXISTS dispositivo (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  nome             TEXT NOT NULL UNIQUE,
  local_id         INTEGER NOT NULL REFERENCES local(id),
  altura_sensor_cm REAL NOT NULL DEFAULT 400 CHECK (altura_sensor_cm > 0),
  ativo            INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0,1))
);

CREATE TABLE IF NOT EXISTS nivel_alerta (
  id    INTEGER PRIMARY KEY,
  nome  TEXT NOT NULL UNIQUE,
  ordem INTEGER NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS tipo_comando (
  id        INTEGER PRIMARY KEY,
  codigo    TEXT NOT NULL UNIQUE,
  descricao TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS leitura (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  dispositivo_id   INTEGER NOT NULL REFERENCES dispositivo(id),
  nivel_alerta_id  INTEGER NOT NULL REFERENCES nivel_alerta(id),
  distancia_cm     REAL NOT NULL CHECK (distancia_cm >= 0),
  limite_perigo_cm REAL NOT NULL,
  criado_em        TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_leitura_disp_data ON leitura(dispositivo_id, criado_em);

CREATE TABLE IF NOT EXISTS comando (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  dispositivo_id  INTEGER NOT NULL REFERENCES dispositivo(id),
  tipo_comando_id INTEGER NOT NULL REFERENCES tipo_comando(id),
  status          TEXT NOT NULL CHECK (status IN ('ENVIADO','FALHA')),
  criado_em       TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS log_evento (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  dispositivo_id INTEGER REFERENCES dispositivo(id),
  tipo           TEXT NOT NULL CHECK (tipo IN ('MUDANCA_NIVEL','COMANDO','ERRO','SISTEMA')),
  mensagem       TEXT NOT NULL,
  criado_em      TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
