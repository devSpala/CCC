"""
Figures produced:
  Figure 1 — N=1 IPC Latency, CPU, Named-Pipe Baseline & eta   (ipc_latency_graph.png)
  Figure 2 — Avg Per-Message Latency vs Payload N=1-20          (avg_latency_concurrency.png)
  Figure 3 — Total Execution Time vs Concurrency N              (total_time_vs_concurrency.png)
  Figure 4 — Aggregate Throughput vs Concurrency N              (throughput_vs_concurrency.png)
  Figure 5 — CCC Risk Heatmap                                   (ccc_risk_heatmap.png)
  Figure 6 — MEASURED WPF re-fire timeline (CCC vs idle)        (cpu_overhead_graph.png)
  Figure 7 — Connection Recovery Latency by State               (recovery_latency_graph.png)

"""

import csv
import statistics
import matplotlib.pyplot as plt
import numpy as np

plt.style.use('seaborn-v0_8-whitegrid')

COLORS  = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728',
           '#9467bd', '#8c564b', '#e377c2', '#7f7f7f']
MARKERS = ['o', 's', '^', 'D', 'v', 'P', '*', 'X']

UWP_QUOTA = 3000.0   # ms — Windows background task execution quota

# Figure 6 uses HARDCODED measured values (see ACTIVE_EVENTS / IDLE_EVENTS below).
# No CSV is read at runtime.
CAPTURE_WINDOW_S = 90.0
CCC_PROC_NAME    = 'BridgeHandler.exe'   # the WPF child that re-fires

# ================================================================
#  INTERPOLATION MODELS  (unchanged)
# ================================================================
def model_avg_ms(payload_mb, N=1):
    base     = 7.29 * (payload_mb ** 0.958)
    pipeline = 1.0 if N == 1 else max(0.90, 1.0 - 0.08 * np.log10(N))
    return round(base * pipeline, 3)

def model_cpu_ms(total_ms, payload_mb):
    if payload_mb <= 1 and total_ms < 15:
        return 0.0
    return round(total_ms * 0.22, 3)

def model_mem(N, payload_mb):
    raw            = N * payload_mb * 0.85
    reclaim_factor = max(0.05, 1.0 - 0.15 * np.log10(max(1, N)))
    return max(1, int(raw * reclaim_factor))

def model_pipe_ms(payload_mb):
    return 0.50 + 0.048 * payload_mb

