import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
import os, io, copy, warnings
warnings.filterwarnings("ignore")

from FJSP_data import (
    PANEL_TYPES, Panneau, OrdreFabrication, Statut,
    get_duree_avec_manutention, get_duree_totale_theorique,
    get_route, get_machines_disponibles, get_temps,
    prochain_debut_shift, TEMPS_MANUTENTION,
    MACHINE_VERS_POSTE, MACHINES_PAR_POSTE,
)
from FJSP_env import (
    FJSPEnv, N_MACHINES, ALL_MACHINES, FENETRE_ACTIVE,
    CAPACITE_STOCK_STANDBY, HORIZON,
)
# =============================================================================
# 0. CONFIG PAGE
# =============================================================================

st.set_page_config(
    page_title="FJSP Scheduler — Bombardier",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded",
)

NAVY   = "#0B1E3D"   # Ink — primary structural colour, headers & titles
CYAN   = "#0077C8"   # Aerospace Blue — primary accent / action
WHITE  = "#FFFFFF"
LGRAY  = "#F3F5F8"   # Cloud — page background
MGRAY  = "#DBE1EA"   # Hairline — borders & dividers
DGRAY  = "#5B6B82"   # Slate — secondary text
RED    = "#C8333B"   # Stop — critical / late
GREEN  = "#1E9E6A"   # Go — on-time / nominal
ORANGE = "#D98B2B"   # Signal Amber — caution

