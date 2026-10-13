-- Deploy Fase 3 — APENAS tabelas novas (não altera tabelas existentes)
-- Executar na base MariaDB principal da aplicação (DB_SGC)

SOURCE criar_Tb_ML_Log.sql;
SOURCE criar_Tb_Correcao_Feedback.sql;
SOURCE criar_tb_performance.sql;

-- Alternativa sem SOURCE (executar direto no cliente SQL):
-- Ver conteúdo de criar_Tb_ML_Log.sql e criar_Tb_Correcao_Feedback.sql