# ================================================================
#  RAW MEASURED DATA  (unchanged from v4)
# ================================================================
raw_measured = {
    1: {
        1:    {'total_ms': 8.5029,     'avg_ms': 8.5029,     'cpu_ms': 0.0,       'mem_mb': 1},
        10:   {'total_ms': 60.3867,    'avg_ms': 60.3867,    'cpu_ms': 15.625,    'mem_mb': 10},
        100:  {'total_ms': 509.1221,   'avg_ms': 509.1221,   'cpu_ms': 125.0,     'mem_mb': 99},
        200:  {'total_ms': 1010.1107,  'avg_ms': 1010.1107,  'cpu_ms': 234.375,   'mem_mb': 200},
        500:  {'total_ms': 2752.5891,  'avg_ms': 2752.5891,  'cpu_ms': 578.125,   'mem_mb': 500},
        1024: {'total_ms': 7341.7573,  'avg_ms': 7341.7573,  'cpu_ms': 1843.75,   'mem_mb': 212},
    },
    5: {
        1:    {'total_ms': 187.8909,   'avg_ms': 37.578,     'cpu_ms': 15.625,    'mem_mb': 5},
        10:   {'total_ms': 280.719,    'avg_ms': 56.1438,    'cpu_ms': 78.125,    'mem_mb': 50},
        100:  {'total_ms': 2311.6724,  'avg_ms': 462.3345,   'cpu_ms': 531.25,    'mem_mb': 500},
        200:  {'total_ms': 4919.7856,  'avg_ms': 983.957,    'cpu_ms': 1125.0,    'mem_mb': 1000},
        500:  {'total_ms': 13414.453,  'avg_ms': 2682.891,   'cpu_ms': 3093.75,   'mem_mb': None},
        1024: {'total_ms': 32347.4548, 'avg_ms': 6469.491,   'cpu_ms': 7250.0,    'mem_mb': None},
    },
    10: {
        1:    {'total_ms': 280.5954,   'avg_ms': 28.0595,    'cpu_ms': 15.625,    'mem_mb': 10},
        10:   {'total_ms': 535.5095,   'avg_ms': 53.551,     'cpu_ms': 125.0,     'mem_mb': 100},
        100:  {'total_ms': 4413.8655,  'avg_ms': 441.387,    'cpu_ms': 1015.625,  'mem_mb': None},
        200:  {'total_ms': 9435.832,   'avg_ms': 943.583,    'cpu_ms': 2187.5,    'mem_mb': None},
        500:  {'total_ms': 26759.641,  'avg_ms': 2675.964,   'cpu_ms': 6296.875,  'mem_mb': None},
        1024: {'total_ms': 66124.495,  'avg_ms': 6612.450,   'cpu_ms': 14875.0,   'mem_mb': 523},
    },
    20: {
        1:    {'total_ms': 420.6392,   'avg_ms': 21.032,     'cpu_ms': 31.25,     'mem_mb': 20},
        10:   {'total_ms': 1028.4132,  'avg_ms': 51.421,     'cpu_ms': 250.0,     'mem_mb': 200},
        100:  {'total_ms': 8988.5947,  'avg_ms': 449.430,    'cpu_ms': 2109.375,  'mem_mb': None},
        200:  {'total_ms': 20223.4879, 'avg_ms': 1011.174,   'cpu_ms': 4578.125,  'mem_mb': None},
        500:  {'total_ms': 57104.357,  'avg_ms': 2855.218,   'cpu_ms': 11953.125, 'mem_mb': None},
        1024: {'total_ms': None,       'avg_ms': None,       'cpu_ms': None,      'mem_mb': None},
    },
    500: {
        1:    {'total_ms': 3140.512,   'avg_ms': 6.281,      'cpu_ms': 546.875,   'mem_mb': 431},
        10:   {'total_ms': 27115.633,  'avg_ms': 54.231,     'cpu_ms': 5453.125,  'mem_mb': 1818},
        100:  {'total_ms': 257409.072, 'avg_ms': 514.818,    'cpu_ms': 53390.625, 'mem_mb': 749},
        200:  {'total_ms': None,       'avg_ms': None,       'cpu_ms': None,      'mem_mb': None},
        500:  {'total_ms': None,       'avg_ms': None,       'cpu_ms': None,      'mem_mb': None},
        1024: {'total_ms': None,       'avg_ms': None,       'cpu_ms': None,      'mem_mb': None},
    },
    600: {
        1:    {'total_ms': 3738.493,   'avg_ms': 6.231,      'cpu_ms': 718.75,    'mem_mb': 531},
        10:   {'total_ms': 32660.369,  'avg_ms': 54.434,     'cpu_ms': 7187.5,    'mem_mb': 2818},
        100:  {'total_ms': 305709.137, 'avg_ms': 509.515,    'cpu_ms': 65171.875, 'mem_mb': None},
        200:  {'total_ms': None,       'avg_ms': None,       'cpu_ms': None,      'mem_mb': None},
        500:  {'total_ms': None,       'avg_ms': None,       'cpu_ms': None,      'mem_mb': None},
        1024: {'total_ms': None,       'avg_ms': None,       'cpu_ms': None,      'mem_mb': None},
    },
    700: {
        1:    {'total_ms': 4823.696,   'avg_ms': 6.891,      'cpu_ms': 671.875,   'mem_mb': 632},
        10:   {'total_ms': 39359.998,  'avg_ms': 56.229,     'cpu_ms': 8484.375,  'mem_mb': 947},
        100:  {'total_ms': None,       'avg_ms': None,       'cpu_ms': None,      'mem_mb': None},
        200:  {'total_ms': None,       'avg_ms': None,       'cpu_ms': None,      'mem_mb': None},
        500:  {'total_ms': None,       'avg_ms': None,       'cpu_ms': None,      'mem_mb': None},
        1024: {'total_ms': None,       'avg_ms': None,       'cpu_ms': None,      'mem_mb': None},
    },
    1000: {
        1:    {'total_ms': 8834.182,   'avg_ms': 8.834,      'cpu_ms': 1015.625,  'mem_mb': 743},
        10:   {'total_ms': 56086.106,  'avg_ms': 56.086,     'cpu_ms': 11765.625, 'mem_mb': 5056},
        100:  {'total_ms': None,       'avg_ms': None,       'cpu_ms': None,      'mem_mb': None},
        200:  {'total_ms': None,       'avg_ms': None,       'cpu_ms': None,      'mem_mb': None},
        500:  {'total_ms': None,       'avg_ms': None,       'cpu_ms': None,      'mem_mb': None},
        1024: {'total_ms': None,       'avg_ms': None,       'cpu_ms': None,      'mem_mb': None},
    },
}