st.markdown(f"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root {{
    --ink: {NAVY}; --blue: {CYAN}; --cloud: {LGRAY}; --hairline: {MGRAY};
    --slate: {DGRAY}; --stop: {RED}; --go: {GREEN}; --amber: {ORANGE};
}}
html, body, [class*="css"] {{
    font-family: 'IBM Plex Sans', 'Segoe UI', Arial, sans-serif;
    background: linear-gradient(135deg, {LGRAY} 0%, #EEF2F7 100%);
    color: #16213E;
}}
/* Hero section — hero is thesis: the workshop flow */
.hero-workshop {{
    background: linear-gradient(110deg, {NAVY} 0%, #0E3F66 50%, {CYAN} 100%);
    padding: 32px; border-radius: 8px; margin-bottom: 28px;
    position: relative; overflow: hidden;
    box-shadow: 0 12px 32px rgba(11,30,61,0.22);
}}
.hero-workshop::before {{
    content:""; position: absolute; inset: 0;
    background-image: 
        radial-gradient(circle at 20% 80%, rgba(0,119,200,0.08) 0%, transparent 50%),
        radial-gradient(circle at 80% 20%, rgba(30,158,106,0.06) 0%, transparent 50%);
    pointer-events: none;
}}
.hero-workshop-title {{
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.3rem; font-weight: 600; color: {WHITE};
    margin: 0 0 6px; letter-spacing: -0.01em; position: relative; z-index: 1;
}}
.hero-workshop-subtitle {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.78rem; color: rgba(255,255,255,0.65);
    margin: 0; letter-spacing: 0.05em; position: relative; z-index: 1;
}}
.workshop-svg {{
    width: 100%; height: auto; margin-top: 16px; position: relative; z-index: 1;
}}
/* faint blueprint grid — signature texture, evokes engineering drawings */
[data-testid="stAppViewContainer"] > .main {{
    background-image:
        repeating-linear-gradient(0deg, rgba(11,30,61,0.025) 0px, rgba(11,30,61,0.025) 1px, transparent 1px, transparent 26px),
        repeating-linear-gradient(90deg, rgba(11,30,61,0.025) 0px, rgba(11,30,61,0.025) 1px, transparent 1px, transparent 26px);
}}
h1, h2, h3, .aa-header-title, .aa-section {{
    font-family: 'Space Grotesk', 'IBM Plex Sans', sans-serif;
}}
code, .stCode, [data-testid="stMetricValue"] {{
    font-family: 'IBM Plex Mono', monospace !important;
}}
[data-testid="stSidebar"] {{
    background: linear-gradient(180deg, {NAVY} 0%, #050F22 100%);
    border-right: 1px solid rgba(255,255,255,0.08);
}}
[data-testid="stSidebar"] * {{ color: {WHITE} !important; font-family:'IBM Plex Sans', sans-serif; }}
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stDateInput label,
[data-testid="stSidebar"] .stTimeInput label {{
    color: rgba(255,255,255,0.55) !important; font-size: 0.78rem;
}}
.aa-header {{
    position: relative; overflow: hidden;
    background: linear-gradient(120deg, {NAVY} 0%, #102A52 55%, #0E3F66 100%);
    padding: 22px 32px; border-radius: 6px; margin-bottom: 26px;
    border-left: 4px solid {CYAN};
    box-shadow: 0 8px 24px rgba(11,30,61,0.18);
}}
.aa-header::after {{
    content:""; position:absolute; inset:0;
    background-image: repeating-linear-gradient(
        90deg, rgba(255,255,255,0.05) 0px, rgba(255,255,255,0.05) 1px,
        transparent 1px, transparent 64px);
    pointer-events:none;
}}
.aa-header-title {{ font-size:1.55rem; font-weight:600; color:{WHITE}; margin:0;
    letter-spacing:-0.01em; position:relative; }}
.aa-header-sub {{ font-size:0.85rem; color:rgba(255,255,255,0.68); margin:6px 0 0;
    font-family:'IBM Plex Mono', monospace; position:relative; }}
/* KPI cards as instrumentation gauges */
.aa-card {{
    background:{WHITE}; border-radius:8px; padding:18px 22px;
    border:1px solid {MGRAY}; margin-bottom:16px;
    box-shadow:0 1px 3px rgba(11,30,61,0.06);
    position: relative;
}}
.aa-card::before {{
    content: ""; position: absolute; inset: 0;
    background-image: radial-gradient(circle at top right, rgba(0,119,200,0.03) 0%, transparent 70%);
    border-radius: 8px; pointer-events: none;
}}
.aa-card-title {{ font-size:0.72rem; font-weight:600; color:{DGRAY};
    text-transform:uppercase; letter-spacing:0.09em; margin-bottom:8px;
    font-family:'IBM Plex Mono', monospace; }}
.aa-card-value {{ font-size:2.4rem; font-weight:600; color:{NAVY};
    font-family:'Space Grotesk', sans-serif; line-height: 1; }}
.aa-card-sub {{ font-size:0.8rem; color:{DGRAY}; margin-top:4px; }}
.aa-card-accent {{ border-top:3px solid {CYAN}; }}
.aa-card-ok     {{ border-top:3px solid {GREEN}; }}
.aa-card-warn   {{ border-top:3px solid {ORANGE}; }}
.aa-card-danger {{ border-top:3px solid {RED}; }}
.aa-section {{
    font-size:0.92rem; font-weight:600; color:{NAVY};
    border-left:3px solid {CYAN}; padding-left:12px; margin:22px 0 14px;
    text-transform:uppercase; letter-spacing:0.04em;
}}
/* Route stepper — signature element */
.route-flow {{ display:flex; align-items:center; flex-wrap:wrap; margin:6px 0; gap: 4px; }}
.route-step {{
    display:inline-flex; align-items:center; gap:5px;
    padding:4px 10px 4px 8px; font-size:0.74rem; font-weight:600;
    font-family:'IBM Plex Mono', monospace; letter-spacing:0.01em;
    border-radius:3px;
}}
.route-step::before {{ content:""; width:7px; height:7px; flex:none; }}
.route-done {{ background:#E9F6F0; color:#147A52; border:1px solid #B9E3CE; }}
.route-done::before {{ background:{GREEN}; border-radius:50%; }}
.route-current {{ background:{NAVY}; color:{WHITE}; border: 1px solid {CYAN}; }}
.route-current::before {{ background:{CYAN}; }}
.route-todo {{ background:{WHITE}; color:{DGRAY}; border:1px dashed {MGRAY}; }}
.route-todo::before {{ background:{WHITE}; border:1.5px solid {MGRAY}; border-radius:50%; }}
.route-connector {{ color:{MGRAY}; margin:0 1px; font-family:'IBM Plex Mono', monospace; font-weight: 500; }}
.stButton > button[kind="primary"] {{
    background: {NAVY} !important;
    color:{WHITE} !important; border:none !important;
    border-radius:5px !important; font-weight:600 !important;
    font-family:'IBM Plex Sans', sans-serif !important;
    letter-spacing:0.01em;
}}
.stButton > button[kind="primary"]:hover {{
    background: {CYAN} !important;
}}
hr {{ border-color:{MGRAY} !important; margin:16px 0 !important; }}
</style>
""", unsafe_allow_html=True)

# =============================================================================
# 1. CONSTANTES
# =============================================================================

MODEL_PATH  = "best_model.zip"
T_REFERENCE = datetime(2026, 1, 1, 0, 0)

COULEURS_TYPE = {
    "Sup AV": "#0077C8", "Sup AR": "#0B1E3D",
    "Inf AV": "#C8333B", "Ar D":   "#1E9E6A",
    "Ar G":   "#D98B2B", "Av D":   "#6B4FA0", "Av G": "#147A7A",
}

# =============================================================================
# 2. UTILITAIRES TEMPS — temps linéaire
# =============================================================================

def h_to_dt(h: float) -> datetime:
    return T_REFERENCE + timedelta(hours=float(h))

def dt_to_h(dt: datetime) -> float:
    return max(0.0, (dt - T_REFERENCE).total_seconds() / 3600)

def h_to_str(h: float) -> str:
    return h_to_dt(h).strftime("%d/%m/%Y %H:%M")

# --- Shifts 14h/jour (ex : 6h→20h) -----------------------------------------
SHIFT_START = 6   # heure de début shift (heure locale)
SHIFT_HEURES = 14  # heures effectives par jour

def h_shift_to_dt(h_lineaire: float) -> datetime:
    """Convertit des heures cumulées linéaires en datetime réel avec shifts 14h/jour.

    Ex : h=15 → jour 2, heure 6h + (15-14)h = 7h  (car jour 1 = 14h de 6h à 20h)
    Une opération qui chevauche la fin du shift est interrompue et reprend le lendemain.
    """
    h = float(h_lineaire)
    jours_complets = int(h // SHIFT_HEURES)
    h_restantes    = h % SHIFT_HEURES
    dt_debut_shift = (T_REFERENCE.replace(hour=SHIFT_START, minute=0, second=0)
                      + timedelta(days=jours_complets))
    return dt_debut_shift + timedelta(hours=h_restantes)

def _split_op_shifts(debut_h: float, fin_h: float):
    """Découpe un intervalle [debut_h, fin_h] (heures linéaires) en segments
    correspondant aux plages de shift réelles.  Retourne une liste de
    (debut_dt, fin_dt) pour chaque segment (jamais plus long qu'un shift).
    """
    segments = []
    t = debut_h
    while t < fin_h - 1e-6:
        # Fin du shift courant en heures linéaires
        fin_shift = (int(t // SHIFT_HEURES) + 1) * SHIFT_HEURES
        t_end = min(fin_h, fin_shift)
        segments.append((h_shift_to_dt(t), h_shift_to_dt(t_end)))
        t = fin_shift  # début du prochain shift = même que fin shift courant
    return segments

# =============================================================================
# 3. ROUTE VISUELLE — [I4]
# =============================================================================

def _render_route_html(panneau: Panneau) -> str:
    """Génère la gamme sous forme de stepper process-flow
    (fait / en cours / à faire) — diagramme inspiré des plans de gamme."""
    route  = panneau.route
    op_cur = panneau.op_courante
    html   = '<div class="route-flow">'
    for i, poste in enumerate(route):
        if i < op_cur:
            css = "route-done"
        elif i == op_cur:
            css = "route-current"
        else:
            css = "route-todo"
        html += f'<span class="route-step {css}">{poste}</span>'
        if i < len(route) - 1:
            html += '<span class="route-connector">┄┄&gt;</span>'
    html += '</div>'
    return html

# =============================================================================
# 4. MODÈLE PPO
# =============================================================================

@st.cache_resource
def charger_modele():
    if os.path.exists(MODEL_PATH):
        try:
            from sb3_contrib import MaskablePPO
            return MaskablePPO.load(MODEL_PATH), "PPO"
        except Exception:
            pass
    return None, "EDD"

# =============================================================================
# 5. ORDONNANCEMENT
# =============================================================================

def ordonnancer(panneaux, t_actuel, modele=None, mode="EDD"):
    env = FJSPEnv(n_panneaux=len(panneaux))
    env.initialiser_etat_reel(panneaux, t_actuel)

    done      = False
    steps     = 0
    MAX_STEPS = 10_000
    mod       = modele if mode == "PPO" else None
    n_total   = len(panneaux)

    progress = st.progress(0, text="Initialisation...")

    while not done and steps < MAX_STEPS:
        steps += 1
        done, info = env.step_parallel(mod)
        if steps % 200 == 0:
            n_done = info.get("pan_termines", 0)
            pct    = min(int(n_done / max(n_total, 1) * 100), 99)
            progress.progress(pct,
                text=f"Itération {steps} — {n_done}/{n_total} terminés "
                     f"— t={info.get('t', 0):.0f}h")

    progress.progress(100, text="Calcul terminé ✓")
    progress.empty()

    df       = env.get_planning_df()
    termines = [p for p in env.tous_les_panneaux
                if p.statut == Statut.TERMINE and p.historique]
    makespan = float(df["fin"].max()) if df is not None and not df.empty else 0.0
    n_ok     = sum(1 for p in termines
                   if p.historique[-1]["fin"] <= p.due_date)
    retards  = [max(0.0, p.historique[-1]["fin"] - p.due_date) for p in termines]

    metriques = {
        "makespan"    : makespan,
        "taux_ok"     : n_ok / len(termines) if termines else 0,
        "n_ok"        : n_ok,
        "n_total"     : len(termines),
        "retard_moyen": float(np.mean(retards)) if retards else 0.0,
        "n_steps"     : steps,
        "mode"        : mode,
    }
    return df, metriques, env

# =============================================================================
# 6. GANTT
# =============================================================================

def _get_unite_stars(df: pd.DataFrame, panneaux: list, mode_axe: str):
    """Calcule les annotations étoiles ⭐ à placer dans le Gantt.

    Une étoile est placée sur la machine du dernier panneau terminé de chaque
    groupe de 7 (une unité = 7 types).  La position X correspond à la fin
    maximale du groupe, la position Y à la machine correspondante.

    Retourne une liste de dicts {x, y, label, mode} prêts à injecter via
    fig.add_annotation().
    """
    if df is None or df.empty or not panneaux:
        return []

    # Identifier l'OF de base de chaque panneau pour regrouper par unité.
    # Convention : on regroupe par séquence d'entrée (ordre d'ajout),
    # lots de 7 panneaux consécutifs.
    mgh_ids = [p.mgh_id for p in panneaux]
    stars = []

    for lot_start in range(0, len(mgh_ids), 7):
        lot = mgh_ids[lot_start: lot_start + 7]
        if len(lot) < 7:
            break  # lot incomplet → pas d'étoile

        df_lot = df[df["MGH"].isin(lot)]
        if df_lot.empty:
            continue

        fin_max = df_lot["fin"].max()
        row_max = df_lot[df_lot["fin"] == fin_max].iloc[0]
        machine = row_max["machine"]
        n_unite = lot_start // 7 + 1

        if mode_axe == "datetime":
            x_val = h_to_dt(fin_max)
        elif mode_axe == "shifts":
            x_val = h_shift_to_dt(fin_max)
        else:  # heures
            x_val = fin_max

        stars.append({
            "x"    : x_val,
            "y"    : machine,
            "label": f"⭐ U{n_unite}",
            "mode" : mode_axe,
        })

    return stars


def _add_unite_stars(fig: go.Figure, stars: list):
    """Injecte les annotations étoile dans une figure Plotly."""
    for s in stars:
        fig.add_annotation(
            x=s["x"], y=s["y"],
            text=s["label"],
            showarrow=True,
            arrowhead=2, arrowsize=1, arrowwidth=1.5,
            arrowcolor="#C9A646",
            font=dict(size=14, color="#C9A646"),
            bgcolor="rgba(0,0,0,0.55)",
            bordercolor="#C9A646",
            borderwidth=1,
            borderpad=3,
            ax=0, ay=-30,
            xanchor="center",
            yanchor="bottom",
        )


def creer_gantt(df: pd.DataFrame, panneaux: list,
                mode_axe: str = "datetime") -> go.Figure:
    if df is None or df.empty:
        return go.Figure()

    df = df.copy()

    # ------------------------------------------------------------------ SHIFTS
    if mode_axe == "shifts":
        fig = go.Figure()
        machines_ordre = list(reversed(ALL_MACHINES))
        m_to_y = {m: i for i, m in enumerate(machines_ordre)}
        t_now = st.session_state.get("t_actuel", 0.0)

        for _, row in df.iterrows():
            y_pos   = m_to_y.get(row["machine"], 0)
            couleur = COULEURS_TYPE.get(row["type_panneau"], "#888")
            segments = _split_op_shifts(row["debut"], row["fin"])

            for seg_idx, (seg_start_dt, seg_end_dt) in enumerate(segments):
                opacity = 0.4 if row["interrompu"] else 0.85
                # Barre du segment
                fig.add_trace(go.Bar(
                    x=[(seg_end_dt - seg_start_dt).total_seconds() / 3600],
                    y=[row["machine"]],
                    base=[seg_start_dt.isoformat()],
                    orientation="h",
                    marker_color=couleur,
                    opacity=opacity,
                    width=0.7,
                    showlegend=(seg_idx == 0 and
                                row["type_panneau"] not in
                                [t.name for t in fig.data if hasattr(t, "name")]),
                    name=row["type_panneau"],
                    legendgroup=row["type_panneau"],
                    hovertemplate=(
                        f"<b>{row['MGH']}</b><br>"
                        f"Poste : {row['poste']}<br>"
                        f"Machine : {row['machine']}<br>"
                        f"Début : {seg_start_dt.strftime('%d/%m %H:%M')}<br>"
                        f"Fin : {seg_end_dt.strftime('%d/%m %H:%M')}<br>"
                        + ("⚠️ Interrompu<br>" if row["interrompu"] else "")
                        + "<extra></extra>"
                    ),
                ))
                # Étiquette MGH sur le plus grand segment
                dur_h = (seg_end_dt - seg_start_dt).total_seconds() / 3600
                if dur_h > 3:
                    mid_dt = seg_start_dt + (seg_end_dt - seg_start_dt) / 2
                    fig.add_annotation(
                        x=mid_dt, y=row["machine"],
                        text=row["MGH"], showarrow=False,
                        font=dict(size=8, color="white"),
                        xanchor="center", yanchor="middle")

                # Hachures visuelles pour indiquer la coupure de shift
                if len(segments) > 1 and seg_idx < len(segments) - 1:
                    fig.add_annotation(
                        x=seg_end_dt, y=row["machine"],
                        text="✂️", showarrow=False,
                        font=dict(size=10), yanchor="middle",
                        xanchor="center")

        # Ligne Maintenant
        if t_now > 0:
            x_now = h_shift_to_dt(t_now)
            fig.add_shape(type="line", x0=x_now, x1=x_now, y0=0, y1=1,
                          xref="x", yref="paper",
                          line=dict(color="#D98B2B", width=2.5))
            fig.add_annotation(x=x_now, y=1.04, xref="x", yref="paper",
                               text="▼ Maintenant", showarrow=False,
                               font=dict(size=10, color="#D98B2B"), xanchor="center")

        # Due dates
        vues = set()
        for p in panneaux:
            if p.due_date not in vues:
                vues.add(p.due_date)
                x_dt = h_shift_to_dt(p.due_date)
                fig.add_shape(type="line", x0=x_dt, x1=x_dt, y0=0, y1=1,
                              xref="x", yref="paper",
                              line=dict(color=RED, width=1.5, dash="dot"), opacity=0.85)
                fig.add_annotation(x=x_dt, y=1.02, xref="x", yref="paper",
                                   text=f"↓ {p.mgh_id}", showarrow=False,
                                   font=dict(size=9, color=RED), xanchor="left")

        # Zones hors-shift (grisées) — un rectangle par jour visible
        if not df.empty:
            max_h = float(df["fin"].max())
            n_jours = int(max_h // SHIFT_HEURES) + 2
            for j in range(n_jours):
                fin_shift_dt  = (T_REFERENCE.replace(hour=SHIFT_START + SHIFT_HEURES,
                                  minute=0, second=0) + timedelta(days=j))
                deb_shift_dt  = (T_REFERENCE.replace(hour=SHIFT_START, minute=0, second=0)
                                  + timedelta(days=j + 1))
                fig.add_vrect(x0=fin_shift_dt, x1=deb_shift_dt,
                              fillcolor=MGRAY, opacity=0.18,
                              layer="below", line_width=0)

        fig.update_yaxes(
            categoryorder="array",
            categoryarray=list(reversed(ALL_MACHINES)),
            title="Bâti / Machine",
            tickfont=dict(size=11, color=NAVY),
        )
        x_axis = dict(
            type="date",
            showgrid=True, gridcolor=MGRAY,
            title=f"Calendrier réel (shift {SHIFT_START}h–{SHIFT_START+SHIFT_HEURES}h "
                  f"= {SHIFT_HEURES}h/jour)",
            tickformat="%d/%m\n%H:%M",
        )
        fig.update_layout(
            barmode="overlay",
            height=max(550, len(ALL_MACHINES) * 26),
            plot_bgcolor=WHITE, paper_bgcolor=WHITE,
            font=dict(family="IBM Plex Sans, Arial", size=12, color=NAVY),
            xaxis=x_axis,
            legend=dict(title=dict(text="Type panneau"),
                        bgcolor="rgba(255,255,255,0.9)",
                        bordercolor=MGRAY, borderwidth=1),
            margin=dict(l=10, r=10, t=40, b=10),
        )
        _add_unite_stars(fig, _get_unite_stars(df, panneaux, "shifts"))
        return fig

    # ---------------------------------------------------------- DATETIME (continu)
    if mode_axe == "datetime":
        df["debut_dt"] = df["debut"].apply(h_to_dt)
        df["fin_dt"]   = df["fin"].apply(h_to_dt)

        fig = px.timeline(
            df,
            x_start   = "debut_dt",
            x_end     = "fin_dt",
            y         = "machine",
            color     = "type_panneau",
            color_discrete_map = COULEURS_TYPE,
            hover_data = ["MGH", "OF", "poste", "interrompu", "en_retard"],
            labels    = {"type_panneau": "Type panneau", "machine": "Machine"},
        )
        fig.update_yaxes(categoryorder="array",
                         categoryarray=list(reversed(ALL_MACHINES)))

        # Ligne Maintenant
        t_now = st.session_state.get("t_actuel", 0.0)
        if t_now > 0:
            x_now = h_to_dt(t_now)
            fig.add_shape(type="line", x0=x_now, x1=x_now, y0=0, y1=1,
                          xref="x", yref="paper",
                          line=dict(color="#D98B2B", width=2.5))
            fig.add_annotation(x=x_now, y=1.04, xref="x", yref="paper",
                               text="▼ Maintenant", showarrow=False,
                               font=dict(size=10, color="#D98B2B"), xanchor="center")

        # Due dates
        vues = set()
        for p in panneaux:
            if p.due_date not in vues:
                vues.add(p.due_date)
                x_dt = h_to_dt(p.due_date)
                fig.add_shape(type="line", x0=x_dt, x1=x_dt, y0=0, y1=1,
                              xref="x", yref="paper",
                              line=dict(color=RED, width=1.5, dash="dot"), opacity=0.85)
                fig.add_annotation(x=x_dt, y=1.02, xref="x", yref="paper",
                                   text=f"↓ {p.mgh_id}", showarrow=False,
                                   font=dict(size=9, color=RED), xanchor="left")

        # Opérations interrompues
        for _, row in df[df["interrompu"] == True].iterrows():
            mid_dt = row["debut_dt"] + (row["fin_dt"] - row["debut_dt"]) / 2
            fig.add_annotation(x=mid_dt, y=row["machine"], text="⚠️",
                               showarrow=False, font=dict(size=14), yanchor="middle")

        x_axis = dict(showgrid=True, gridcolor=MGRAY, title="Date (temps continu)")

    # ---------------------------------------------------------- HEURES CUMULÉES
    else:
        fig            = go.Figure()
        machines_ordre = list(reversed(ALL_MACHINES))
        m_to_y         = {m: i for i, m in enumerate(machines_ordre)}

        for _, row in df.iterrows():
            y_pos   = m_to_y.get(row["machine"], 0)
            couleur = COULEURS_TYPE.get(row["type_panneau"], "#888")
            fig.add_shape(type="rect",
                          x0=row["debut"], x1=row["fin"],
                          y0=y_pos - 0.4, y1=y_pos + 0.4,
                          fillcolor=couleur,
                          line=dict(color="white", width=0.5),
                          opacity=0.85 if not row["interrompu"] else 0.4)
            if row["fin"] - row["debut"] > 10:
                fig.add_annotation(x=(row["debut"] + row["fin"]) / 2, y=y_pos,
                                   text=row["MGH"], showarrow=False,
                                   font=dict(size=8, color="white"),
                                   xanchor="center", yanchor="middle")

        vues = set()
        for p in panneaux:
            if p.due_date not in vues:
                vues.add(p.due_date)
                fig.add_shape(type="line",
                              x0=p.due_date, x1=p.due_date,
                              y0=-0.5, y1=len(machines_ordre) - 0.5,
                              line=dict(color=RED, width=1.5, dash="dot"), opacity=0.85)
                fig.add_annotation(x=p.due_date, y=len(machines_ordre) - 0.5,
                                   text=f"↓ {p.mgh_id}", showarrow=False,
                                   font=dict(size=9, color=RED), xanchor="left")

        fig.update_yaxes(tickmode="array",
                         tickvals=list(range(len(machines_ordre))),
                         ticktext=machines_ordre)
        x_axis = dict(showgrid=True, gridcolor=MGRAY, title="Heures cumulées (h)")

    fig.update_layout(
        height       = max(550, len(ALL_MACHINES) * 26),
        plot_bgcolor = WHITE, paper_bgcolor = WHITE,
        font         = dict(family="IBM Plex Sans, Arial", size=12, color=NAVY),
        xaxis        = x_axis,
        yaxis        = dict(title="Bâti / Machine", tickfont=dict(size=11, color=NAVY)),
        legend       = dict(title=dict(text="Type panneau"),
                            bgcolor="rgba(255,255,255,0.9)",
                            bordercolor=MGRAY, borderwidth=1),
        margin       = dict(l=10, r=10, t=40, b=10),
    )
    # Étoiles ⭐ — fin de chaque lot de 7 panneaux (une unité complète)
    _add_unite_stars(fig, _get_unite_stars(df, panneaux, mode_axe))
    return fig

# =============================================================================
# 7. EXPORT EXCEL
# =============================================================================

def exporter_excel(df: pd.DataFrame, panneaux: list) -> bytes:
    buf     = io.BytesIO()
    due_map = {p.mgh_id: p.due_date for p in panneaux}
    of_map  = {p.mgh_id: p.of_id    for p in panneaux}

    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df_exp = df.copy()
        df_exp["OF"]        = df_exp["MGH"].map(of_map).fillna("—")
        df_exp["Début"]     = df_exp["debut"].apply(h_to_str)
        df_exp["Fin"]       = df_exp["fin"].apply(h_to_str)
        df_exp["Manut."]    = df_exp["fin_manut"].apply(h_to_str)
        df_exp["Servitude"] = df_exp["MGH"].map(due_map).apply(
            lambda h: h_to_str(h) if h else "—")
        df_exp["En retard"] = df_exp.apply(
            lambda r: "⚠️ Retard" if (due_map.get(r["MGH"], 9999) < r["fin"])
                      else "✓", axis=1)

        cols = ["MGH", "OF", "type_panneau", "poste", "machine",
                "Début", "Fin", "Manut.", "Servitude", "interrompu", "En retard"]
        df_exp[cols].rename(columns={
            "type_panneau": "Type panneau", "interrompu": "Interrompu"
        }).to_excel(writer, sheet_name="Planning", index=False)

        resume = []
        for p in panneaux:
            fin_r = p.historique[-1]["fin"] \
                    if p.statut == Statut.TERMINE and p.historique else None
            resume.append({
                "MGH"          : p.mgh_id,
                "OF"           : p.of_id,
                "Type"         : p.panel_type,
                "Statut"       : p.statut.value,
                "Dispo matière": h_to_str(p.release_date),
                "Servitude"    : h_to_str(p.due_date),
                "Route"        : " → ".join(get_route(p.panel_type)),
                "Fin réelle"   : h_to_str(fin_r) if fin_r else "—",
                "Retard (h)"   : round(max(0.0, fin_r - p.due_date), 1) if fin_r else "—",
                "Livraison"    : ("✓ À temps" if fin_r and fin_r <= p.due_date
                                  else ("⚠ Retard" if fin_r else "En cours")),
            })
        pd.DataFrame(resume).to_excel(
            writer, sheet_name="Résumé panneaux", index=False)

    return buf.getvalue()

# =============================================================================
# 8. SESSION STATE
# =============================================================================

def init_session():
    defaults = {
        "panneaux"   : [],
        "planning_df": None,
        "metriques"  : None,
        "env"        : None,
        "mgh_counter": 10000,
        "of_counter" : 0,
        "t_actuel"   : 0.0,   # [I7] t=0 au démarrage
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

def new_mgh():
    st.session_state.mgh_counter += 1
    return f"MGH{st.session_state.mgh_counter}"

def new_of():
    st.session_state.of_counter += 1
    return f"OF-{st.session_state.of_counter:03d}"

# =============================================================================
# 9. SIDEBAR
# =============================================================================

init_session()
modele, mode = charger_modele()

with st.sidebar:
    import base64, os as _os

    def _load_img_b64(filename: str):
        for folder in [
            _os.getcwd(),
            _os.path.dirname(_os.path.abspath(__file__)) if "__file__" in dir() else _os.getcwd(),
        ]:
            path = _os.path.join(folder, filename)
            if _os.path.exists(path):
                with open(path, "rb") as f:
                    return base64.b64encode(f.read()).decode()
        return None

    logo_aa = _load_img_b64("airbus_atlantic.png")
    img_g75 = _load_img_b64("bombardier_g7500.png")

    logo_html = '<div style="display:flex;align-items:center;justify-content:center;gap:12px;padding:10px 0 6px">'
    if logo_aa:
        logo_html += f'<img src="data:image/png;base64,{logo_aa}" style="height:38px;object-fit:contain">'
    else:
        logo_html += f'<span style="color:{CYAN};font-size:0.7rem;font-weight:700">AIRBUS<br>ATLANTIC</span>'
    logo_html += '<div style="width:1px;height:32px;background:rgba(255,255,255,0.2)"></div>'
    if img_g75:
        logo_html += f'<img src="data:image/png;base64,{img_g75}" style="height:38px;object-fit:contain">'
    else:
        logo_html += f'<span style="color:{WHITE};font-size:0.7rem;font-weight:700">BOMBARDIER<br>G7500</span>'
    logo_html += '</div>'
    st.markdown(logo_html, unsafe_allow_html=True)

    st.markdown(
        f'<div style="text-align:center;padding:4px 0 8px">'
        f'<p style="color:{WHITE};font-size:1.0rem;font-weight:600;margin:0;'
        f'font-family:\'Space Grotesk\',sans-serif">✈️ BOMBARDIER</p>'
        f'<p style="color:{CYAN};font-size:0.68rem;letter-spacing:0.16em;'
        f'text-transform:uppercase;margin:4px 0 0;'
        f'font-family:\'IBM Plex Mono\',monospace">FJSP Scheduler</p>'
        f'</div>', unsafe_allow_html=True)
    st.divider()

    # Mode agent — badge instrumentation (accent gauche, coins carrés)
    if mode == "PPO":
        st.markdown(
            f'<div style="background:rgba(30,158,106,0.16);color:{WHITE};'
            f'border-left:3px solid {GREEN};border-radius:3px;'
            f'padding:7px 12px;font-weight:600;font-size:0.82rem;'
            f'font-family:\'IBM Plex Mono\',monospace;letter-spacing:0.02em">'
            f'AGENT PPO — ACTIF</div>',
            unsafe_allow_html=True)
    else:
        st.markdown(
            f'<div style="background:rgba(0,119,200,0.16);color:{WHITE};'
            f'border-left:3px solid {CYAN};border-radius:3px;'
            f'padding:7px 12px;font-weight:600;font-size:0.82rem;'
            f'font-family:\'IBM Plex Mono\',monospace;letter-spacing:0.02em">'
            f'MODE EDD — FALLBACK</div>',
            unsafe_allow_html=True)
        st.caption(f"Modèle attendu :\n`{MODEL_PATH}`")

    st.divider()

    # Heure courante
    st.markdown(
        f'<p style="color:rgba(255,255,255,0.55);font-size:0.72rem;font-weight:600;'
        f'text-transform:uppercase;letter-spacing:0.1em;'
        f'font-family:\'IBM Plex Mono\',monospace">Heure courante</p>',
        unsafe_allow_html=True)
    d_sel  = st.date_input("Date", value=T_REFERENCE.date(), label_visibility="collapsed")
    h_sel  = st.time_input("Heure",
                            value=datetime.strptime("00:00", "%H:%M").time(),
                            label_visibility="collapsed")
    dt_sel = datetime.combine(d_sel, h_sel)
    st.session_state.t_actuel = max(0.0, dt_to_h(dt_sel))
    st.caption(f"t absolu = {st.session_state.t_actuel:.1f}h")

    st.divider()

    n_pan = len(st.session_state.panneaux)
    n_enc = sum(1 for p in st.session_state.panneaux if p.statut == Statut.EN_COURS)
    n_std = sum(1 for p in st.session_state.panneaux if p.statut == Statut.STANDBY)

    # [I3] Jauge stock STANDBY
    stock_pct  = n_std / CAPACITE_STOCK_STANDBY
    stock_color = RED if n_std >= CAPACITE_STOCK_STANDBY else \
                  ORANGE if stock_pct >= 0.7 else GREEN
    st.markdown(
        f'<div style="color:rgba(255,255,255,0.55);font-size:0.8rem;'
        f'font-family:\'IBM Plex Mono\',monospace">'
        f'PANNEAUX &nbsp;<b style="color:{WHITE}">{n_pan}</b><br>'
        f'EN COURS &nbsp;<b style="color:{WHITE}">{n_enc}</b> &nbsp;&nbsp;'
        f'STANDBY &nbsp;<b style="color:{WHITE}">{n_std}</b></div>',
        unsafe_allow_html=True)
    st.markdown(
        f'<div style="margin-top:8px">'
        f'<div style="font-size:0.68rem;color:rgba(255,255,255,0.45);'
        f'font-family:\'IBM Plex Mono\',monospace;letter-spacing:0.06em">'
        f'STOCK STANDBY</div>'
        f'<div style="background:rgba(255,255,255,0.1);border-radius:3px;'
        f'height:8px;margin-top:4px">'
        f'<div style="background:{stock_color};width:{min(stock_pct*100,100):.0f}%;'
        f'height:8px;border-radius:3px"></div></div>'
        f'<div style="font-size:0.7rem;color:{stock_color};margin-top:3px;'
        f'font-family:\'IBM Plex Mono\',monospace">'
        f'{n_std} / {CAPACITE_STOCK_STANDBY}</div></div>',
        unsafe_allow_html=True)
    st.divider()
    st.markdown(
        f'<p style="color:rgba(255,255,255,0.3);font-size:0.7rem;text-align:center">'
        f'© 2026 Bombardier — PFE FJSP</p>',
        unsafe_allow_html=True)

# =============================================================================
# 10. HELPER FILE DE PRODUCTION
# =============================================================================

def _render_file_production(key_suffix: str = ""):
    st.markdown('<div class="aa-section">File de production</div>',
                unsafe_allow_html=True)

    if not st.session_state.panneaux:
        st.info("Aucun panneau. Utilisez le formulaire.")
        return

    rows = []
    for p in st.session_state.panneaux:
        d       = get_duree_avec_manutention(p.panel_type)
        fenetre = p.due_date - p.release_date

        poste_courant   = "—"
        machine_courant = "—"
        avancement_pct  = "—"
        prochaine_op    = "—"

        if p.statut == Statut.EN_COURS and p.machine_assignee:
            machine_courant = p.machine_assignee
            poste_courant   = MACHINE_VERS_POSTE.get(p.machine_assignee, "—")
            avanc_declare   = getattr(p, "avancement_declare", None)
            if p.debut_op is not None and p.fin_op is not None:
                duree_op = p.fin_op - p.debut_op
                if duree_op > 0:
                    elapsed     = max(0.0, st.session_state.t_actuel - p.debut_op)
                    avanc_calc  = min(1.0, elapsed / duree_op)
                    avanc_final = max(avanc_declare or 0.0, avanc_calc)
                    avancement_pct = f"{avanc_final*100:.0f}%"
            elif avanc_declare is not None:
                avancement_pct = f"{avanc_declare*100:.0f}%"
            # [I5] Prochaine op
            if p.op_courante + 1 < len(p.route):
                prochaine_op = p.route[p.op_courante + 1]

        elif p.statut == Statut.STANDBY:
            meta = getattr(p, "meta", {})
            pct  = meta.get("avancement_pct")
            if pct is not None:
                avancement_pct  = f"{pct}%"
                machine_courant = meta.get("dernier_poste", "—")
                poste_courant   = MACHINE_VERS_POSTE.get(machine_courant, "—")
            if p.op_courante < len(p.route):
                prochaine_op = p.route[p.op_courante]

        rows.append({
            "MGH"          : p.mgh_id,
            "OF"           : p.of_id,
            "Type"         : p.panel_type,
            "Statut"       : p.statut.value,
            "Poste"        : poste_courant,
            "Machine"      : machine_courant,
            "Avancement"   : avancement_pct,
            "Prochaine op.": prochaine_op,       # [I5]
            "Dispo mat."   : h_to_str(p.release_date),
            "Servitude"    : h_to_str(p.due_date),
            "Durée th."    : f"{d:.0f}h",
            "Facteur"      : f"{fenetre/d:.2f}x" if d > 0 else "—",
            "Risque"       : "⚠️" if d > 0 and fenetre/d < 1.5 else "✓",
        })

    df_file = pd.DataFrame(rows)
    st.dataframe(df_file, use_container_width=True, height=340)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("🗑️ Vider la file",
                     key=f"vider_file_{key_suffix}", width="stretch"):
            for k in ["panneaux", "planning_df", "metriques", "env"]:
                st.session_state[k] = [] if k == "panneaux" else None
            st.rerun()
    with c2:
        csv_export = df_file.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Exporter file CSV", data=csv_export,
            file_name=f"file_production_{datetime.now():%Y%m%d_%H%M}.csv",
            mime="text/csv",
            key=f"export_file_{key_suffix}",
            width="stretch",
        )

    st.markdown('<div class="aa-section">Durées théoriques</div>',
                unsafe_allow_html=True)
    st.markdown('<div class="aa-card">', unsafe_allow_html=True)
    for pt in PANEL_TYPES:
        d    = get_duree_avec_manutention(pt)
        route_str = " → ".join(get_route(pt))
        c1, c2, c3 = st.columns([1, 1, 3])
        c1.write(f"**{pt}**")
        c2.write(f"{d:.0f}h")
        c3.caption(route_str)
    st.markdown('</div>', unsafe_allow_html=True)

# =============================================================================
# 11. HEADER + NAVIGATION
# =============================================================================

st.markdown(
    f'<div class="aa-header">'
    f'<p class="aa-header-title">✈️ Système d\'Ordonnancement FJSP</p>'
    f'<p class="aa-header-sub">'
    f'Ligne de fabrication de panneaux — Bombardier &nbsp;|&nbsp; '
    f'Agent : <strong>{mode}</strong> &nbsp;|&nbsp; '
    f't = {h_to_str(st.session_state.t_actuel)}'
    f'</p></div>',
    unsafe_allow_html=True,
)

# Hero: Workshop diagram — signature element
svg_workshop = f'''
<div class="hero-workshop">
    <p class="hero-workshop-title">📐 Schéma du flux d'atelier</p>
    <p class="hero-workshop-subtitle">8 postes de travail × 7 familles de panneaux — agent PPO optimise la séquence</p>
    <svg viewBox="0 0 1200 240" class="workshop-svg" xmlns="http://www.w3.org/2000/svg">
        <!-- Postes (8 colonnes) -->
        <g id="posts">
            <rect x="40" y="40" width="120" height="80" fill="rgba(255,255,255,0.12)" stroke="{CYAN}" stroke-width="2" rx="4"/>
            <text x="100" y="65" text-anchor="middle" font-size="12" font-family="IBM Plex Mono" font-weight="600" fill="{WHITE}">P1</text>
            <text x="100" y="85" text-anchor="middle" font-size="10" font-family="IBM Plex Mono" fill="rgba(255,255,255,0.7)">Découpe</text>
            
            <rect x="180" y="40" width="120" height="80" fill="rgba(255,255,255,0.12)" stroke="{CYAN}" stroke-width="2" rx="4"/>
            <text x="240" y="65" text-anchor="middle" font-size="12" font-family="IBM Plex Mono" font-weight="600" fill="{WHITE}">P2</text>
            <text x="240" y="85" text-anchor="middle" font-size="10" font-family="IBM Plex Mono" fill="rgba(255,255,255,0.7)">Fraisage</text>
            
            <rect x="320" y="40" width="120" height="80" fill="rgba(255,255,255,0.12)" stroke="{CYAN}" stroke-width="2" rx="4"/>
            <text x="380" y="65" text-anchor="middle" font-size="12" font-family="IBM Plex Mono" font-weight="600" fill="{WHITE}">P3</text>
            <text x="380" y="85" text-anchor="middle" font-size="10" font-family="IBM Plex Mono" fill="rgba(255,255,255,0.7)">Perçage</text>
            
            <rect x="460" y="40" width="120" height="80" fill="rgba(255,255,255,0.12)" stroke="{CYAN}" stroke-width="2" rx="4"/>
            <text x="520" y="65" text-anchor="middle" font-size="12" font-family="IBM Plex Mono" font-weight="600" fill="{WHITE}">P4</text>
            <text x="520" y="85" text-anchor="middle" font-size="10" font-family="IBM Plex Mono" fill="rgba(255,255,255,0.7)">Assemblage</text>
            
            <rect x="600" y="40" width="120" height="80" fill="rgba(255,255,255,0.12)" stroke="{CYAN}" stroke-width="2" rx="4"/>
            <text x="660" y="65" text-anchor="middle" font-size="12" font-family="IBM Plex Mono" font-weight="600" fill="{WHITE}">P5</text>
            <text x="660" y="85" text-anchor="middle" font-size="10" font-family="IBM Plex Mono" fill="rgba(255,255,255,0.7)">Soudage</text>
            
            <rect x="740" y="40" width="120" height="80" fill="rgba(255,255,255,0.12)" stroke="{CYAN}" stroke-width="2" rx="4"/>
            <text x="800" y="65" text-anchor="middle" font-size="12" font-family="IBM Plex Mono" font-weight="600" fill="{WHITE}">P6</text>
            <text x="800" y="85" text-anchor="middle" font-size="10" font-family="IBM Plex Mono" fill="rgba(255,255,255,0.7)">Peinture</text>
            
            <rect x="880" y="40" width="120" height="80" fill="rgba(255,255,255,0.12)" stroke="{CYAN}" stroke-width="2" rx="4"/>
            <text x="940" y="65" text-anchor="middle" font-size="12" font-family="IBM Plex Mono" font-weight="600" fill="{WHITE}">P7</text>
            <text x="940" y="85" text-anchor="middle" font-size="10" font-family="IBM Plex Mono" fill="rgba(255,255,255,0.7)">Inspection</text>
            
            <rect x="1020" y="40" width="120" height="80" fill="rgba(255,255,255,0.12)" stroke="{CYAN}" stroke-width="2" rx="4"/>
            <text x="1080" y="65" text-anchor="middle" font-size="12" font-family="IBM Plex Mono" font-weight="600" fill="{WHITE}">P8</text>
            <text x="1080" y="85" text-anchor="middle" font-size="10" font-family="IBM Plex Mono" fill="rgba(255,255,255,0.7)">Emballage</text>
        </g>
        
        <!-- Connecteurs -->
        <line x1="160" y1="80" x2="180" y2="80" stroke="rgba(0,119,200,0.4)" stroke-width="2" stroke-dasharray="4,4"/>
        <line x1="300" y1="80" x2="320" y2="80" stroke="rgba(0,119,200,0.4)" stroke-width="2" stroke-dasharray="4,4"/>
        <line x1="440" y1="80" x2="460" y2="80" stroke="rgba(0,119,200,0.4)" stroke-width="2" stroke-dasharray="4,4"/>
        <line x1="580" y1="80" x2="600" y2="80" stroke="rgba(0,119,200,0.4)" stroke-width="2" stroke-dasharray="4,4"/>
        <line x1="720" y1="80" x2="740" y2="80" stroke="rgba(0,119,200,0.4)" stroke-width="2" stroke-dasharray="4,4"/>
        <line x1="860" y1="80" x2="880" y2="80" stroke="rgba(0,119,200,0.4)" stroke-width="2" stroke-dasharray="4,4"/>
        <line x1="1000" y1="80" x2="1020" y2="80" stroke="rgba(0,119,200,0.4)" stroke-width="2" stroke-dasharray="4,4"/>
        
        <!-- Panel types (7 familles, bas) -->
        <g id="panels">
            <circle cx="100" cy="165" r="8" fill="#0077C8"/>
            <text x="100" y="185" text-anchor="middle" font-size="9" font-family="IBM Plex Mono" fill="{DGRAY}">Sup AV</text>
            
            <circle cx="200" cy="165" r="8" fill="#0B1E3D"/>
            <text x="200" y="185" text-anchor="middle" font-size="9" font-family="IBM Plex Mono" fill="{DGRAY}">Sup AR</text>
            
            <circle cx="300" cy="165" r="8" fill="#C8333B"/>
            <text x="300" y="185" text-anchor="middle" font-size="9" font-family="IBM Plex Mono" fill="{DGRAY}">Inf AV</text>
            
            <circle cx="400" cy="165" r="8" fill="#1E9E6A"/>
            <text x="400" y="185" text-anchor="middle" font-size="9" font-family="IBM Plex Mono" fill="{DGRAY}">Ar D</text>
            
            <circle cx="500" cy="165" r="8" fill="#D98B2B"/>
            <text x="500" y="185" text-anchor="middle" font-size="9" font-family="IBM Plex Mono" fill="{DGRAY}">Ar G</text>
            
            <circle cx="600" cy="165" r="8" fill="#6B4FA0"/>
            <text x="600" y="185" text-anchor="middle" font-size="9" font-family="IBM Plex Mono" fill="{DGRAY}">Av D</text>
            
            <circle cx="700" cy="165" r="8" fill="#147A7A"/>
            <text x="700" y="185" text-anchor="middle" font-size="9" font-family="IBM Plex Mono" fill="{DGRAY}">Av G</text>
        </g>
        
        <!-- Legend -->
        <text x="40" y="220" font-size="9" font-family="IBM Plex Mono" fill="rgba(255,255,255,0.5)">22 machines sur 8 postes × agent RL parcourt 130-D observation space pour routing optimal</text>
    </svg>
</div>
'''
st.markdown(svg_workshop, unsafe_allow_html=True)

PAGE = st.radio(
    "Navigation",
    ["📋 Commandes", "⚙️ Ordonnancement", "📊 Résultats", "🔔 Aléas"],
    horizontal=True, label_visibility="collapsed",
)
st.divider()

# =============================================================================
# PAGE 1 — COMMANDES
# =============================================================================

if PAGE == "📋 Commandes":
    st.markdown('<div class="aa-section">Saisie des commandes client</div>',
                unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(
        ["➕ Panneau unique", "📦 Unité complète (7 panneaux)", "📂 Import CSV"])

    # ---- TAB 1 : Panneau unique -----------------------------------------------
    with tab1:
        col1, col2 = st.columns([1.3, 1])
        with col1:
            r1, r2 = st.columns(2)
            with r1:
                type_panneau = st.selectbox("Type de panneau", PANEL_TYPES, key="p_type")
                of_ref       = st.text_input("Référence OF", placeholder="auto", key="p_of")
            with r2:
                date_dispo = st.date_input("Disponibilité matière",
                                            value=date.today(), key="p_dispo")
                date_serv  = st.date_input("Date de servitude",
                                            value=date.today() + timedelta(days=45),
                                            key="p_serv")

            statut_init = st.selectbox(
                "Statut initial",
                ["EN_ATTENTE", "EN_COURS", "STANDBY"],
                key="p_statut",
                help=(
                    "EN_ATTENTE : panneau en file, pas encore démarré\n"
                    "EN_COURS   : panneau en production sur une machine\n"
                    "STANDBY    : panneau suspendu (attente pièce, aléa...)"
                ),
            )

            en_cours   = (statut_init == "EN_COURS")
            en_standby = (statut_init == "STANDBY")
            actif      = en_cours or en_standby

            st.divider()

            # ---- Aperçu de la gamme pour ce type
            route_preview = get_route(type_panneau)
            route_html    = " → ".join(
                f'<code style="background:{CYAN};color:{WHITE};'
                f'padding:2px 6px;border-radius:4px">{p}</code>'
                if i == 0 else
                f'<code style="background:{LGRAY};color:{DGRAY};'
                f'padding:2px 6px;border-radius:4px;border:1px solid {MGRAY}">{p}</code>'
                for i, p in enumerate(route_preview)
            )
            st.markdown(
                f'<div style="font-size:0.8rem;color:{DGRAY};margin-bottom:10px">'
                f'<b>Gamme {type_panneau} :</b><br>{route_html}</div>',
                unsafe_allow_html=True)

            st.markdown(
                f"**📍 Position actuelle** "
                f"{'— ' + statut_init if actif else '(non applicable pour EN_ATTENTE)'}"
            )

            c1, c2 = st.columns(2)
            with c1:
                # [I1] Machines filtrées selon le poste courant déclaré
                # Pour EN_COURS, toutes les machines sont proposées (l'agent choisit
                # n'importe quel poste de la gamme)
                machine_init = st.selectbox(
                    "Machine en cours",
                    ["—"] + ALL_MACHINES,
                    disabled=not actif,
                    key="p_machine",
                    help="Machine sur laquelle le panneau est actuellement",
                )
            with c2:
                avancement = st.slider(
                    "Avancement (%)", 0, 100, 50,
                    disabled=not actif,
                    key="p_avancement",
                    help="Pourcentage d'avancement sur la machine sélectionnée",
                ) / 100.0

            # [I1] Aperçu de la route après déclaration EN_COURS
            if en_cours and machine_init != "—":
                poste_machine = MACHINE_VERS_POSTE.get(machine_init, "")
                route_p       = get_route(type_panneau)
                op_idx        = next(
                    (i for i, p in enumerate(route_p) if p == poste_machine), 0)
                steps_html = '<div class="route-flow">'
                for i, p in enumerate(route_p):
                    if i < op_idx:
                        steps_html += f'<span class="route-step route-done">{p}</span>'
                    elif i == op_idx:
                        steps_html += f'<span class="route-step route-current">{p}</span>'
                    else:
                        steps_html += f'<span class="route-step route-todo">{p}</span>'
                    if i < len(route_p) - 1:
                        steps_html += '<span class="route-connector">┄┄&gt;</span>'
                steps_html += '</div>'
                st.markdown(steps_html, unsafe_allow_html=True)

            # Champs STANDBY
            raison_standby = ""
            date_remise    = None
            if en_standby:
                st.markdown("**⏸️ Informations suspension**")
                c3, c4 = st.columns(2)
                with c3:
                    raison_standby = st.text_input(
                        "Raison du STANDBY",
                        placeholder="Ex: attente pièce, aléa qualité...",
                        key="p_raison")
                with c4:
                    date_remise = st.date_input(
                        "Date estimée de remise en ligne",
                        value=date.today() + timedelta(days=7),
                        key="p_remise")

                # [I2] Alerte stock plein
                n_std_cur = sum(1 for p in st.session_state.panneaux
                                if p.statut == Statut.STANDBY)
                if n_std_cur >= CAPACITE_STOCK_STANDBY:
                    st.error(
                        f"⛔ Stock STANDBY plein ({n_std_cur}/{CAPACITE_STOCK_STANDBY}). "
                        f"Impossible d'ajouter un panneau STANDBY supplémentaire. "
                        f"Remettez en ligne un panneau existant.")

            # ---- Bouton ajout — double validation stock + machine
            # machines_en_cours_occupees défini ici (scope global du formulaire)
            machines_en_cours_occupees = {
                p.machine_assignee
                for p in st.session_state.panneaux
                if p.statut == Statut.EN_COURS and p.machine_assignee
            }
            n_std_cur          = sum(1 for p in st.session_state.panneaux
                                     if p.statut == Statut.STANDBY)
            stock_plein        = en_standby and (n_std_cur >= CAPACITE_STOCK_STANDBY)
            mach_deja_occupee  = (en_cours and machine_init != "—"
                                  and machine_init in machines_en_cours_occupees)

            if st.button("➕ Ajouter panneau", type="primary",
                         key="btn_ajouter_panneau", width="stretch",
                         disabled=stock_plein or mach_deja_occupee):

                mach = machine_init if machine_init != "—" else None
                # Garde-fou côté serveur — au cas où le bouton passerait quand même
                if en_cours and mach and mach in machines_en_cours_occupees:
                    st.error(f"❌ {mach} déjà occupée par un panneau EN_COURS.")
                    st.stop()

                rel = dt_to_h(datetime.combine(date_dispo, datetime.min.time()))
                due = dt_to_h(datetime.combine(date_serv, datetime.min.time())
                              + timedelta(hours=23, minutes=59))
                if due <= rel:
                    due = rel + get_duree_avec_manutention(type_panneau) * 2.0

                duree_theo = get_duree_avec_manutention(type_panneau)
                mgh = new_mgh()
                of  = of_ref.strip() if of_ref.strip() else new_of()
                p   = Panneau(type_panneau, of, rel, due)
                p.mgh_id = mgh
                mach = machine_init if machine_init != "—" else None

                if en_cours and mach:
                    # [I1] FIX-ROUTE : assigner_machine() synchronise op_courante
                    # via MACHINE_VERS_POSTE → op_courante pointe le bon poste
                    d_op  = get_temps(mach, type_panneau)
                    t_deb = max(0.0, st.session_state.t_actuel - d_op * avancement)
                    p.assigner_machine(mach, t_deb)
                    p.avancement_declare = avancement

                elif en_standby:
                    p.statut = Statut.STANDBY
                    p.meta   = {
                        "dernier_poste"    : mach or "—",
                        "avancement_pct"   : round(avancement * 100),
                        "raison_standby"   : raison_standby,
                        "remise_en_ligne_h": dt_to_h(
                            datetime.combine(date_remise, datetime.min.time())
                        ) if date_remise else None,
                    }
                    if date_remise:
                        p.release_date = dt_to_h(
                            datetime.combine(date_remise, datetime.min.time()))

                st.session_state.panneaux.append(p)
                fenetre = due - rel

                if en_standby:
                    st.info(
                        f"⏸️ {mgh} ({type_panneau}) ajouté en STANDBY "
                        f"— remise prévue : "
                        f"{date_remise.strftime('%d/%m/%Y') if date_remise else 'inconnue'}")
                elif en_cours and mach:
                    # Afficher la route synchronisée
                    poste_m  = MACHINE_VERS_POSTE.get(mach, "")
                    route_p  = get_route(type_panneau)
                    op_final = next(
                        (i for i, pos in enumerate(route_p) if pos == poste_m), 0)
                    suite    = " → ".join(route_p[op_final + 1:]) or "TERMINÉ"
                    st.success(
                        f"✅ {mgh} ({type_panneau}) EN_COURS sur {mach} "
                        f"({avancement*100:.0f}%) — Suite : {suite}")
                elif fenetre < duree_theo:
                    st.warning(
                        f"⚠️ Délai court : {fenetre:.0f}h / {duree_theo:.0f}h théoriques")
                else:
                    st.success(
                        f"✅ {mgh} ({type_panneau}) [{statut_init}] ajouté "
                        f"— facteur {fenetre/duree_theo:.2f}x")
                st.rerun()

            # Panneaux STANDBY — remise en ligne
            panneaux_standby = [
                p for p in st.session_state.panneaux if p.statut == Statut.STANDBY]
            if panneaux_standby:
                st.divider()
                st.markdown("**⏸️ Panneaux en STANDBY — Remise en ligne**")
                for p_sb in panneaux_standby:
                    meta   = getattr(p_sb, "meta", {})
                    raison = meta.get("raison_standby", "—")
                    poste  = meta.get("dernier_poste", "—")
                    avanc  = meta.get("avancement_pct", 0)
                    c1, c2, c3 = st.columns([2, 2, 1])
                    with c1:
                        st.write(f"**{p_sb.mgh_id}** — {p_sb.panel_type}")
                        st.caption(f"Poste : {poste} | Avancement : {avanc}%")
                        if raison and raison != "—":
                            st.caption(f"Raison : {raison}")
                    with c2:
                        remise_h = meta.get("remise_en_ligne_h")
                        if remise_h:
                            st.caption(f"Remise prévue : {h_to_str(remise_h)}")
                    with c3:
                        if st.button("▶️ Remettre", key=f"remise_{p_sb.mgh_id}",
                                     help="Remettre en file EN_ATTENTE"):
                            p_sb.statut       = Statut.EN_ATTENTE
                            p_sb.meta         = {}
                            p_sb.release_date = st.session_state.t_actuel
                            st.success(f"✅ {p_sb.mgh_id} remis en EN_ATTENTE")
                            st.rerun()

        with col2:
            _render_file_production(key_suffix="tab1")

    # ---- TAB 2 : Unité complète -----------------------------------------------
    with tab2:
        col1, col2 = st.columns([1.3, 1])
        with col1:
            st.markdown(
                '<div class="aa-card">'
                '<div class="aa-card-title">Une unité = 7 panneaux (un de chaque type)'
                ' avec la même date de servitude</div>',
                unsafe_allow_html=True)
            with st.form("form_unite", clear_on_submit=True):
                r1, r2 = st.columns(2)
                with r1:
                    of_unite     = st.text_input("Référence OF unité", placeholder="auto")
                    date_dispo_u = st.date_input("Disponibilité matière",
                                                  value=date.today(), key="dispo_unite")
                with r2:
                    date_serv_u = st.date_input("Date de servitude commune",
                                                 value=date.today() + timedelta(days=60),
                                                 key="serv_unite")
                st.markdown("**Types inclus :**")
                cols_types = st.columns(4)
                types_sel  = {}
                for i, pt in enumerate(PANEL_TYPES):
                    with cols_types[i % 4]:
                        types_sel[pt] = st.checkbox(pt, value=True, key=f"chk_{pt}")
                submitted_u = st.form_submit_button(
                    "📦 Ajouter l'unité", type="primary", width="stretch")

            if submitted_u:
                rel_u   = dt_to_h(datetime.combine(date_dispo_u, datetime.min.time()))
                due_u   = dt_to_h(datetime.combine(date_serv_u, datetime.min.time())
                                  + timedelta(hours=23, minutes=59))
                of_base = of_unite.strip() if of_unite.strip() else new_of()
                n_aj    = 0
                alertes = []
                for pt, sel in types_sel.items():
                    if not sel:
                        continue
                    duree_theo = get_duree_avec_manutention(pt)
                    mgh = new_mgh()
                    p   = Panneau(pt, f"{of_base}-{pt.replace(' ','')}", rel_u, due_u)
                    p.mgh_id = mgh
                    st.session_state.panneaux.append(p)
                    n_aj += 1
                    if due_u - rel_u < duree_theo:
                        alertes.append(f"⚠️ {pt} : {due_u-rel_u:.0f}h / {duree_theo:.0f}h")
                if n_aj:
                    st.success(f"✅ {n_aj} panneau(x) ajoutés — servitude : {h_to_str(due_u)}")
                    for a in alertes:
                        st.warning(a)
                    st.rerun()

        with col2:
            _render_file_production(key_suffix="tab2")

    # ---- TAB 3 : Import CSV ---------------------------------------------------
    with tab3:
        st.markdown(
            '<div class="aa-card">'
            '<div class="aa-card-title">Format attendu</div>'
            '<code>type, of, date_dispo, date_serv</code><br>'
            'Exemple : <code>Sup AV, OF-001, 2026-01-01, 2026-03-01</code>'
            '</div>', unsafe_allow_html=True)
        csv_file = st.file_uploader("📂 Importer CSV", type="csv")
        if csv_file:
            try:
                df_csv = pd.read_csv(csv_file)
                for _, row in df_csv.iterrows():
                    rel = dt_to_h(datetime.strptime(str(row["date_dispo"]), "%Y-%m-%d"))
                    due = dt_to_h(datetime.strptime(str(row["date_serv"]),  "%Y-%m-%d")
                                  + timedelta(hours=23, minutes=59))
                    p        = Panneau(str(row["type"]),
                                       str(row.get("of", new_of())), rel, due)
                    p.mgh_id = new_mgh()
                    st.session_state.panneaux.append(p)
                st.success(f"✅ {len(df_csv)} panneaux importés")
                st.rerun()
            except Exception as e:
                st.error(f"Erreur CSV : {e}")

# =============================================================================
# PAGE 2 — ORDONNANCEMENT
# =============================================================================

elif PAGE == "⚙️ Ordonnancement":
    st.markdown('<div class="aa-section">Lancer l\'ordonnancement</div>',
                unsafe_allow_html=True)

    n = len(st.session_state.panneaux)
    if n == 0:
        st.warning("Aucun panneau. Allez à **Commandes** d'abord.")
    else:
        m1, m2, m3 = st.columns(3)
        m1.markdown(
            f'<div class="aa-card aa-card-accent">'
            f'<div class="aa-card-title">Panneaux en file</div>'
            f'<div class="aa-card-value">{n}</div></div>',
            unsafe_allow_html=True)
        m2.markdown(
            f'<div class="aa-card aa-card-accent">'
            f'<div class="aa-card-title">Mode agent</div>'
            f'<div class="aa-card-value" style="font-size:1.3rem">{mode}</div>'
            f'</div>', unsafe_allow_html=True)
        m3.markdown(
            f'<div class="aa-card aa-card-accent">'
            f'<div class="aa-card-title">t courant</div>'
            f'<div class="aa-card-value" style="font-size:1.1rem">'
            f'{h_to_str(st.session_state.t_actuel)}</div></div>',
            unsafe_allow_html=True)

        # [I4] Tableau avec route visuelle
        rows = []
        for p in st.session_state.panneaux:
            d       = get_duree_avec_manutention(p.panel_type)
            fenetre = p.due_date - p.release_date
            fct     = fenetre / d if d > 0 else 0
            rows.append({
                "MGH"        : p.mgh_id,
                "Type"       : p.panel_type,
                "Statut"     : p.statut.value,
                "Op. courante": p.route[p.op_courante] if p.op_courante < len(p.route) else "—",
                "Dispo mat." : h_to_str(p.release_date),
                "Servitude"  : h_to_str(p.due_date),
                "Durée théo.": f"{d:.0f}h",
                "Facteur"    : f"{fct:.2f}x",
                "Risque"     : "⚠️ Serré" if fct < 1.5 else "✓ OK",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True)
        st.divider()

        if st.button("🚀 Calculer l'ordonnancement", type="primary", width="stretch"):
            with st.spinner(f"Calcul ({mode}) — ordonnancement parallèle..."):
                panneaux_copy = copy.deepcopy(st.session_state.panneaux)
                df, met, env  = ordonnancer(
                    panneaux_copy, st.session_state.t_actuel, modele, mode)
                st.session_state.planning_df = df
                st.session_state.metriques   = met
                st.session_state.env         = env
                st.session_state.panneaux    = env.tous_les_panneaux
            st.success(
                f"✅ Terminé en {met['n_steps']} itérations — makespan {met['makespan']:.0f}h")
            st.rerun()

# =============================================================================
# PAGE 3 — RÉSULTATS
# =============================================================================

elif PAGE == "📊 Résultats":
    st.markdown('<div class="aa-section">Résultats d\'ordonnancement</div>',
                unsafe_allow_html=True)

    if st.session_state.planning_df is None:
        st.warning("Aucun ordonnancement calculé. Allez à **Ordonnancement**.")
    else:
        df  = st.session_state.planning_df
        met = st.session_state.metriques

        k1, k2, k3, k4 = st.columns(4)
        taux_pct = met["taux_ok"] * 100
        acc_taux = ("aa-card-ok"     if taux_pct >= 80
                    else "aa-card-warn" if taux_pct >= 60
                    else "aa-card-danger")
        acc_ret  = ("aa-card-ok"     if met["retard_moyen"] < 10
                    else "aa-card-warn" if met["retard_moyen"] < 50
                    else "aa-card-danger")

        k1.markdown(
            f'<div class="aa-card aa-card-accent">'
            f'<div class="aa-card-title">Makespan</div>'
            f'<div class="aa-card-value">{met["makespan"]:.0f}h</div>'
            f'<div class="aa-card-sub">Fin : {h_to_str(met["makespan"])}</div>'
            f'</div>', unsafe_allow_html=True)
        k2.markdown(
            f'<div class="aa-card {acc_taux}">'
            f'<div class="aa-card-title">Livraison à temps</div>'
            f'<div class="aa-card-value">{taux_pct:.0f}%</div>'
            f'<div class="aa-card-sub">{met["n_ok"]}/{met["n_total"]} panneaux</div>'
            f'</div>', unsafe_allow_html=True)
        k3.markdown(
            f'<div class="aa-card {acc_ret}">'
            f'<div class="aa-card-title">Retard moyen</div>'
            f'<div class="aa-card-value">{met["retard_moyen"]:.1f}h</div>'
            f'<div class="aa-card-sub">sur panneaux en retard</div>'
            f'</div>', unsafe_allow_html=True)
        k4.markdown(
            f'<div class="aa-card aa-card-accent">'
            f'<div class="aa-card-title">Mode / Itérations</div>'
            f'<div class="aa-card-value" style="font-size:1.3rem">{met["mode"]}</div>'
            f'<div class="aa-card-sub">{met["n_steps"]:,} itérations</div>'
            f'</div>', unsafe_allow_html=True)

        st.divider()

        # Gantt — se régénère automatiquement avec t_actuel courant
        st.markdown('<div class="aa-section">Diagramme de Gantt</div>',
                    unsafe_allow_html=True)

        gc1, gc2 = st.columns([3, 1])
        with gc1:
            mode_axe_label = st.radio(
                "Axe X",
                [
                    "📅 Dates calendaires continues",
                    f"🏭 Calendrier shifts ({SHIFT_HEURES}h/jour, {SHIFT_START}h–{SHIFT_START+SHIFT_HEURES}h)",
                    "⏱️ Heures cumulées (0, 100, 200...)",
                ],
                horizontal=True,
            )
        with gc2:
            st.markdown("<br>", unsafe_allow_html=True)
            st.caption(
                f"🟠 Ligne Maintenant = **{h_to_str(st.session_state.t_actuel)}**  \n"
                f"Changer la date dans la ◀️ sidebar pour déplacer la ligne."
            )
            if "shifts" in mode_axe_label.lower() or "14h" in mode_axe_label:
                st.caption(
                    f"🌙 Les zones grises = hors shift.  \n"
                    f"✂️ = opération coupée sur 2 jours."
                )

        if "shifts" in mode_axe_label or f"{SHIFT_HEURES}h" in mode_axe_label:
            mode_axe = "shifts"
        elif "calendaires" in mode_axe_label:
            mode_axe = "datetime"
        else:
            mode_axe = "heures"
        # La ligne orange utilise t_actuel courant — se met à jour sans réordonnancer
        fig = creer_gantt(df, st.session_state.panneaux, mode_axe)
        st.plotly_chart(fig, use_container_width=True, key=f"gantt_{st.session_state.t_actuel:.0f}")
        st.divider()

        # Graphique utilisation des bâtis
        st.markdown('<div class="aa-section">Utilisation des bâtis</div>',
                    unsafe_allow_html=True)
        makespan_val = float(df["fin"].max())
        if makespan_val > 0:
            util_data = []
            for m in ALL_MACHINES:
                df_m  = df[df["machine"] == m]
                t_occ = float((df_m["fin"] - df_m["debut"]).sum())                         if not df_m.empty else 0.0
                util_data.append({"Machine": m, "Utilisation": t_occ / makespan_val})
            df_util  = pd.DataFrame(util_data).sort_values("Utilisation", ascending=True)
            fig_util = px.bar(
                df_util, x="Utilisation", y="Machine", orientation="h",
                color="Utilisation",
                color_continuous_scale=[[0, RED], [0.5, ORANGE], [1, GREEN]],
                title="Taux d'utilisation par bâti",
                range_x=[0, 1],
            )
            fig_util.update_layout(
                plot_bgcolor=WHITE, paper_bgcolor=WHITE,
                font=dict(family="IBM Plex Sans", color=NAVY),
                height=500, coloraxis_showscale=False,
                xaxis_tickformat=".0%",
            )
            fig_util.add_vline(
                x=0.75, line_dash="dash", line_color=NAVY, opacity=0.4,
                annotation_text="Seuil 75%", annotation_position="top right",
            )
            st.plotly_chart(fig_util, use_container_width=True)
        st.divider()

        # Tableau planning détaillé
        st.markdown('<div class="aa-section">Détail des opérations</div>',
                    unsafe_allow_html=True)
        t_now   = st.session_state.t_actuel
        df_aff  = df.copy()
        df_aff["Début"] = df_aff["debut"].apply(h_to_str)
        df_aff["Fin"]   = df_aff["fin"].apply(h_to_str)

        def _etat_reel(r):
            if r["interrompu"]:
                return "🔴 Interrompu"
            if r["fin"] <= t_now:
                return "✅ Terminé" if not r["en_retard"] else "⚠️ Terminé en retard"
            if r["debut"] <= t_now < r["fin"]:
                pct = int((t_now - r["debut"]) / max(r["fin"] - r["debut"], 1) * 100)
                return f"⚙️ En cours ({pct}%)"
            return "⏳ Planifié" if not r["en_retard"] else "⚠️ Retard prévu"

        df_aff["État"] = df_aff.apply(_etat_reel, axis=1)
        st.caption(
            f"🟠 **Maintenant** = {h_to_str(t_now)} | "
            f"✅ Terminé = fin avant maintenant | "
            f"⚙️ En cours = opération active | "
            f"⏳ Planifié = opération future"
        )
        st.dataframe(
            df_aff[["MGH", "OF", "type_panneau", "poste", "machine",
                    "Début", "Fin", "État"]],
            use_container_width=True)
        st.divider()

        # Exports
        c1, c2 = st.columns(2)
        with c1:
            xl = exporter_excel(df, st.session_state.panneaux)
            st.download_button(
                "⬇️ Exporter Excel", data=xl,
                file_name=f"planning_fjsp_{datetime.now():%Y%m%d_%H%M}.xlsx",
                mime=("application/vnd.openxmlformats-officedocument"
                      ".spreadsheetml.sheet"),
                type="primary", width="stretch",
            )
        with c2:
            html_gantt = fig.to_html(include_plotlyjs="cdn")
            st.download_button(
                "⬇️ Exporter Gantt HTML", data=html_gantt,
                file_name=f"gantt_fjsp_{datetime.now():%Y%m%d_%H%M}.html",
                mime="text/html", width="stretch",
            )

# =============================================================================
# PAGE 4 — ALÉAS
# =============================================================================

elif PAGE == "🔔 Aléas":
    st.markdown('<div class="aa-section">Gestion des aléas de production</div>',
                unsafe_allow_html=True)

    if not st.session_state.panneaux:
        st.warning("Aucun panneau en production. Lancez d'abord un ordonnancement.")
    else:
        panneaux   = st.session_state.panneaux
        t_now      = st.session_state.get("t_actuel", 0.0)
        en_cours_p = [p for p in panneaux if p.statut == Statut.EN_COURS]
        en_standby = [p for p in panneaux if p.statut == Statut.STANDBY]
        n_standby  = len(en_standby)

        # État ligne
        st.markdown('<div class="aa-section">📊 État actuel de la ligne</div>',
                    unsafe_allow_html=True)
        st.caption(
            f"⏱️ Heure courante : **{h_to_str(t_now)}** "
            f"(t = {t_now:.1f}h depuis le {T_REFERENCE.strftime('%d/%m/%Y')})")

        df_plan = st.session_state.planning_df
        if df_plan is not None and not df_plan.empty:
            # Filtrer selon t_actuel COURANT — se met à jour quand on change la date
            ops_terminees = df_plan[df_plan["fin"]   <= t_now]
            ops_en_cours  = df_plan[(df_plan["debut"] <= t_now) & (df_plan["fin"] > t_now)]
            ops_futures   = df_plan[df_plan["debut"]  > t_now]

            k1, k2, k3, k4 = st.columns(4)
            k1.metric("✅ Opérations terminées", len(ops_terminees))
            k2.metric("⚙️ En cours maintenant",  len(ops_en_cours))
            k3.metric("⏳ Opérations futures",    len(ops_futures))
            k4.metric(f"⏸️ Standby ({n_standby}/{CAPACITE_STOCK_STANDBY})",
                      n_standby,
                      delta=f"{CAPACITE_STOCK_STANDBY - n_standby} places libres",
                      delta_color="off")

            if not ops_en_cours.empty:
                st.markdown("**⚙️ Opérations actuellement en cours :**")
                aff_enc = ops_en_cours.copy()
                aff_enc["Avancement"] = aff_enc.apply(
                    lambda r: f"{int((t_now-r['debut'])/max(r['fin']-r['debut'],1)*100)}%",
                    axis=1)
                aff_enc["Fin prévue"] = aff_enc["fin"].apply(h_to_str)
                aff_enc["Début"]      = aff_enc["debut"].apply(h_to_str)
                st.dataframe(
                    aff_enc[["MGH", "type_panneau", "machine", "Début", "Avancement", "Fin prévue"]],
                    use_container_width=True, hide_index=True)

            st.info(
                f"💡 Lors du réordonnancement après aléa, l'agent repart de **t={t_now:.0f}h** "
                f"et considère les {len(ops_terminees)} opérations terminées comme fixes.")
        st.divider()

        col1, col2 = st.columns(2)

        # ---- Déclarer un aléa
        with col1:
            st.markdown('<div class="aa-card">', unsafe_allow_html=True)
            st.markdown("### 🔴 Déclarer un aléa")

            # Construire la liste des panneaux EN COURS à t_actuel
            # depuis le planning_df (source de vérité) plutôt que session_state
            # → s'adapte automatiquement quand on change la date
            if df_plan is not None and not df_plan.empty:
                # Panneaux dont une opération est en cours à t_now selon le planning
                mgh_en_cours_maintenant = set(
                    df_plan[(df_plan["debut"] <= t_now) & (df_plan["fin"] > t_now)]["MGH"]
                )
                # Récupérer les objets Panneau correspondants
                en_cours_maintenant = [
                    p for p in panneaux
                    if p.mgh_id in mgh_en_cours_maintenant
                    and p.statut != Statut.STANDBY
                ]
                # Enrichir avec info opération courante depuis le planning
                ops_enc_dict = {}
                if not ops_en_cours.empty:
                    for _, row in ops_en_cours.iterrows():
                        ops_enc_dict[row["MGH"]] = {
                            "machine" : row["machine"],
                            "poste"   : row["poste"],
                            "avancement": int((t_now - row["debut"]) /
                                             max(row["fin"] - row["debut"], 1) * 100),
                            "fin_prevue": h_to_str(row["fin"]),
                        }
            else:
                en_cours_maintenant = en_cours_p
                ops_enc_dict        = {}

            # [I6] Alerte stock plein
            if n_standby >= CAPACITE_STOCK_STANDBY:
                st.error(
                    f"⛔ Stock STANDBY plein ({n_standby}/{CAPACITE_STOCK_STANDBY}). "
                    f"Impossible de déclarer un nouvel aléa. "
                    f"Remettez en ligne un panneau avant de continuer.")
            elif not en_cours_maintenant:
                st.info(f"Aucun panneau en cours à {h_to_str(t_now)}.")
            else:
                # Options enrichies avec état depuis le planning
                def _label_panneau(p):
                    info = ops_enc_dict.get(p.mgh_id, {})
                    mach = info.get("machine", p.machine_assignee or "—")
                    avanc = info.get("avancement", 0)
                    return f"{p.mgh_id} — {p.panel_type} / {mach} ({avanc}%)"

                opts  = [_label_panneau(p) for p in en_cours_maintenant]
                choix = st.selectbox("Panneau en cours à déclarer", opts)
                p_sel = en_cours_maintenant[opts.index(choix)]

                # Fiche détaillée enrichie depuis le planning
                info_sel  = ops_enc_dict.get(p_sel.mgh_id, {})
                mach_sel  = info_sel.get("machine",  p_sel.machine_assignee or "—")
                poste_sel = info_sel.get("poste",    p_sel.poste_courant or "—")
                avanc_sel = info_sel.get("avancement", 0)
                fin_sel   = info_sel.get("fin_prevue", "—")

                st.markdown(
                    f'<div style="background:{LGRAY};border-radius:8px;'
                    f'padding:12px;margin:8px 0;border-left:3px solid {CYAN}">'
                    f'<b>{p_sel.mgh_id}</b> — {p_sel.panel_type}<br>'
                    f'Bâti actuel : <code>{mach_sel}</code> &nbsp;|&nbsp; '
                    f'Poste : <code>{poste_sel}</code><br>'
                    f'Avancement : <b>{avanc_sel}%</b> &nbsp;|&nbsp; '
                    f'Fin prévue : <b>{fin_sel}</b>'
                    f'</div>', unsafe_allow_html=True)

                # Route visuelle
                st.markdown(_render_route_html(p_sel), unsafe_allow_html=True)

                duree_sb = st.number_input(
                    "Durée standby estimée (h)", 0.5, 200.0, 4.0, 0.5)
                t_retour = t_now + duree_sb

                st.markdown(
                    f'<div style="background:#FBF1E2;border-radius:4px;'
                    f'padding:9px 12px;border-left:3px solid {ORANGE};'
                    f'font-size:0.85rem">'
                    f'Retour estimé : <b>{h_to_str(t_retour)}</b> &nbsp;|&nbsp; '
                    f'Places restantes : <b>{CAPACITE_STOCK_STANDBY - n_standby - 1}</b>'
                    f'</div>', unsafe_allow_html=True)

                if st.button("🔴 Déclarer l'aléa + recalculer",
                             type="primary", width="stretch"):
                    if st.session_state.env:
                        res = st.session_state.env.declarer_alea(
                            p_sel.mgh_id, duree_sb, modele)
                        if res.get("succes"):
                            st.success(
                                f"✅ Aléa déclaré — bâti **{res['machine_liberee']}** "
                                f"libre à {h_to_str(res['t_libre'])}")
                            if res["candidats"]:
                                st.info(f"💡 Candidats slot : "
                                        f"**{', '.join(res['candidats'])}**")
                            if res.get("nouveau_planning") is not None:
                                st.session_state.planning_df = res["nouveau_planning"]
                            st.session_state.panneaux = \
                                st.session_state.env.tous_les_panneaux
                            st.rerun()
                        else:
                            st.error(res.get("raison", "Erreur inconnue"))
                    else:
                        st.error("Lancez d'abord un ordonnancement.")
            st.markdown('</div>', unsafe_allow_html=True)

        # ---- Panneaux en standby
        with col2:
            st.markdown('<div class="aa-card">', unsafe_allow_html=True)
            st.markdown("### 🟢 Panneaux en standby")
            if not en_standby:
                st.info("Aucun panneau en standby.")
            else:
                for p in en_standby:
                    with st.expander(f"{p.mgh_id} — {p.panel_type}"):
                        # [I4] Route visuelle
                        st.markdown(_render_route_html(p), unsafe_allow_html=True)
                        if p.alea:
                            st.markdown(
                                f'**Poste :** {p.alea.poste}  \n'
                                f'**Progression :** {p.alea.progression_pct*100:.0f}%  \n'
                                f'**Durée restante :** {p.alea.duree_restante:.2f}h  \n'
                                f'**Retour estimé :** {h_to_str(p.alea.t_retour_estime)}')
                        if st.button(f"🟢 Remettre en ligne",
                                     key=f"ret_{p.mgh_id}", width="stretch"):
                            if st.session_state.env:
                                ret = st.session_state.env.remettre_en_ligne(
                                    p.mgh_id, modele)
                                if ret.get("succes"):
                                    st.success(f"✅ {p.mgh_id} remis en ligne — "
                                               f"stock : {ret['n_standby']}/{CAPACITE_STOCK_STANDBY}")
                                    if ret.get("nouveau_planning") is not None:
                                        st.session_state.planning_df = ret["nouveau_planning"]
                                    st.session_state.panneaux = \
                                        st.session_state.env.tous_les_panneaux
                                    st.rerun()
                            else:
                                st.error("Lancez d'abord un ordonnancement.")
            st.markdown('</div>', unsafe_allow_html=True)

        # Historique aléas
        alea_hist = [p for p in panneaux if p.alea]
        if alea_hist:
            st.divider()
            st.markdown('<div class="aa-section">Historique des aléas</div>',
                        unsafe_allow_html=True)
            rows = []
            for p in alea_hist:
                a = p.alea
                rows.append({
                    "MGH"         : p.mgh_id,
                    "Type"        : p.panel_type,
                    "Poste"       : a.poste,
                    "Machine"     : a.machine,
                    "Progression" : f"{a.progression_pct*100:.0f}%",
                    "Fait (h)"    : f"{a.duree_deja_faite:.2f}",
                    "Reste (h)"   : f"{a.duree_restante:.2f}",
                    "Standby est.": f"{a.duree_standby_est:.1f}h",
                    "Retour est." : h_to_str(a.t_retour_estime),
                    "Retour réel" : h_to_str(a.t_retour_reel) if a.t_retour_reel else "—",
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
