
// State Management - Estado global de la app
let allMatches = [];
let SEASON_CACHE = [];
let currentFilter = 'all';
let customCombinada = [];
let _lastTopAlta = [];
let _lastTopMedia = [];
let ALL_BASE_CACHE_LOADED = false;

var PROGOL_REAL = [
  {n:1, home:'PUEBLA', away:'PUMAS'},{n:2, home:'PACHUCA', away:'TIGRES'},{n:3, home:'AGUILAS', away:'TOLUCA'},{n:4, home:'ELCHE', away:'VALENCIA'},{n:5, home:'ATH. BILBAO', away:'R. SOCIEDAD'},{n:6, home:'BOURNEMOUTH', away:'LEEDS'},{n:7, home:'LIVERPOOL', away:'ARSENAL'},{n:8, home:'MILAN', away:'INTER MILAN'},{n:9, home:'JUVENTUS', away:'NAPOLES'},{n:10, home:'AUGSBURGO', away:'FRIBURGO'},{n:11, home:'LORIENT', away:'BREST'},{n:12, home:'GREMIO', away:'AT. MINEIRO'},{n:13, home:'BOCA JRS', away:'RIVER PLATE'},{n:14, home:'U. CATOLICA', away:'U. DE CHILE'}
];
var REVANCHA_REAL = [
  {n:1, home:'MONTERREY', away:'TIJUANA'},{n:2, home:'GUADALAJARA', away:'ATLANTE'},{n:3, home:'S. LAGUNA', away:'NECAXA'},{n:4, home:'C. AZUL', away:'LEON'},{n:5, home:'GETAFE', away:'SEVILLA'},{n:6, home:'CHELSEA', away:'MAN. UNITED'},{n:7, home:'AJAX', away:'AZ ALKMAAR'}
];
var PROGOL_META = {fecha:'2026-10-30', hasta:'20:55', fuente:'TuLotero'};