data = {}
for N, payloads in raw_measured.items():
    data[N] = {}
    for p, metrics in payloads.items():
        d = dict(metrics)
        if d['avg_ms']   is None: d['avg_ms']   = model_avg_ms(p, N)
        if d['total_ms'] is None: d['total_ms'] = round(N * d['avg_ms'], 3)
        if d['cpu_ms']   is None: d['cpu_ms']   = model_cpu_ms(d['total_ms'], p)
        if d['mem_mb']   is None: d['mem_mb']   = model_mem(N, p)
        data[N][p] = d

def get(N, p, key):       return data[N][p][key]
def is_measured(N, p, key):
    try:    return raw_measured[N][p][key] is not None
    except KeyError: return False
def split(N, ps, key):
    xm, ym, xi, yi = [], [], [], []
    for p in ps:
        v = get(N, p, key)
        (xm if is_measured(N,p,key) else xi).append(p)
        (ym if is_measured(N,p,key) else yi).append(v)
    return xm, ym, xi, yi

PAYLOADS     = [1, 10, 100, 200, 500, 1024]
PAYLOAD_LABS = ['1 MB', '10 MB', '100 MB', '200 MB', '500 MB', '1 GB']
Ns_LOW       = [1, 5, 10, 20]
Ns_ALL       = [1, 5, 10, 20, 500, 600, 700, 1000]

# ---- Figures 1-5 and 7 are identical to v4 (omitted comments for brevity) ----

def plot_figure1():
    lat  = [get(1, p, 'avg_ms') for p in PAYLOADS]
    cpu  = [get(1, p, 'cpu_ms') for p in PAYLOADS]
    pipe = [model_pipe_ms(p)    for p in PAYLOADS]
    eta  = [l / pi for l, pi in zip(lat, pipe)]
    fig, ax1 = plt.subplots(figsize=(10, 6)); ax2 = ax1.twinx()
    ax1.plot(PAYLOADS, lat, marker='o', linestyle='-',  color='#1f77b4', linewidth=2, markersize=8, label='AppService Latency (ms)')
    ax1.plot(PAYLOADS, cpu, marker='s', linestyle='--', color='#ff7f0e', linewidth=2, markersize=8, label='CPU Usage (ms)')
    ax1.plot(PAYLOADS, pipe, marker='^', linestyle=':', color='#7f7f7f', linewidth=1.8, markersize=7, label='Named-pipe baseline (ms, lit.)')
    for p, v in zip(PAYLOADS, lat): ax1.annotate(f'{v:.1f}', (p, v), textcoords='offset points', xytext=(0,10), ha='center', fontsize=8, color='#1f77b4', fontweight='bold')
    for p, v in zip(PAYLOADS, cpu): ax1.annotate(f'{v:.1f}', (p, v), textcoords='offset points', xytext=(0,-14), ha='center', fontsize=8, color='#d62728', fontweight='bold')
    ax2.plot(PAYLOADS, eta, marker='D', linestyle='-.', color='#9467bd', linewidth=1.5, markersize=6, alpha=0.8, label=r'$\eta$ = AppSvc / Pipe ($\times$)')
    for p, e in zip(PAYLOADS, eta): ax2.annotate(f'{e:.0f}\u00d7', (p, e), textcoords='offset points', xytext=(0,7), ha='center', fontsize=7, color='#9467bd', fontstyle='italic')
    ax1.set_xscale('log'); ax1.set_yscale('log'); ax1.set_xticks(PAYLOADS); ax1.set_xticklabels(PAYLOAD_LABS)
    ax1.set_xlabel('Payload Data Size (MB / GB)', fontsize=11, fontweight='bold')
    ax1.set_ylabel('Time (ms) \u2014 Log Scale', fontsize=11, fontweight='bold')
    ax2.set_ylabel(r'Overhead Ratio $\eta$ (AppService / Named Pipe)', fontsize=10, fontweight='bold', color='#9467bd')
    ax2.tick_params(axis='y', labelcolor='#9467bd')
    l1,lb1=ax1.get_legend_handles_labels(); l2,lb2=ax2.get_legend_handles_labels()
    ax1.legend(l1+l2, lb1+lb2, loc='lower right', frameon=True, fontsize=8)
    ax1.set_title('IPC Latency, CPU Overhead & Named-Pipe Baseline vs Payload Size (N=1)\n'
                  r'$\eta$ confirms CCC is a structural lifecycle failure (LQIA\,L3), not AppService-specific', fontsize=12, fontweight='bold')
    ax1.grid(True, which='both', linestyle='--', alpha=0.6); plt.tight_layout()
    plt.savefig('ipc_latency_graph.png', dpi=300); plt.close(); print("Saved ipc_latency_graph.png")

