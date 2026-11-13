import { Injectable, NgZone } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { BehaviorSubject, Observable, Subject } from 'rxjs';
import { map } from 'rxjs/operators';
import {
  Clasificacion, Dispositivo, EventoPanel, MetricasDia, MetricasGenerales
} from './models';

// ─────────────────────────────────────────────────────────────────────────────
// GreenBinService — datos reales del backend local (carpeta backend/).
//
// El panel se sirve desde el mismo backend, así que las rutas son relativas:
// /api/... y /ws/eventos. Con `ng serve`, proxy.conf.json las reenvía a
// http://localhost:8000.
// ─────────────────────────────────────────────────────────────────────────────
@Injectable({ providedIn: 'root' })
export class GreenBinService {
  private readonly api = '/api';

  /** Eventos en vivo (nueva clasificación, cambio de estado de un dispositivo). */
  readonly eventos$ = new Subject<EventoPanel>();
  /** true mientras el panel está conectado al backend por WebSocket. */
  readonly conectado$ = new BehaviorSubject<boolean>(false);

  private ws?: WebSocket;
  private espera = 1000;

  constructor(private http: HttpClient, private zone: NgZone) {
    this.conectarWs();
  }

  // ── REST ──────────────────────────────────────────────────────────────────
  getMetricas(): Observable<MetricasGenerales> {
    return this.http.get<MetricasGenerales>(`${this.api}/metricas`);
  }

  getHistorialSemanal(): Observable<MetricasDia[]> {
    return this.http.get<MetricasDia[]>(`${this.api}/historial`, { params: { dias: 7 } });
  }

  getUltimasClasificaciones(limite = 8): Observable<Clasificacion[]> {
    return this.http.get<any[]>(`${this.api}/clasificaciones`, { params: { limite } })
      .pipe(map(lista => lista.map(c => this.aClasificacion(c))));
  }

  getDispositivos(): Observable<Dispositivo[]> {
    return this.http.get<Dispositivo[]>(`${this.api}/dispositivos`);
  }

  // ── WebSocket con reconexión automática ───────────────────────────────────
  private conectarWs(): void {
    const protocolo = location.protocol === 'https:' ? 'wss' : 'ws';
    this.zone.runOutsideAngular(() => {
      const ws = new WebSocket(`${protocolo}://${location.host}/ws/eventos`);
      this.ws = ws;
      ws.onopen = () => this.zone.run(() => {
        this.espera = 1000;
        this.conectado$.next(true);
        this.eventos$.next({ tipo: 'actualizar' });   // recarga lo que se perdió desconectado
      });
      ws.onmessage = e => this.zone.run(() => {
        const msg = JSON.parse(e.data);
        if (msg.tipo === 'clasificacion') msg.datos = this.aClasificacion(msg.datos);
        this.eventos$.next(msg as EventoPanel);
      });
      ws.onclose = () => this.zone.run(() => {
        this.conectado$.next(false);
        setTimeout(() => this.conectarWs(), this.espera);
        this.espera = Math.min(this.espera * 2, 15000);
      });
    });
  }

  private aClasificacion(c: any): Clasificacion {
    return { ...c, timestamp: new Date(c.timestamp) };
  }
}
