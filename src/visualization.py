import matplotlib.pyplot as plt
import numpy as np

from problem import EnsiaProblem

DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"]
DAY_SHORT = [d[:3] for d in DAYS]
PERIOD_TIMES = [
    "08:30",
    "10:10",
    "11:50",
    "13:30",
    "15:10",
    "16:50",
]
PERIODS = len(PERIOD_TIMES)
TOTAL_SLOTS = len(DAYS) * PERIODS

BG = "#f8f8f8"
GRID_COLOR = "#ffffff"
DAY_SEP = "#4b5563"
TITLE_COLOR = "#111827"
LABEL_COLOR = "#111827"
SUB_COLOR = "#4b5563"
ROOM_CMAP = "YlGnBu"
PROF_CMAP = "OrRd"

FONT_SMALL = {"fontsize": 9, "color": LABEL_COLOR}
FONT_AXIS = {"fontsize": 12, "color": LABEL_COLOR}
FONT_TITLE = {"fontsize": 18, "fontweight": "bold", "color": TITLE_COLOR}
FONT_TICK = {"labelsize": 10, "colors": LABEL_COLOR}


def _col_labels():
    labels = []
    for d in DAY_SHORT:
        for p in PERIOD_TIMES:
            labels.append(f"{p}")
    return labels
 
def _build_room_matrix(problem, state, use_utilization=False):
    rooms      = problem.rooms
    room_index = {r["id"]: i for i, r in enumerate(rooms)}
    matrix     = np.zeros((len(rooms), TOTAL_SLOTS), dtype=float)
 
    for eid, (rid, slot) in state.items():
        if rid not in room_index or not (0 <= slot < TOTAL_SLOTS):
            continue
        row = room_index[rid]
        if use_utilization:
            ev  = problem.events_by_id[eid]
            cap = max(1, problem.rooms_by_id[rid]["capacity"])
            matrix[row, slot] = ev["headcount"] / cap
        else:
            matrix[row, slot] += 1
 
    labels = [f"{r['name']}  ({r['capacity']})" for r in rooms]
    return matrix, labels
 
def _build_prof_matrix(problem, state):
    tids   = sorted({ev["teacher_id"] for ev in problem.events})
    t_idx  = {tid: i for i, tid in enumerate(tids)}
    matrix = np.zeros((len(tids), TOTAL_SLOTS), dtype=float)
 
    for eid, (rid, slot) in state.items():
        ev  = problem.events_by_id[eid]
        tid = ev["teacher_id"]
        if tid in t_idx and 0 <= slot < TOTAL_SLOTS:
            matrix[t_idx[tid], slot] = 1
 
    labels = [f"Teacher {tid}" for tid in tids]
    return matrix, labels
 
 