def plot_figure2():
    plt.figure(figsize=(10, 6)); first=True
    for idx, N in enumerate(Ns_LOW):
        xm,ym,xi,yi=split(N,PAYLOADS,'avg_ms')
        plt.plot(xm,ym,marker=MARKERS[idx],linewidth=2,markersize=8,color=COLORS[idx],label=f'N={N}')
        if xi:
            lbl='Interpolated (MAPE\u200a=\u200a13.9%)' if first else '_nolegend_'
            plt.plot(xi,yi,marker=MARKERS[idx],linewidth=1.5,markersize=8,color=COLORS[idx],linestyle='--',alpha=0.60,label=lbl); first=False
    plt.xscale('log'); plt.yscale('log'); plt.xticks(PAYLOADS,PAYLOAD_LABS)
    plt.xlabel('Payload Size per Message', fontsize=11, fontweight='bold')
    plt.ylabel('Average Latency per Message (ms) \u2014 Log Scale', fontsize=11, fontweight='bold')
    plt.title('Average Per-Message IPC Latency vs Payload Size\nN = 1, 5, 10, 20  (solid = measured; dashed = interpolated, MAPE\u200a=\u200a13.9%)', fontsize=11, fontweight='bold')
    plt.legend(frameon=True, fontsize=9); plt.grid(True, which='both', linestyle='--', alpha=0.6); plt.tight_layout()
    plt.savefig('avg_latency_concurrency.png', dpi=300); plt.close(); print("Saved avg_latency_concurrency.png")

def plot_figure3():
    plt.figure(figsize=(10, 6)); plot_ps=[1,10,100]; plot_lab=['1 MB','10 MB','100 MB']; first=True
    for idx,(p,lab) in enumerate(zip(plot_ps,plot_lab)):
        xm,ym,xi,yi=[],[],[],[]
        for N in Ns_ALL:
            v=get(N,p,'total_ms')
            (xm if is_measured(N,p,'total_ms') else xi).append(N)
            (ym if is_measured(N,p,'total_ms') else yi).append(v)
        plt.plot(xm,ym,marker=MARKERS[idx],linewidth=2.5,markersize=8,color=COLORS[idx],label=f'{lab}')
        if xi:
            lbl='Interpolated (model)' if first else '_nolegend_'
            plt.plot(xi,yi,marker=MARKERS[idx],linewidth=1.5,markersize=8,color=COLORS[idx],linestyle='--',alpha=0.60,label=lbl); first=False
    n_ref=np.array([1,1000]); plt.plot(n_ref,n_ref*get(1,10,'avg_ms'),color='grey',linewidth=1.2,linestyle=':',label='Linear scaling ref (10 MB)')
    plt.xscale('log'); plt.yscale('log')
    plt.xlabel('Number of Concurrent IPC Messages (N)', fontsize=11, fontweight='bold')
    plt.ylabel('Total Execution Time (ms) \u2014 Log Scale', fontsize=11, fontweight='bold')
    plt.title('Total IPC Execution Time vs Concurrency Level\nNear-linear growth confirms serialised AppService queue \u2014 no parallelism benefit', fontsize=12, fontweight='bold')
    plt.legend(frameon=True, fontsize=9); plt.grid(True, which='both', linestyle='--', alpha=0.6); plt.tight_layout()
    plt.savefig('total_time_vs_concurrency.png', dpi=300); plt.close(); print("Saved total_time_vs_concurrency.png")

