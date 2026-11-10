-- V127.2 SQL - Tablas leagues/teams con lat/lon/altitud para remover hardcode TEAM_LOCATIONS
-- VersionHeader: V127.2 SQL | 2026-11-03 | backend/data/V127_2_Teams_Migration.sql

-- 1. Tabla leagues
CREATE TABLE IF NOT EXISTS leagues (
  code TEXT PRIMARY KEY, -- mex.1, esp.1, eng.1 etc
  name TEXT NOT NULL,
  country TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

-- 2. Tabla teams con geolocalización
CREATE TABLE IF NOT EXISTS teams (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL, -- Puebla, Toluca, America etc
  display_name TEXT, -- Club Puebla, Deportivo Toluca
  league_code TEXT REFERENCES leagues(code),
  city TEXT,
  stadium TEXT,
  lat DOUBLE PRECISION NOT NULL,
  lon DOUBLE PRECISION NOT NULL,
  altitude INT NOT NULL, -- metros sobre nivel del mar
  created_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(name, league_code)
);

-- 3. Índices
CREATE INDEX IF NOT EXISTS idx_teams_league ON teams(league_code);
CREATE INDEX IF NOT EXISTS idx_teams_name ON teams(name);

-- 4. Insert leagues (15 ligas mundiales)
INSERT INTO leagues (code, name, country) VALUES
('mex.1', 'Liga MX', 'Mexico'),
('esp.1', 'La Liga', 'Spain'),
('eng.1', 'Premier League', 'England'),
('ita.1', 'Serie A', 'Italy'),
('ger.1', 'Bundesliga', 'Germany'),
('fra.1', 'Ligue 1', 'France'),
('usa.1', 'MLS', 'USA'),
('bra.1', 'Brasileirao', 'Brazil'),
('arg.1', 'Liga Argentina', 'Argentina'),
('uefa.champions', 'Champions League', 'UEFA'),
('uefa.europa', 'Europa League', 'UEFA'),
('uefa.europa.conf', 'Conference League', 'UEFA'),
('concacaf.champions', 'Concacaf Champions', 'Concacaf'),
('eng.fa', 'FA Cup', 'England'),
('mex.cup', 'Copa MX', 'Mexico')
ON CONFLICT (code) DO NOTHING;

-- 5. Insert teams Liga MX con lat/lon/altitud REAL (reemplaza TEAM_LOCATIONS hardcode)
INSERT INTO teams (name, display_name, league_code, city, stadium, lat, lon, altitude) VALUES
('Toluca', 'Deportivo Toluca', 'mex.1', 'Toluca', 'Nemesio Diez', 19.287860, -99.654300, 2680),
('Puebla', 'Club Puebla', 'mex.1', 'Puebla', 'Cuauhtemoc', 19.079000, -98.165000, 2135),
('Pachuca', 'CF Pachuca', 'mex.1', 'Pachuca', 'Hidalgo', 20.105000, -98.757000, 2420),
('Pumas UNAM', 'Pumas UNAM', 'mex.1', 'CDMX', 'Olimpico Universitario', 19.331500, -99.192500, 2280),
('America', 'Club America', 'mex.1', 'CDMX', 'Azteca', 19.302800, -99.150400, 2240),
('Cruz Azul', 'Cruz Azul', 'mex.1', 'CDMX', 'Azteca', 19.302800, -99.150400, 2240),
('Leon', 'Club Leon', 'mex.1', 'Leon', 'Leon', 21.111500, -101.657000, 1815),
('Atletico San Luis', 'Atletico San Luis', 'mex.1', 'San Luis Potosi', 'Alfonso Lastras', 22.136800, -100.937800, 1860),
('Atlas', 'Atlas FC', 'mex.1', 'Guadalajara', 'Jalisco', 20.706900, -103.328000, 1566),
('Guadalajara', 'Chivas', 'mex.1', 'Guadalajara', 'Akron', 20.681800, -103.462500, 1566),
('Chivas', 'Chivas', 'mex.1', 'Guadalajara', 'Akron', 20.681800, -103.462500, 1566),
('Queretaro', 'Queretaro FC', 'mex.1', 'Queretaro', 'Corregidora', 20.578800, -100.369700, 1820),
('Juarez', 'FC Juarez', 'mex.1', 'Ciudad Juarez', 'Olimpico Benito Juarez', 31.738000, -106.487000, 1120),
('FC Juarez', 'FC Juarez', 'mex.1', 'Ciudad Juarez', 'Olimpico Benito Juarez', 31.738000, -106.487000, 1120),
('Monterrey', 'Rayados Monterrey', 'mex.1', 'Monterrey', 'BBVA', 25.669000, -100.244000, 540),
('Tigres UANL', 'Tigres UANL', 'mex.1', 'Monterrey', 'Universitario', 25.725000, -100.312000, 540),
('Tigres', 'Tigres', 'mex.1', 'Monterrey', 'Universitario', 25.725000, -100.312000, 540),
('Santos Laguna', 'Santos Laguna', 'mex.1', 'Torreon', 'TSM Corona', 25.561800, -103.470000, 1120),
('Santos', 'Santos Laguna', 'mex.1', 'Torreon', 'TSM Corona', 25.561800, -103.470000, 1120),
('Tijuana', 'Club Tijuana', 'mex.1', 'Tijuana', 'Caliente', 32.460000, -117.010000, 20),
('Mazatlan', 'Mazatlan FC', 'mex.1', 'Mazatlan', 'El Kraken', 23.247000, -106.417000, 10),
('Necaxa', 'Club Necaxa', 'mex.1', 'Aguascalientes', 'Victoria', 21.883300, -102.290000, 1880),
('FC Juarez', 'FC Juarez', 'mex.1', 'Ciudad Juarez', 'Olimpico', 31.738000, -106.487000, 1120)
ON CONFLICT (name, league_code) DO UPDATE SET lat=EXCLUDED.lat, lon=EXCLUDED.lon, altitude=EXCLUDED.altitude, city=EXCLUDED.city, stadium=EXCLUDED.stadium;

-- Verificación
-- SELECT * FROM teams WHERE league_code='mex.1' ORDER BY altitude DESC;
-- SELECT COUNT(*) FROM teams; -- debe dar 20+ equipos Liga MX
-- SELECT COUNT(*) FROM leagues; -- 15 ligas

-- END V127.2 SQL | backend/data/V127_2_Teams_Migration.sql
