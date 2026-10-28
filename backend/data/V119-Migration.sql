
-- V119 - Modelo Disciplinario: tarjetas, faltas, arbitro, posesion
-- Extension tabla matches para variables disciplinarias

-- Agregar columnas disciplinarias a matches (nullable para no romper existing)
ALTER TABLE matches ADD COLUMN IF NOT EXISTS home_yellow INT DEFAULT 0;
ALTER TABLE matches ADD COLUMN IF NOT EXISTS away_yellow INT DEFAULT 0;
ALTER TABLE matches ADD COLUMN IF NOT EXISTS home_red INT DEFAULT 0;
ALTER TABLE matches ADD COLUMN IF NOT EXISTS away_red INT DEFAULT 0;
ALTER TABLE matches ADD COLUMN IF NOT EXISTS home_fouls INT DEFAULT 0;
ALTER TABLE matches ADD COLUMN IF NOT EXISTS away_fouls INT DEFAULT 0;
ALTER TABLE matches ADD COLUMN IF NOT EXISTS referee TEXT;
ALTER TABLE matches ADD COLUMN IF NOT EXISTS home_possession REAL DEFAULT 50;
ALTER TABLE matches ADD COLUMN IF NOT EXISTS away_possession REAL DEFAULT 50;
ALTER TABLE matches ADD COLUMN IF NOT EXISTS home_shots INT DEFAULT 0;
ALTER TABLE matches ADD COLUMN IF NOT EXISTS away_shots INT DEFAULT 0;
ALTER TABLE matches ADD COLUMN IF NOT EXISTS home_shots_on_target INT DEFAULT 0;
ALTER TABLE matches ADD COLUMN IF NOT EXISTS away_shots_on_target INT DEFAULT 0;

-- Tabla nueva para estadisticas detalladas por partido (si ESPN no trae, se llena via API-Football)
CREATE TABLE IF NOT EXISTS match_stats (
  match_id TEXT PRIMARY KEY,
  home_team TEXT,
  away_team TEXT,
  league_code TEXT,
  date DATE,
  referee TEXT,
  home_yellow INT DEFAULT 0,
  away_yellow INT DEFAULT 0,
  home_red INT DEFAULT 0,
  away_red INT DEFAULT 0,
  home_fouls INT DEFAULT 0,
  away_fouls INT DEFAULT 0,
  home_possession REAL DEFAULT 50,
  away_possession REAL DEFAULT 50,
  home_shots INT DEFAULT 0,
  away_shots INT DEFAULT 0,
  home_shots_on_target INT DEFAULT 0,
  away_shots_on_target INT DEFAULT 0,
  home_corners INT DEFAULT 0,
  away_corners INT DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Extender team_stats con disciplina
ALTER TABLE team_stats ADD COLUMN IF NOT EXISTS avg_yellow REAL DEFAULT 0;
ALTER TABLE team_stats ADD COLUMN IF NOT EXISTS avg_red REAL DEFAULT 0;
ALTER TABLE team_stats ADD COLUMN IF NOT EXISTS avg_fouls REAL DEFAULT 0;
ALTER TABLE team_stats ADD COLUMN IF NOT EXISTS discipline_index REAL DEFAULT 1.0;
ALTER TABLE team_stats ADD COLUMN IF NOT EXISTS avg_possession REAL DEFAULT 50;
ALTER TABLE team_stats ADD COLUMN IF NOT EXISTS referee_bias REAL DEFAULT 0;

-- Tabla arbitros
CREATE TABLE IF NOT EXISTS referees (
  name TEXT PRIMARY KEY,
  matches INT DEFAULT 0,
  avg_yellow REAL DEFAULT 0,
  avg_red REAL DEFAULT 0,
  avg_fouls REAL DEFAULT 0,
  home_win_pct REAL DEFAULT 0,
  draw_pct REAL DEFAULT 0,
  away_win_pct REAL DEFAULT 0,
  strictness_index REAL DEFAULT 1.0,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indices
CREATE INDEX IF NOT EXISTS idx_match_stats_referee ON match_stats(referee);
CREATE INDEX IF NOT EXISTS idx_matches_referee ON matches(referee);
CREATE INDEX IF NOT EXISTS idx_team_stats_discipline ON team_stats(discipline_index);