def plot_figure4():
    plt.figure(figsize=(10, 6)); plot_ps=[1,10,100]; plot_lab=['1 MB','10 MB','100 MB']; first=True
    for idx,(p,lab) in enumerate(zip(plot_ps,plot_lab)):
        xm,ym,xi,yi=[],[],[],[]
        for N in Ns_ALL:
            total=get(N,p,'total_ms'); tp=(N*p)/(total/1000.0)
            (xm if is_measured(N,p,'total_ms') else xi).append(N)
            (ym if is_measured(N,p,'total_ms') else yi).append(tp)
        plt.plot(xm,ym,marker=MARKERS[idx],linewidth=2.5,markersize=8,color=COLORS[idx],label=f'{lab}')
        if xi:
            lbl='Interpolated (model)' if first else '_nolegend_'
            plt.plot(xi,yi,marker=MARKERS[idx],linewidth=1.5,markersize=8,color=COLORS[idx],linestyle='--',alpha=0.60,label=lbl); first=False
    plt.xscale('log')
    plt.xlabel('Number of Concurrent IPC Messages (N)', fontsize=11, fontweight='bold')
    plt.ylabel('Aggregate Throughput (MB/s)', fontsize=11, fontweight='bold')
    plt.title('IPC Aggregate Throughput vs Concurrency Level\nThroughput saturates then degrades at high N \u2014 AppService broker bottleneck', fontsize=12, fontweight='bold')
    plt.legend(frameon=True, fontsize=9); plt.grid(True, which='both', linestyle='--', alpha=0.6); plt.tight_layout()
    plt.savefig('throughput_vs_concurrency.png', dpi=300); plt.close(); print("Saved throughput_vs_concurrency.png")

def plot_figure5():
    ns_h=[1,5,10,20]; ps_h=[1,10,100,200,500,1024]
    matrix=np.zeros((len(ns_h),len(ps_h))); is_meas=np.zeros((len(ns_h),len(ps_h)),dtype=bool)
    for i,N in enumerate(ns_h):
        for j,p in enumerate(ps_h):
            matrix[i,j]=get(N,p,'total_ms')/UWP_QUOTA; is_meas[i,j]=is_measured(N,p,'total_ms')
    fig,ax=plt.subplots(figsize=(11,5))
    im=ax.imshow(matrix,cmap='RdYlGn_r',vmin=0,vmax=22,aspect='auto')
    cbar=plt.colorbar(im,ax=ax,fraction=0.046,pad=0.04)
    cbar.set_label('Total Execution Time / UWP Background Quota (3 s)\nGreen < 1 = safe   |   Red > 1 = CCC guaranteed', fontsize=9)
    ax.set_xticks(range(len(ps_h))); ax.set_xticklabels(['1 MB','10 MB','100 MB','200 MB','500 MB','1 GB'], fontsize=10)
    ax.set_yticks(range(len(ns_h))); ax.set_yticklabels([f'N={N}' for N in ns_h], fontsize=10)
    ax.set_xlabel('Payload Size per Message', fontsize=11, fontweight='bold')
    ax.set_ylabel('Concurrent Messages (N)', fontsize=11, fontweight='bold')
    ax.set_title('CCC Risk Heatmap \u2014 Total Execution Time / UWP Background Quota\n[M] = directly measured   [I] = interpolated   (R\u22651 boundary robust to 24% max model residual)', fontsize=11, fontweight='bold')
    for i in range(len(ns_h)):
        for j in range(len(ps_h)):
            v=matrix[i,j]; tag='[M]' if is_meas[i,j] else '[I]'; col='white' if v>13 else 'black'
            ax.text(j,i,f'{v:.1f}x\n{tag}',ha='center',va='center',fontsize=8,fontweight='bold',color=col)
    plt.tight_layout(); plt.savefig('ccc_risk_heatmap.png', dpi=300); plt.close(); print("Saved ccc_risk_heatmap.png")