def _draw_day_separators(ax, n_slots, n_rows, periods=PERIODS):
    for d in range(1, n_slots // periods):
        x = d * periods - 0.5
        ax.axvline(x, color=DAY_SEP, linewidth=1.4, zorder=3)
 
def _draw_day_headers(ax, n_slots, periods=PERIODS):
    """Draw day name banners just above the heatmap."""
    for i, day in enumerate(DAY_SHORT):
        center = i * periods + periods / 2 - 0.5
        ax.text(center, -1.5, day, ha="center", va="center",
                fontsize=10, fontweight="bold", color=TITLE_COLOR,
                fontfamily="DejaVu Sans")
 
def _style_ax(ax):
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(axis="both", which="both", length=0)
 
 
# ── Main plot function ────────────────────────────────────────────────────────
def _plot(matrix, row_labels, title, cmap, value_label, save_path, show):
    n_rows, n_cols = matrix.shape
    cell_h = max(0.22, min(0.38, 14 / n_rows))
    fig_h  = max(7, n_rows * cell_h + 3)
    fig_w  = 22
 
    fig = plt.figure(figsize=(fig_w, fig_h), facecolor=BG)
    fig.patch.set_facecolor(BG)
 
    # Leave room at top for day headers
    ax = fig.add_axes([0.13, 0.10, 0.80, 0.78])
    ax.set_facecolor(BG)
 
    vmax = max(1.0, float(np.nanmax(matrix)))
    im   = ax.imshow(matrix, aspect="auto", cmap=cmap,
                     origin="upper", interpolation="nearest",
                     vmin=0, vmax=vmax)
 
    # Grid
    ax.set_xticks(np.arange(-0.5, n_cols, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, n_rows, 1), minor=True)
    ax.grid(which="minor", color=GRID_COLOR, linewidth=0.6, zorder=2)
    ax.tick_params(which="minor", length=0)
 
    # Day separators
    _draw_day_separators(ax, n_cols, n_rows)
 
    # X-axis: one tick per period per day
    period_ticks   = list(range(n_cols))
    period_labels  = []
    for d in range(len(DAYS)):
        for p, t in enumerate(PERIOD_TIMES):
            period_labels.append(t)
 
    ax.set_xticks(period_ticks)
    ax.set_xticklabels(period_labels, rotation=45, ha="right", **FONT_SMALL)
 
    # Y-axis
    ax.set_yticks(range(n_rows))
    ax.set_yticklabels(row_labels, **FONT_SMALL)
 
    # Day headers above plot
    _draw_day_headers(ax, n_cols)
 
    # Axis labels & title
    ax.set_xlabel("Time Period", **FONT_AXIS)
    ax.set_ylabel("Resource", **FONT_AXIS)
    ax.set_title(title, pad=28, **FONT_TITLE)
 
    _style_ax(ax)
 
    # Colorbar
    cbar_ax = fig.add_axes([0.945, 0.10, 0.013, 0.78])
    cbar    = fig.colorbar(im, cax=cbar_ax)
    cbar.set_label(value_label, fontsize=10, color=LABEL_COLOR)
    cbar.ax.tick_params(**FONT_TICK)
    cbar.outline.set_visible(False)
    cbar_ax.set_facecolor(BG)
 
    # Stats annotation
    total_cells = n_rows * n_cols
    occupied    = int(np.sum(matrix > 0))
    pct         = occupied / total_cells * 100
    fig.text(0.135, 0.02,
             f"Occupancy: {occupied}/{total_cells} slots  ({pct:.1f}%)",
             fontsize=9, color=SUB_COLOR, fontfamily="DejaVu Sans")
 
    if save_path:
        fig.savefig(save_path, dpi=180, bbox_inches="tight", facecolor=BG)
        print(f"  Saved → {save_path}")
    if show:
        plt.show()
    plt.close(fig)
 
 
#the vis func
def plot_room_occupancy_heatmap(problem, state=None, save_path=None,
                                show=True, use_utilization=False):
    state  = state if state is not None else problem.state
    matrix, labels = _build_room_matrix(problem, state, use_utilization)
    title  = "Room Occupancy Heatmap"
    vlabel = "Utilization ratio" if use_utilization else "Classes assigned"
    _plot(matrix, labels, title, ROOM_CMAP, vlabel, save_path, show)
 
 
def plot_professor_schedule_heatmap(problem, state=None, save_path=None, show=True):
    state  = state if state is not None else problem.state
    matrix, labels = _build_prof_matrix(problem, state)
    _plot(matrix, labels, "Professor Schedule Heatmap",
          PROF_CMAP, "Assigned class", save_path, show)
 
 
# excution
if __name__ == "__main__":
    print("Loading problem …")
    problem = EnsiaProblem("dataset/data_s2.json")
    print(f"  Events: {len(problem.events)}  |  Rooms: {len(problem.rooms)}")
 
    print("Plotting room occupancy heatmap …")
    plot_room_occupancy_heatmap(problem,
                                save_path="room_occupancy_heatmap.png",
                                show=False)
 
    print("Plotting room utilization heatmap …")
    plot_room_occupancy_heatmap(problem,
                                save_path="room_utilization_heatmap.png",
                                show=False,
                                use_utilization=True)
 
    print("Plotting professor schedule heatmap …")
    plot_professor_schedule_heatmap(problem,
                                    save_path="professor_schedule_heatmap.png",
                                    show=False)
 
    print("Done.")