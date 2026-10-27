
-- LiAn V64.6.0 Supabase Historico - Base que crece
-- Ejecutar en Supabase > SQL Editor > New Query

-- 1. Ligas
CREATE TABLE IF NOT EXISTS leagues (
  code TEXT PRIMARY KEY, -- ej mex.1, eng.1
  name TEXT NOT NULL,
  country TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Equipos (normalizados)
CREATE TABLE IF NOT EXISTS teams (
  id TEXT PRIMARY KEY, -- slug: america-mex
  name TEXT NOT NULL,
  short_name TEXT,
  league_code TEXT REFERENCES leagues(code),
  logo_url TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_teams_league ON teams(league_code);
CREATE INDEX IF NOT EXISTS idx_teams_name ON teams(name);

-- 3. Partidos historicos (NUNCA borrar, solo upsert)
CREATE TABLE IF NOT EXISTS matches (
  id TEXT PRIMARY KEY, -- date_league_home_away slug
  external_id TEXT,
  date DATE NOT NULL,
  time TEXT,
  home TEXT NOT NULL,
  away TEXT NOT NULL,
  home_team_id TEXT REFERENCES teams(id),
  away_team_id TEXT REFERENCES teams(id),
  league TEXT,
  league_code TEXT,
  season TEXT, -- 2024-2025
  round TEXT,
  status TEXT DEFAULT 'NS',
  status_detail TEXT,
  estado TEXT DEFAULT 'PROGRAMADO', -- PROGRAMADO, EN_JUEGO, FINALIZADO
  home_score INT,
  away_score INT,
  score TEXT,
  home_xg REAL,
  away_xg REAL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_matches_unique ON matches(date, league_code, home, away);
CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(date DESC);
CREATE INDEX IF NOT EXISTS idx_matches_league ON matches(league_code);
CREATE INDEX IF NOT EXISTS idx_matches_estado ON matches(estado);
CREATE INDEX IF NOT EXISTS idx_matches_date_league ON matches(date, league_code);

-- 4. ELO historico (evolucion real, no hash)
CREATE TABLE IF NOT EXISTS elo_ratings (
  id BIGSERIAL PRIMARY KEY,
  team TEXT NOT NULL, -- nombre normalizado
  team_id TEXT REFERENCES teams(id),
  rating REAL NOT NULL DEFAULT 1500,
  date DATE NOT NULL,
  league_code TEXT,
  matches_played INT DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_elo_team_date ON elo_ratings(team, date DESC);
CREATE INDEX IF NOT EXISTS idx_elo_date ON elo_ratings(date DESC);

-- 5. Estadisticas por equipo (para Poisson ataque/defensa real)
CREATE TABLE IF NOT EXISTS team_stats (
  id BIGSERIAL PRIMARY KEY,
  team TEXT NOT NULL,
  team_id TEXT REFERENCES teams(id),
  league_code TEXT,
  matches_played INT DEFAULT 0,
  goals_for INT DEFAULT 0,
  goals_against INT DEFAULT 0,
  avg_goals_for REAL DEFAULT 0,
  avg_goals_against REAL DEFAULT 0,
  avg_xg_for REAL DEFAULT 0,
  avg_xg_against REAL DEFAULT 0,
  attack_strength REAL DEFAULT 1.0,
  defense_strength REAL DEFAULT 1.0,
  form_last5 TEXT, -- ej W-D-L-W-W
  points_last5 INT DEFAULT 0,
  last_update DATE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(team, league_code)
);
CREATE INDEX IF NOT EXISTS idx_team_stats_team ON team_stats(team);

-- 6. Predicciones historicas (por version de modelo)
CREATE TABLE IF NOT EXISTS predictions (
  id BIGSERIAL PRIMARY KEY,
  match_id TEXT REFERENCES matches(id) ON DELETE CASCADE,
  date DATE,
  model_version TEXT DEFAULT 'V64.6.0',
  prob_1 REAL,
  prob_x REAL,
  prob_2 REAL,
  xg_home REAL,
  xg_away REAL,
  favorite TEXT,
  confidence TEXT, -- Alta, Media, Limitada
  evidence INT,
  sufficiency TEXT,
  risk TEXT,
  resultado_real TEXT, -- 1, X, 2
  acierto BOOLEAN,
  source TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_predictions_match ON predictions(match_id);
CREATE INDEX IF NOT EXISTS idx_predictions_date ON predictions(date DESC);
CREATE INDEX IF NOT EXISTS idx_predictions_model ON predictions(model_version);

-- 7. Log de sincronizaciones
CREATE TABLE IF NOT EXISTS sync_log (
  id BIGSERIAL PRIMARY KEY,
  source TEXT,
  date DATE,
  count INT,
  duration_ms INT,
  status TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Trigger para updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_matches_updated_at ON matches;
CREATE TRIGGER update_matches_updated_at BEFORE UPDATE ON matches FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
DROP TRIGGER IF EXISTS update_team_stats_updated_at ON team_stats;
CREATE TRIGGER update_team_stats_updated_at BEFORE UPDATE ON team_stats FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- RLS: Desactivado para desarrollo, activaremos despues con service_role
ALTER TABLE leagues DISABLE ROW LEVEL SECURITY;
ALTER TABLE teams DISABLE ROW LEVEL SECURITY;
ALTER TABLE matches DISABLE ROW LEVEL SECURITY;
ALTER TABLE elo_ratings DISABLE ROW LEVEL SECURITY;
ALTER TABLE team_stats DISABLE ROW LEVEL SECURITY;
ALTER TABLE predictions DISABLE ROW LEVEL SECURITY;
ALTER TABLE sync_log DISABLE ROW LEVEL SECURITY;

-- Datos iniciales ligas
INSERT INTO leagues (code, name, country) VALUES 
('mex.1','Liga MX','Mexico'),
('arg.1','Liga Profesional Argentina','Argentina'),
('bra.1','Brasileirao','Brasil'),
('eng.1','Premier League','Inglaterra'),
('esp.1','La Liga','España'),
('ita.1','Serie A','Italia'),
('usa.1','MLS','USA')
ON CONFLICT (code) DO NOTHING;
