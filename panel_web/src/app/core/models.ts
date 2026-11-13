// ── Categorías de residuos ────────────────────────────────────────────────────
export type CategoriaResiduo = 'organico' | 'aprovechable' | 'no_aprovechable';

export interface CategoriaInfo {
  id: CategoriaResiduo;
  label: string;
  caneca: string;
  color: string;        // color hex para indicadores visuales
  bgClass: string;      // clase CSS para fondo
  textClass: string;    // clase CSS para texto
}

export const CATEGORIAS: CategoriaInfo[] = [
  {
    id: 'organico',
    label: 'Orgánico',
    caneca: 'Caneca verde',
    color: '#1D9E75',
    bgClass: 'cat-organico',
    textClass: 'cat-organico-text'
  },
  {
    id: 'aprovechable',
    label: 'Aprovechable',
    caneca: 'Caneca blanca',
    color: '#d0cfc9',
    bgClass: 'cat-aprovechable',
    textClass: 'cat-aprovechable-text'
  },
  {
    id: 'no_aprovechable',
    label: 'No aprovechable',
    caneca: 'Caneca negra',
    color: '#3d3d3a',
    bgClass: 'cat-no-aprovechable',
    textClass: 'cat-no-aprovechable-text'
  }
];

// ── Dispositivo ───────────────────────────────────────────────────────────────
// Se registra solo: la Raspberry Pi envía un "latido" cada 30 s al backend.
export type EstadoDispositivo = 'online' | 'offline' | 'warning';

export interface Dispositivo {
  id: string;
  nombre: string;
  ubicacion: string;
  estado: EstadoDispositivo;
  clasificacionesHoy: number;
  confianzaPromedio: number;     // 0-1
  modelo: string;
  umbral: number;                // 0-1
  ultimoLatido: string | null;
  ultimaClasificacion: string | null;
}

// ── Clasificación ─────────────────────────────────────────────────────────────
// Solo el resultado: la Raspberry Pi nunca envía imágenes (RNF-05).
export type EstadoPrediccion = 'seguro' | 'dudoso';

export interface Clasificacion {
  id: number;
  timestamp: Date;
  dispositivoId: string;
  dispositivoNombre: string;
  categoria: CategoriaResiduo;
  confianza: number;             // 0-1
  estado: EstadoPrediccion;
  tiempoS: number | null;        // detección → audio, en segundos (PR-08)
}

// ── Métricas del dashboard ────────────────────────────────────────────────────
export interface MetricasDia {
  fecha: string;                 // Lun, Mar...
  dia: string;                   // AAAA-MM-DD
  total: number;
  organico: number;
  aprovechable: number;
  noAprovechable: number;
}

export interface MetricasGenerales {
  clasificacionesHoy: number;
  clasificacionesAyer: number;
  variacionVsAyer: number | null; // porcentaje; null si ayer no hubo datos
  confianzaPromedio: number | null;
  dispositivosActivos: number;
  dispositivosTotal: number;
  prediccionesDudosas: number;
  pctDudosas: number;
  distribucion: Record<CategoriaResiduo, number>;   // % de hoy por categoría
  totalHistorico: number;
}

// ── Mensajes del WebSocket /ws/eventos ────────────────────────────────────────
export type EventoPanel =
  | { tipo: 'clasificacion'; datos: Clasificacion }
  | { tipo: 'dispositivo' }
  | { tipo: 'actualizar' };
