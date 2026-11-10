-- DML: dados iniciais (idempotente) e consultas de exemplo.
INSERT OR IGNORE INTO nivel_alerta (id, nome, ordem) VALUES
  (1,'SEGURO',1), (2,'ALERTA',2), (3,'PERIGO',3);

INSERT OR IGNORE INTO tipo_comando (id, codigo, descricao) VALUES
  (1,'SILENCIAR','Silencia o alarme sonoro'),
  (2,'ATIVAR_SOM','Reativa o alarme sonoro'),
  (3,'COMPORTA_ABRIR','Abre a comporta'),
  (4,'COMPORTA_FECHAR','Fecha a comporta'),
  (5,'MODO_AUTO','Devolve a comporta ao controle automático');

INSERT OR IGNORE INTO local (id, nome, descricao) VALUES
  (1,'Córrego Piloto','Ponto de monitoramento do protótipo');

INSERT OR IGNORE INTO dispositivo (id, nome, local_id, altura_sensor_cm) VALUES
  (1,'Arduino-01',1,400);

-- Consultas de exemplo (rodar manualmente):
-- Média/mínimo/máximo por hora nas últimas 24 h:
--   SELECT strftime('%Y-%m-%d %H:00', criado_em) AS hora, ROUND(AVG(distancia_cm),1) AS media,
--          MIN(distancia_cm) AS minima, MAX(distancia_cm) AS maxima
--   FROM leitura WHERE criado_em >= datetime('now','localtime','-24 hours') GROUP BY hora;
-- Quantas vezes cada nível ocorreu:
--   SELECT n.nome, COUNT(*) FROM leitura l JOIN nivel_alerta n ON n.id = l.nivel_alerta_id GROUP BY n.nome;
