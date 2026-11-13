import { Component, OnDestroy, OnInit } from '@angular/core';
import { Subscription } from 'rxjs';
import { debounceTime } from 'rxjs/operators';
import { CommonModule, DecimalPipe, DatePipe, PercentPipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { GreenBinService } from '../../core/greenbin.service';
import { MetricCardComponent } from '../../shared/metric-card/metric-card.component';
import {
  MetricasGenerales, MetricasDia,
  Clasificacion, Dispositivo, CATEGORIAS
} from '../../core/models';

@Component({
  selector: 'gb-dashboard',
  standalone: true,
  imports: [CommonModule, RouterLink, MetricCardComponent, DecimalPipe, DatePipe, PercentPipe],
  template: `
    <div class="page-header">
      <div>
        <h1 class="page-title">Dashboard</h1>
        <p class="page-sub">Fundación Escuela Tecnológica de Neiva — {{ hoy | date:"EEEE d 'de' MMMM, yyyy" }}</p>
      </div>
      <div class="export">
        <a class="btn-export" href="/api/exportar.csv?formato=excel" download>
          <i class="ti ti-file-spreadsheet"></i> Exportar CSV
        </a>
        <a class="export-alt" href="/api/exportar.csv?formato=estandar" download
           title="Separador coma y punto decimal (Python, R, Google Sheets)">formato estándar</a>
      </div>
    </div>

    <!-- Métricas principales -->
    <div class="metrics-grid" *ngIf="metricas">
      <gb-metric-card
        icon="recycle"
        label="Clasificaciones hoy"
        [value]="(metricas.clasificacionesHoy | number) ?? ''"
        [sub]="textoVariacion()"
        iconColorClass="icon-green"
        [subColorClass]="(metricas.variacionVsAyer ?? 0) < 0 ? 'sub-warn' : 'sub-green'"
      />
      <gb-metric-card
        icon="chart-line"
        label="Confianza promedio"
        [value]="metricas.confianzaPromedio === null ? '—' : ((metricas.confianzaPromedio | percent:'1.0-0') ?? '')"
        sub="Umbral configurado: 70 %"
        iconColorClass="icon-blue"
        subColorClass="sub-muted"
      />
      <gb-metric-card
        icon="device-desktop"
        label="Dispositivos activos"
        [value]="metricas.dispositivosActivos + ' / ' + metricas.dispositivosTotal"
        [sub]="textoDispositivos()"
        iconColorClass="icon-green"
        [subColorClass]="metricas.dispositivosActivos === metricas.dispositivosTotal && metricas.dispositivosTotal ? 'sub-green' : 'sub-warn'"
      />
      <gb-metric-card
        icon="alert-triangle"
        label="Predicciones dudosas"
        [value]="(metricas.prediccionesDudosas | number) ?? ''"
        [sub]="metricas.pctDudosas + ' % de hoy'"
        iconColorClass="icon-warn"
        subColorClass="sub-warn"
      />
    </div>

    <div class="two-col">
      <!-- Gráfico semanal + distribución -->
      <div class="card">
        <div class="card-header">
          <i class="ti ti-chart-bar"></i>
          Clasificaciones — últimos 7 días
        </div>
        <div class="empty" *ngIf="historial.length && maxTotal === 0">
          <i class="ti ti-chart-bar-off"></i> Aún no hay clasificaciones esta semana
        </div>
        <div class="bar-chart" *ngIf="historial.length && maxTotal > 0">
          <div class="chart-bars">
            <div class="bar-group" *ngFor="let dia of historial; let i = index">
              <div class="bar-stack">
                <div class="bar-segment seg-organico"
                     [style.height.%]="(dia.organico / maxTotal) * 100"
                     [title]="'Orgánico: ' + dia.organico"></div>
                <div class="bar-segment seg-aprovechable"
                     [style.height.%]="(dia.aprovechable / maxTotal) * 100"
                     [title]="'Aprovechable: ' + dia.aprovechable"></div>
                <div class="bar-segment seg-no"
                     [style.height.%]="(dia.noAprovechable / maxTotal) * 100"
                     [title]="'No aprovechable: ' + dia.noAprovechable"></div>
              </div>
              <div class="bar-label" [class.bar-label--today]="i === historial.length - 1">{{ dia.fecha }}</div>
            </div>
          </div>
          <div class="chart-legend">
            <span class="legend-item"><span class="dot dot-org"></span>Orgánico</span>
            <span class="legend-item"><span class="dot dot-apr"></span>Aprovechable</span>
            <span class="legend-item"><span class="dot dot-no"></span>No aprovechable</span>
          </div>
        </div>

        <div class="divider"></div>

        <div class="card-header">
          <i class="ti ti-chart-pie"></i>
          Distribución por categoría — hoy
        </div>
        <div class="cat-bars">
          <div class="cat-bar-row" *ngFor="let cat of categorias">
            <div class="cat-bar-label">{{ cat.label }}</div>
            <div class="cat-bar-track">
              <div class="cat-bar-fill"
                   [style.width.%]="getCatPct(cat.id)"
                   [style.background]="cat.color"></div>
            </div>
            <div class="cat-bar-val">{{ getCatPct(cat.id) | number:'1.0-0' }}%</div>
          </div>
        </div>
      </div>

      <!-- Dispositivos -->
      <div class="card">
        <div class="card-header">
          <i class="ti ti-device-desktop"></i>
          Estado de dispositivos
          <a routerLink="/dispositivos" class="card-link">Ver todos →</a>
        </div>
        <div class="empty" *ngIf="!dispositivos.length">
          <i class="ti ti-plug-connected-x"></i> Ninguna Raspberry Pi se ha conectado todavía
        </div>
        <div class="devices-list">
          <div class="device-item" *ngFor="let d of dispositivos">
            <div class="device-dot" [class]="'dot-estado-' + d.estado"></div>
            <div class="device-info">
              <div class="device-name">{{ d.nombre }}</div>
              <div class="device-loc">
                <i class="ti ti-map-pin"></i> {{ d.ubicacion }}
              </div>
            </div>
            <div class="device-stats">
              <div class="device-cnt">{{ d.clasificacionesHoy }} hoy</div>
              <div class="device-conf">{{ d.confianzaPromedio | percent:'1.0-0' }} conf.</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Tabla de últimas clasificaciones -->
    <div class="card card--full">
      <div class="card-header">
        <i class="ti ti-history"></i>
        Últimas clasificaciones
      </div>
      <div class="table-wrap">
        <table class="log-table">
          <thead>
            <tr>
              <th>Hora</th>
              <th>Dispositivo</th>
              <th>Categoría</th>
              <th>Caneca</th>
              <th>Confianza</th>
              <th>Estado</th>
            </tr>
          </thead>
          <tbody>
            <tr *ngFor="let log of clasificaciones">
              <td class="td-mono">{{ log.timestamp | date:'HH:mm:ss' }}</td>
              <td class="td-muted">{{ log.dispositivoNombre }}</td>
              <td>
                <span class="pill pill--cat" [ngClass]="'pill-' + log.categoria">
                  {{ getCatLabel(log.categoria) }}
                </span>
              </td>
              <td class="td-muted">{{ getCaneca(log.categoria) }}</td>
              <td>
                <span class="conf-bar">
                  <span class="conf-fill"
                        [style.width.%]="log.confianza * 100"
                        [class.conf-fill--ok]="log.estado === 'seguro'"
                        [class.conf-fill--warn]="log.estado === 'dudoso'"></span>
                </span>
                {{ log.confianza | percent:'1.0-0' }}
              </td>
              <td>
                <span class="pill" [ngClass]="log.estado === 'seguro' ? 'pill--ok' : 'pill--warn'">
                  {{ log.estado === 'seguro' ? 'SEGURO' : 'DUDOSO' }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
        <div class="empty" *ngIf="!clasificaciones.length">
          <i class="ti ti-clock"></i> Sin clasificaciones registradas
        </div>
      </div>
    </div>
  `,
  styles: [`
    .page-header {
      display: flex; align-items: flex-start;
      justify-content: space-between; margin-bottom: 24px;
    }
    .page-title { font-size: 22px; font-weight: 600; color: var(--text-primary); }
    .page-sub   { font-size: 13px; color: var(--text-muted); margin-top: 2px; }
    .export { display: flex; flex-direction: column; align-items: flex-end; gap: 4px; }
    .btn-export {
      display: inline-flex; align-items: center; gap: 6px; text-decoration: none;
      background: var(--green); color: #fff; font-size: 13px; font-weight: 500;
      padding: 8px 14px; border-radius: 8px;
    }
    .btn-export:hover { filter: brightness(1.08); }
    .export-alt { font-size: 11px; color: var(--text-muted); }

    .metrics-grid {
      display: grid; grid-template-columns: repeat(4, 1fr);
      gap: 14px; margin-bottom: 24px;
    }
    .two-col {
      display: grid; grid-template-columns: 1fr 1fr;
      gap: 16px; margin-bottom: 24px;
    }
    .card {
      background: var(--surface); border: 1px solid var(--border);
      border-radius: 14px; padding: 20px;
    }
    .card--full { margin-bottom: 24px; }
    .empty { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--text-muted); padding: 12px 0; }
    .card-header {
      display: flex; align-items: center; gap: 8px;
      font-size: 14px; font-weight: 500; color: var(--text-primary);
      margin-bottom: 18px;
    }
    .card-header i { font-size: 16px; color: var(--text-muted); }
    .card-link {
      margin-left: auto; font-size: 12px;
      color: var(--green); text-decoration: none;
    }
    .divider { border: none; border-top: 1px solid var(--border); margin: 18px 0; }

    /* Gráfico de barras apiladas */
    .bar-chart { }
    .chart-bars {
      display: flex; align-items: flex-end; gap: 8px; height: 120px; margin-bottom: 10px;
    }
    .bar-group { display: flex; flex-direction: column; align-items: center; flex: 1; height: 100%; justify-content: flex-end; }
    .bar-stack { display: flex; flex-direction: column-reverse; width: 100%; flex: 1; }
    .bar-segment { width: 100%; transition: height 0.6s ease; border-radius: 0; }
    .bar-stack .bar-segment:last-child { border-radius: 4px 4px 0 0; }
    .seg-organico    { background: var(--green); }
    .seg-aprovechable{ background: #b0b0aa; }
    .seg-no          { background: #3d3d3a; }
    .bar-label {
      font-size: 11px; color: var(--text-muted);
      margin-top: 6px; text-align: center;
    }
    .bar-label--today { color: var(--green); font-weight: 600; }
    .chart-legend {
      display: flex; gap: 14px; margin-top: 8px;
    }
    .legend-item { display: flex; align-items: center; gap: 5px; font-size: 11px; color: var(--text-muted); }
    .dot { width: 8px; height: 8px; border-radius: 50%; }
    .dot-org { background: var(--green); }
    .dot-apr { background: #b0b0aa; }
    .dot-no  { background: #3d3d3a; }

    /* Distribución por categoría */
    .cat-bars { display: flex; flex-direction: column; gap: 10px; }
    .cat-bar-row { display: flex; align-items: center; gap: 10px; }
    .cat-bar-label { font-size: 12px; color: var(--text-muted); width: 90px; flex-shrink: 0; }
    .cat-bar-track { flex: 1; height: 8px; border-radius: 99px; background: var(--surface-hover); overflow: hidden; }
    .cat-bar-fill  { height: 100%; border-radius: 99px; transition: width 0.6s ease; }
    .cat-bar-val   { font-size: 12px; color: var(--text-muted); width: 32px; text-align: right; }

    /* Dispositivos */
    .devices-list { display: flex; flex-direction: column; gap: 8px; }
    .device-item {
      display: flex; align-items: center; gap: 12px;
      padding: 10px 12px; border-radius: 8px;
      border: 1px solid var(--border); background: var(--bg);
      transition: background 0.15s; cursor: default;
    }
    .device-item:hover { background: var(--surface-hover); }
    .device-dot { width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }
    .dot-estado-online  { background: var(--green); }
    .dot-estado-offline { background: #e24b4a; }
    .dot-estado-warning { background: #f57c00; }
    .device-info { flex: 1; min-width: 0; }
    .device-name { font-size: 13px; font-weight: 500; color: var(--text-primary); }
    .device-loc  { font-size: 11px; color: var(--text-muted); display: flex; align-items: center; gap: 3px; }
    .device-loc i { font-size: 11px; }
    .device-stats { text-align: right; }
    .device-cnt  { font-size: 13px; font-weight: 500; color: var(--text-primary); }
    .device-conf { font-size: 11px; color: var(--text-muted); }

    /* Tabla */
    .table-wrap { overflow-x: auto; }
    .log-table { width: 100%; border-collapse: collapse; }
    .log-table th {
      font-size: 11px; font-weight: 500; color: var(--text-muted);
      text-align: left; padding: 8px 12px;
      border-bottom: 1px solid var(--border);
      text-transform: uppercase; letter-spacing: .04em;
    }
    .log-table td { font-size: 13px; padding: 10px 12px; border-bottom: 1px solid var(--border); color: var(--text-primary); }
    .log-table tr:last-child td { border-bottom: none; }
    .log-table tr:hover td { background: var(--surface-hover); }
    .td-mono { font-family: var(--font-mono, monospace); font-size: 12px; color: var(--text-muted); }
    .td-muted { color: var(--text-muted); }

    .pill {
      display: inline-block; font-size: 11px; font-weight: 500;
      padding: 2px 8px; border-radius: 99px; white-space: nowrap;
    }
    .pill--ok   { background: var(--green-light); color: var(--green-dark); }
    .pill--warn { background: #fff3e0; color: #e65100; }
    .pill-organico       { background: var(--green-light); color: var(--green-dark); }
    .pill-aprovechable   { background: var(--surface-hover); color: var(--text-muted); border: 1px solid var(--border); }
    .pill-no_aprovechable{ background: #f1efe8; color: #444441; }

    .conf-bar {
      display: inline-block; width: 48px; height: 5px;
      background: var(--surface-hover); border-radius: 99px;
      vertical-align: middle; margin-right: 6px; overflow: hidden;
    }
    .conf-fill { display: block; height: 100%; border-radius: 99px; }
    .conf-fill--ok   { background: var(--green); }
    .conf-fill--warn { background: #f57c00; }

    @media (max-width: 900px) {
      .metrics-grid { grid-template-columns: 1fr 1fr; }
      .two-col { grid-template-columns: 1fr; }
    }
    @media (max-width: 520px) {
      .metrics-grid { grid-template-columns: 1fr; }
    }
  `]
})
export class DashboardComponent implements OnInit, OnDestroy {
  metricas: MetricasGenerales | null = null;
  historial: MetricasDia[] = [];
  clasificaciones: Clasificacion[] = [];
  dispositivos: Dispositivo[] = [];
  categorias = CATEGORIAS;
  hoy = new Date();
  maxTotal = 0;

  private sub?: Subscription;

  constructor(private svc: GreenBinService) {}

  ngOnInit(): void {
    this.cargar();
    // Cada clasificación nueva o cambio de estado de la Pi recarga el tablero
    this.sub = this.svc.eventos$.pipe(debounceTime(300)).subscribe(() => this.cargar());
  }

  ngOnDestroy(): void { this.sub?.unsubscribe(); }

  cargar(): void {
    this.hoy = new Date();
    this.svc.getMetricas().subscribe(m => this.metricas = m);
    this.svc.getHistorialSemanal().subscribe(h => {
      this.historial = h;
      this.maxTotal = Math.max(0, ...h.map(d => d.total));
    });
    this.svc.getUltimasClasificaciones().subscribe(c => this.clasificaciones = c);
    this.svc.getDispositivos().subscribe(d => this.dispositivos = d);
  }

  textoVariacion(): string {
    const v = this.metricas?.variacionVsAyer;
    if (v === null || v === undefined) return 'Sin datos de ayer para comparar';
    return `${v >= 0 ? '↑' : '↓'} ${Math.abs(v)} % vs. ayer`;
  }

  textoDispositivos(): string {
    const m = this.metricas;
    if (!m || !m.dispositivosTotal) return 'Ninguno registrado';
    const fuera = m.dispositivosTotal - m.dispositivosActivos;
    return fuera === 0 ? 'Todos en línea' : `${fuera} sin conexión`;
  }

  getCatLabel(id: string): string {
    return CATEGORIAS.find(c => c.id === id)?.label ?? id;
  }
  getCaneca(id: string): string {
    return CATEGORIAS.find(c => c.id === id)?.caneca ?? '';
  }
  getCatPct(id: string): number {
    return (this.metricas?.distribucion as Record<string, number> | undefined)?.[id] ?? 0;
  }
}