ACTIVE_EVENTS = [
    (0.007, 'spawn'),
    (1.774, 'spawn'), (2.306, 'exit'), (2.872, 'spawn'), (3.372, 'exit'),
    (6.735, 'spawn'), (7.304, 'exit'), (7.857, 'spawn'), (8.387, 'exit'),
    (12.813, 'spawn'), (13.346, 'exit'), (13.913, 'spawn'), (14.414, 'exit'),
    (17.772, 'spawn'), (18.339, 'exit'), (18.878, 'spawn'), (19.387, 'exit'),
    (22.731, 'spawn'), (23.330, 'exit'), (23.921, 'spawn'), (24.433, 'exit'),
    (27.757, 'spawn'), (28.307, 'exit'), (28.824, 'spawn'), (29.356, 'exit'),
    (29.906, 'spawn'), (30.412, 'exit'),
    (33.721, 'spawn'), (34.279, 'exit'), (34.864, 'spawn'), (35.363, 'exit'),
    (39.770, 'spawn'), (40.321, 'exit'), (40.856, 'spawn'), (41.364, 'exit'),
    (44.779, 'spawn'), (45.312, 'exit'), (45.879, 'spawn'), (46.380, 'exit'),
    (49.779, 'spawn'), (50.330, 'exit'), (50.897, 'spawn'), (51.411, 'exit'),
    (55.746, 'spawn'), (56.280, 'exit'), (56.846, 'spawn'), (57.344, 'exit'),
    (57.914, 'spawn'), (58.413, 'exit'),
    (61.780, 'spawn'), (62.296, 'exit'), (62.815, 'spawn'), (63.329, 'exit'),
    (63.863, 'spawn'), (64.351, 'exit'), (64.903, 'spawn'), (65.412, 'exit'),
    (69.762, 'spawn'), (70.279, 'exit'), (70.863, 'spawn'), (71.348, 'exit'),
    (76.748, 'spawn'), (77.313, 'exit'), (77.847, 'spawn'), (78.363, 'exit'),
    (78.898, 'spawn'), (79.396, 'exit'),
    (83.779, 'spawn'), (84.311, 'exit'), (84.863, 'spawn'), (85.363, 'exit'),
    (85.912, 'spawn'), (86.396, 'exit'),
]
IDLE_EVENTS = [ (0.004, 'spawn') ]

MEAS_REFIRES       = 36
MEAS_PERIOD_MEDIAN = 1.12
MEAS_PERIOD_MEAN   = 2.40
MEAS_LIFETIME_MED  = 0.52
IDLE_REFIRES       = 0

def _count_series(events, span):
    t = [0.0]; c = [0]; cur = 0
    for tt, e in events:
        cur += 1 if e == 'spawn' else -1
        t.append(tt); c.append(max(cur, 0))
    t.append(span); c.append(c[-1])
    return t, c

def plot_figure6():
    ta, ca = _count_series(ACTIVE_EVENTS, CAPTURE_WINDOW_S)
    ti, ci = _count_series(IDLE_EVENTS, CAPTURE_WINDOW_S)

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.axhspan(0.0, 1.0, color='#2ca02c', alpha=0.05, zorder=0)
    ax.axhspan(1.0, 2.4, color='#d62728', alpha=0.04, zorder=0)

    ax.step(ti, ci, where='post', color='#2ca02c', linewidth=2.2, zorder=3,
            label=f'Idle baseline \u2014 {IDLE_REFIRES} re-fires (measured)')
    ax.step(ta, ca, where='post', color='#d62728', linewidth=1.8, zorder=4,
            label=f'CCC active \u2014 {MEAS_REFIRES} re-fires / {int(CAPTURE_WINDOW_S)} s (measured)')
    ax.fill_between(ta, ca, step='post', color='#d62728', alpha=0.12, zorder=2)

    ax.text(1.0, 0.82, 'single-instance steady state (1 live WPF process)',
            fontsize=8, color='#1e7a1e', va='center', ha='left', style='italic')
    ax.text(1.0, 2.18, 'duplicate WPF process spawned \u2192 self-terminates (re-fire)',
            fontsize=8, color='#b03030', va='center', ha='left', style='italic')

    ax.annotate(
        'each excursion: resume re-launches a 2nd WPF process;\n'
        'it signals the incumbent and self-terminates (~0.5 s),\n'
        'and that exit re-fires the resume handler',
        xy=(2.9, 2.0), xytext=(30, 0.45),
        arrowprops=dict(arrowstyle='->', color='#7a1f1f', lw=1.3,
                        connectionstyle='arc3,rad=-0.2'),
        fontsize=8.5, color='#7a1f1f', fontweight='bold', va='center',
        bbox=dict(boxstyle='round,pad=0.35', fc='#fff3f3', ec='#d62728', alpha=0.95))

    ax.set_xlabel('Time (Seconds)', fontsize=11, fontweight='bold')
    ax.set_ylabel('Live BridgeHandler (WPF) processes', fontsize=11, fontweight='bold')
    ax.set_yticks([0, 1, 2]); ax.set_ylim(0, 2.4); ax.set_xlim(0, CAPTURE_WINDOW_S)
    ax.set_xticks(range(0, int(CAPTURE_WINDOW_S) + 1, 10))
    ax.set_title(
        'Measured WPF Process Re-Fire During CCC vs Stable Idle Baseline\n'
        f'{MEAS_REFIRES} respawns in {int(CAPTURE_WINDOW_S)} s  \u2502  '
        f'median re-fire period {MEAS_PERIOD_MEDIAN:.2f} s  \u2502  '
        f'median process lifetime {MEAS_LIFETIME_MED:.2f} s',
        fontsize=12, fontweight='bold')
    ax.legend(loc='upper right', frameon=True, fontsize=9, framealpha=0.95)
    ax.grid(True, which='both', linestyle='--', alpha=0.5)
    plt.tight_layout()
    plt.savefig('cpu_overhead_graph.png', dpi=300)
    plt.close()
    print(f"Saved cpu_overhead_graph.png  [MEASURED: {MEAS_REFIRES} re-fires, "
          f"median period {MEAS_PERIOD_MEDIAN:.2f}s, lifetime {MEAS_LIFETIME_MED:.2f}s]")

def plot_figure7():
    states=['Foreground\nInitialisation','Foreground\nRecovery','Background\nCCC Loop\n(small payload)','Background\nCCC Loop\n(large payload)']
    latencies=[120,250,2850,6800]; bar_cols=['#2ca02c','#1f77b4','#ff7f0e','#d62728']
    plt.figure(figsize=(9,6))
    bars=plt.bar(states,latencies,color=bar_cols,width=0.50,edgecolor='white',linewidth=1.2)
    for bar in bars:
        h=bar.get_height(); plt.text(bar.get_x()+bar.get_width()/2,h+60,f'{h:,} ms',ha='center',va='bottom',fontweight='bold',fontsize=10)
    plt.axhline(UWP_QUOTA,color='black',linestyle='--',linewidth=1.8,label=f'UWP Background Quota ~{int(UWP_QUOTA):,} ms')
    plt.axhspan(UWP_QUOTA,max(latencies)*1.20,alpha=0.07,color='#d62728',label='Failure zone \u2014 quota exceeded, CCC re-entry guaranteed')
    plt.ylabel('Connection Recovery Latency (ms)', fontsize=11, fontweight='bold')
    plt.title('AppService Connection Recovery Latency by Lifecycle State\nBackground CCC loop recovery routinely exceeds the UWP execution quota', fontsize=12, fontweight='bold')
    plt.ylim(0,max(latencies)*1.22); plt.legend(frameon=True, fontsize=9); plt.grid(True, axis='y', linestyle='--', alpha=0.6); plt.tight_layout()
    plt.savefig('recovery_latency_graph.png', dpi=300); plt.close(); print("Saved recovery_latency_graph.png")

if __name__ == '__main__':
    print("Generating figures (v6: measured re-fire replaces synthetic CPU/Phi)...")
    print("=" * 65)
    plot_figure1(); plot_figure2(); plot_figure3(); plot_figure4()
    plot_figure5(); plot_figure6(); plot_figure7()
    print("=" * 65)
    print("Done. Figure 6 is MEASURED (hardcoded re-fire timeline). No synthetic Phi emitted.")
