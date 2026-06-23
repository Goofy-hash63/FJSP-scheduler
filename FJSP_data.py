

from enum import Enum
from dataclasses import dataclass
from typing import Optional

# TEMPS LINÉAIRE


TEMPS_MANUTENTION = 0.5   # 30 min = 0.5h


def prochain_debut_shift(t: float, poste: str = "") -> float:
    """Compatibilité : retourne t directement (pas de shift en temps linéaire)."""
    return t


def est_en_production(t: float, poste: str = "") -> bool:
    """La ligne tourne en continu — toujours True."""
    return True


def calculer_fin_op(t_debut: float, duree: float, poste: str = "") -> float:
    """Fin d'opération = début + durée (simple addition)."""
    return t_debut + duree


def temps_effectif_entre(t1: float, t2: float, poste: str = "") -> float:
    """Temps écoulé entre t1 et t2."""
    return max(0.0, t2 - t1)


def calculer_fin_manutention(t_fin_op: float, poste: str = "") -> float:
    """Fin de manutention = fin_op + 30 min."""
    return t_fin_op + TEMPS_MANUTENTION

# TYPES DE PANNEAUX


PANEL_TYPES = ["Sup AV", "Sup AR", "Inf AV", "Ar D", "Ar G", "Av D", "Av G"]
PANEL_INDEX = {p: i for i, p in enumerate(PANEL_TYPES)}

# POSTES ET MACHINES

MACHINES_PAR_POSTE = {
    "MV":           ["MV1", "MV2"],
    "STR_LISSES":   ["SL1", "SL2"],
    "PRECA_LISSES": ["PRECA_L"],
    "COMPL_LISSES": ["CL1", "CL2", "CARCAN"],  # CARCAN = alt. CL1/CL2 pour Ar D, Ar G
    "STR_CADRES":   ["SC1", "SC2", "BIS"],
    "PRECA_CADRES": ["PRECA_C"],
    "COMPL_CADRES": ["CC1", "CC2"],
    "FINITION":     ["FIN1", "FIN2", "FIN3", "FIN4",
                     "FIN5", "FIN6", "FIN7", "FIN8"],
}

MACHINE_VERS_POSTE = {
    m: poste
    for poste, machines in MACHINES_PAR_POSTE.items()
    for m in machines
}

ALL_MACHINES  = [m for ms in MACHINES_PAR_POSTE.values() for m in ms]
MACHINE_INDEX = {m: i for i, m in enumerate(ALL_MACHINES)}

# TEMPS OPÉRATOIRES (heures)


TEMPS_OPERATOIRES: dict[str, dict[str, float]] = {

    "MV1": {"Sup AV":  5.54, "Sup AR":  5.87, "Inf AV": 47.99,
            "Ar D":   61.27, "Ar G":   60.13, "Av D":   63.89, "Av G": 69.24},
    "MV2": {"Sup AV":  5.54, "Sup AR":  5.87, "Inf AV": 47.99,
            "Ar D":   61.27, "Ar G":   60.13, "Av D":   63.89, "Av G": 69.24},

    "SL1": {"Sup AV": 28.14, "Sup AR": 30.60, "Inf AV": 82.41,
            "Ar D":   51.02, "Ar G":   20.15, "Av D":   25.71, "Av G": 24.22},
    "SL2": {"Sup AV": 28.14, "Sup AR": 30.60, "Inf AV": 82.41,
            "Ar D":   51.02, "Ar G":   20.15, "Av D":   25.71, "Av G": 24.22},

    "PRECA_L": {"Sup AV": 23.60, "Sup AR": 22.02, "Inf AV": 19.07,
                "Ar D":    7.82, "Ar G":   10.37, "Av D":   22.48, "Av G": 21.17},

    "CL1": {"Sup AV": 25.83, "Sup AR": 61.00, "Inf AV": 36.91,
            "Ar D":   37.52, "Ar G":   49.55, "Av D":   28.40, "Av G": 26.74},
    "CL2": {"Sup AV": 25.83, "Sup AR": 61.00, "Inf AV": 36.91,
            "Ar D":   37.52, "Ar G":   49.55, "Av D":   28.40, "Av G": 26.74},

    "CARCAN": {"Ar D": 49.55, "Ar G": 49.55},

    "SC1": {"Sup AV":  28.91, "Sup AR":  59.37,
            "Ar D":   112.55, "Ar G":    67.72, "Av D":  83.61, "Av G": 78.75},
    "SC2": {"Sup AV":  28.91, "Sup AR":  59.37,
            "Ar D":   112.55, "Ar G":    67.72, "Av D":  83.61, "Av G": 78.75},

    "BIS": {"Sup AV":  28.91, "Sup AR":  59.37, "Inf AV": 58.71,
            "Ar G":    67.72, "Av D":    83.61, "Av G":   78.75},

    "PRECA_C": {"Sup AV": 6.00, "Sup AR": 5.06, "Inf AV": 3.26},

    "CC1": {"Sup AV": 15.99, "Sup AR": 16.96, "Inf AV": 100.00,
            "Ar D":   44.77, "Ar G":   54.25, "Av D":    48.11, "Av G": 45.32},
    "CC2": {"Sup AV": 15.99, "Sup AR": 16.96, "Inf AV": 100.00,
            "Ar D":   44.77, "Ar G":   54.25, "Av D":    48.11, "Av G": 45.32},
}

_TEMPS_FINITION = {
    "Sup AV":  56.90, "Sup AR":  86.67, "Inf AV": 108.85,
    "Ar D":    49.56, "Ar G":    48.12, "Av D":    59.20, "Av G": 65.96,
}
for _m in ["FIN1", "FIN2", "FIN3", "FIN4", "FIN5", "FIN6", "FIN7", "FIN8"]:
    TEMPS_OPERATOIRES[_m] = dict(_TEMPS_FINITION)

#  COMPATIBILITÉ MACHINE ↔ PANNEAU


def _build_compatibility() -> dict[str, dict[str, bool]]:
    compat: dict[str, dict[str, bool]] = {}
    for machine, durees in TEMPS_OPERATOIRES.items():
        compat[machine] = {pt: (pt in durees and durees[pt] > 0.0)
                           for pt in PANEL_TYPES}
    return compat

MACHINE_COMPATIBILITY: dict[str, dict[str, bool]] = _build_compatibility()


def get_machines_disponibles(poste: str, panel_type: str) -> list[str]:
    """Retourne les machines du poste compatibles avec le type de panneau."""
    return [m for m in MACHINES_PAR_POSTE[poste]
            if MACHINE_COMPATIBILITY.get(m, {}).get(panel_type, False)]

# ROUTING PAR TYPE DE PANNEAU


PANELS_AVEC_PRECA_CADRES = {"Sup AV", "Sup AR", "Inf AV"}


def get_route(panel_type: str) -> list[str]:
    """Retourne la séquence de postes pour un type de panneau."""
    route = ["MV", "STR_LISSES", "PRECA_LISSES", "COMPL_LISSES", "STR_CADRES"]
    if panel_type in PANELS_AVEC_PRECA_CADRES:
        route.append("PRECA_CADRES")
    route += ["COMPL_CADRES", "FINITION"]
    return route

# ACCESSEURS TEMPS

def get_temps(machine: str, panel_type: str) -> float:
    """Retourne la durée opératoire (0.0 si non défini ou non compatible)."""
    return TEMPS_OPERATOIRES.get(machine, {}).get(panel_type, 0.0)


def get_duree_totale_theorique(panel_type: str) -> float:
    """Durée théorique minimale = somme des meilleures machines par poste."""
    total = 0.0
    for poste in get_route(panel_type):
        machines = get_machines_disponibles(poste, panel_type)
        temps = [get_temps(m, panel_type) for m in machines if get_temps(m, panel_type) > 0]
        if temps:
            total += min(temps)
    return total


def get_duree_avec_manutention(panel_type: str) -> float:
    """Durée théorique + manutentions inter-postes."""
    n_postes = len(get_route(panel_type))
    return get_duree_totale_theorique(panel_type) + (n_postes - 1) * TEMPS_MANUTENTION

# STATUT

class Statut(Enum):
    EN_ATTENTE  = "en_attente"
    EN_COURS    = "en_cours"
    MANUTENTION = "manutention"
    STANDBY     = "standby"
    TERMINE     = "termine"

# ÉVÉNEMENT ALÉA

@dataclass
class EvenementAlea:
    t_occurrence      : float
    poste             : str
    machine           : str
    progression_pct   : float
    duree_deja_faite  : float
    duree_restante    : float
    duree_standby_est : float = 0.0
    t_retour_estime   : float = 0.0
    t_retour_reel     : Optional[float] = None

# CLASSE PANNEAU

class Panneau:
    _mgh_counter = 10000

    def __init__(self, panel_type: str, of_id: str,
                 release_date: float = 0.0, due_date: float = float('inf')):
        assert panel_type in PANEL_TYPES, f"Type inconnu : {panel_type}"
        assert release_date >= 0
        assert due_date > release_date

        Panneau._mgh_counter += 1
        self.mgh_id          = f"MGH{Panneau._mgh_counter}"
        self.panel_type      = panel_type
        self.of_id           = of_id
        self.release_date    = release_date
        self.due_date        = due_date
        self.route           = get_route(panel_type)

        self.statut           : Statut              = Statut.EN_ATTENTE
        self.op_courante      : int                 = 0
        self.machine_assignee : Optional[str]       = None
        self.debut_op         : Optional[float]     = None
        self.fin_op           : Optional[float]     = None
        self.fin_manutention  : Optional[float]     = None
        self._duree_effective : float               = 0.0
        self.historique       : list[dict]          = []
        self.alea             : Optional[EvenementAlea] = None

    @property
    def poste_courant(self) -> Optional[str]:
        if self.statut == Statut.TERMINE:
            return None
        return self.route[self.op_courante]

    @property
    def est_disponible(self) -> bool:
        return self.statut == Statut.EN_ATTENTE and self.machine_assignee is None

    @property
    def progression_globale(self) -> float:
        ops_finies = len([h for h in self.historique if not h["interrompu"]])
        return ops_finies / len(self.route)

    def machines_disponibles(self) -> list[str]:
        if self.statut == Statut.TERMINE:
            return []
        return get_machines_disponibles(self.poste_courant, self.panel_type)

    def duree_operation(self, machine: str) -> float:
        if self.alea is not None and self.statut == Statut.EN_ATTENTE:
            return self.alea.duree_restante
        return get_temps(machine, self.panel_type)

    def assigner_machine(self, machine: str, t_debut: float):
        assert self.est_disponible, f"{self.mgh_id} non disponible ({self.statut})"

       
        poste_machine = MACHINE_VERS_POSTE.get(machine, "")
        if poste_machine and self.route[self.op_courante] != poste_machine:
            for idx, poste in enumerate(self.route):
                if poste == poste_machine:
                    self.op_courante = idx
                    break

        duree = self.duree_operation(machine)
        fin   = calculer_fin_op(t_debut, duree)
        fin_m = calculer_fin_manutention(fin)

        self._duree_effective = duree
        self.statut           = Statut.EN_COURS
        self.machine_assignee = machine
        self.debut_op         = t_debut
        self.fin_op           = fin
        self.fin_manutention  = fin_m

    def terminer_operation(self):
        assert self.statut == Statut.EN_COURS
        self.statut = Statut.MANUTENTION

    def liberer_apres_manutention(self):
        assert self.statut == Statut.MANUTENTION
        self.historique.append({
            "poste"      : self.poste_courant,
            "machine"    : self.machine_assignee,
            "debut"      : self.debut_op,
            "fin"        : self.fin_op,
            "fin_manut"  : self.fin_manutention,
            "interrompu" : False,
        })
        self.alea             = None
        self._duree_effective = 0.0
        self.machine_assignee = None
        self.debut_op         = None
        self.fin_op           = None
        self.fin_manutention  = None
        self.op_courante     += 1
        self.statut = Statut.TERMINE if self.op_courante >= len(self.route) \
                      else Statut.EN_ATTENTE

    def declarer_alea(self, t_alea: float, duree_standby_estimee: float):
        assert self.statut == Statut.EN_COURS and self.debut_op is not None
        duree_faite    = temps_effectif_entre(self.debut_op, t_alea)
        duree_restante = max(0.0, self._duree_effective - duree_faite)
        progression    = duree_faite / self._duree_effective \
                         if self._duree_effective > 0 else 0.0
        t_retour_est   = t_alea + duree_standby_estimee

        self.alea = EvenementAlea(
            t_occurrence      = t_alea,
            poste             = self.poste_courant,
            machine           = self.machine_assignee,
            progression_pct   = round(progression, 4),
            duree_deja_faite  = round(duree_faite, 4),
            duree_restante    = round(duree_restante, 4),
            duree_standby_est = duree_standby_estimee,
            t_retour_estime   = round(t_retour_est, 4),
        )
        self.historique.append({
            "poste"     : self.poste_courant,
            "machine"   : self.machine_assignee,
            "debut"     : self.debut_op,
            "fin"       : t_alea,
            "fin_manut" : t_alea,
            "interrompu": True,
        })
        self.machine_assignee = None
        self.debut_op         = None
        self.fin_op           = None
        self.fin_manutention  = None
        self._duree_effective = 0.0
        self.statut           = Statut.STANDBY
        print(f"  [{self.mgh_id}] ALÉA t={t_alea:.2f}h — "
              f"{self.alea.poste} ({progression*100:.1f}% fait) — "
              f"reste {duree_restante:.2f}h — retour estimé t={t_retour_est:.2f}h")

    def remettre_en_ligne(self, t_retour: float):
        assert self.statut == Statut.STANDBY and self.alea is not None
        self.alea.t_retour_reel = t_retour
        self.statut = Statut.EN_ATTENTE
        print(f"  [{self.mgh_id}] RETOUR t={t_retour:.2f}h — "
              f"reste {self.alea.duree_restante:.2f}h sur {self.alea.poste}")

    def __repr__(self) -> str:
        s = self.statut.value.upper()
        if self.statut == Statut.STANDBY and self.alea:
            s += f" ({self.alea.progression_pct*100:.0f}%)"
        return (f"Panneau({self.mgh_id} | {self.panel_type} | "
                f"r={self.release_date:.0f}h d={self.due_date:.0f}h | {s})")

# ORDRE DE FABRICATION

class OrdreFabrication:
    _of_counter = 0

    def __init__(self, panel_type: str, quantite: int,
                 release_date: float = 0.0, due_date: float = float('inf')):
        assert panel_type in PANEL_TYPES
        assert quantite >= 1 and due_date > release_date
        OrdreFabrication._of_counter += 1
        self.of_id        = f"OF-{OrdreFabrication._of_counter:03d}"
        self.panel_type   = panel_type
        self.quantite     = quantite
        self.release_date = release_date
        self.due_date     = due_date
        self.panneaux     = [
            Panneau(panel_type, self.of_id, release_date, due_date)
            for _ in range(quantite)
        ]

    @property
    def est_complete(self) -> bool:
        return all(p.statut == Statut.TERMINE for p in self.panneaux)

# test 

if __name__ == "__main__":
    print("VALIDATION FJSP_data.py ")
    Panneau._mgh_counter = 10000
    OrdreFabrication._of_counter = 0

    # Test 1 : fonctions temps
    assert calculer_fin_op(0, 10)        == 10.0
    assert calculer_fin_manutention(10.) == 10.5
    assert temps_effectif_entre(3, 8)    == 5.0
    print("  ✓ Fonctions temps linéaires OK")

    # Test 2 : COMPL_LISSES — CARCAN uniquement pour Ar D et Ar G
    assert get_machines_disponibles("COMPL_LISSES", "Ar D") == ["CL1", "CL2", "CARCAN"]
    assert get_machines_disponibles("COMPL_LISSES", "Ar G") == ["CL1", "CL2", "CARCAN"]
    assert "CARCAN" not in get_machines_disponibles("COMPL_LISSES", "Sup AV")
    assert "CARCAN" not in get_machines_disponibles("COMPL_LISSES", "Inf AV")
    assert "CARCAN" not in get_machines_disponibles("COMPL_LISSES", "Av D")
    print("  ✓ CARCAN (COMPL_LISSES) — compatible Ar D et Ar G uniquement OK")

    # Test 3 : STR_CADRES
    assert get_machines_disponibles("STR_CADRES", "Inf AV") == ["BIS"]
    assert "BIS" not in get_machines_disponibles("STR_CADRES", "Ar D")
    assert "SC1" in get_machines_disponibles("STR_CADRES", "Ar D")
    assert "SC1" in get_machines_disponibles("STR_CADRES", "Sup AV")
    assert "BIS" in get_machines_disponibles("STR_CADRES", "Sup AV")
    print("  ✓ STR_CADRES (SC1/SC2/BIS) OK")

    # Test 4 : PRECA_CADRES
    assert get_machines_disponibles("PRECA_CADRES", "Sup AV") == ["PRECA_C"]
    assert get_machines_disponibles("PRECA_CADRES", "Ar D")   == []
    assert get_machines_disponibles("PRECA_CADRES", "Av D")   == []
    print("  ✓ PRECA_CADRES OK")

    # Test 5 : routing
    for pt in PANEL_TYPES:
        r = get_route(pt)
        assert "COMPL_LISSES" in r
        assert "STR_CADRES" in r
        if pt in {"Sup AV", "Sup AR", "Inf AV"}:
            assert "PRECA_CADRES" in r, f"{pt} doit avoir PRECA_CADRES"
        else:
            assert "PRECA_CADRES" not in r, f"{pt} ne doit pas avoir PRECA_CADRES"
    print("  ✓ Routing OK")

    # Test 6 : temps opératoires depuis tableau
    assert abs(get_temps("CARCAN", "Ar D")   - 49.55)  < 0.01
    assert abs(get_temps("CARCAN", "Ar G")   - 49.55)  < 0.01
    assert      get_temps("CARCAN", "Sup AV") == 0.0
    assert abs(get_temps("SC1",    "Ar D")   - 112.55) < 0.01
    assert abs(get_temps("SC1",    "Sup AV") - 28.91)  < 0.01
    assert abs(get_temps("BIS",    "Inf AV") - 58.71)  < 0.01
    assert      get_temps("BIS",   "Ar D")   == 0.0
    assert abs(get_temps("CL1",    "Ar D")   - 37.52)  < 0.01
    assert abs(get_temps("CL1",    "Ar G")   - 49.55)  < 0.01
    assert abs(get_temps("PRECA_C","Inf AV") - 3.26)   < 0.01
    print("  ✓ Temps opératoires OK")

    # Test 7 : assignation + aléa
    p = Panneau("Ar D", "OF-001", 0.0, 800.0)
    assert p.route == get_route("Ar D")
    assert "CARCAN" in get_machines_disponibles("COMPL_LISSES", "Ar D")
    p.assigner_machine("MV1", 0.0)
    assert abs(p.fin_op - 61.27) < 0.01
    p.declarer_alea(20.0, 10.0)
    assert abs(p.alea.duree_deja_faite - 20.0) < 0.01
    print(f"  ✓ Panneau Ar D — assignation + aléa OK")

    # Test 8 : durées théoriques
    print("\n  Durées théoriques par type :")
    for pt in PANEL_TYPES:
        d  = get_duree_avec_manutention(pt)
        nb = len(get_route(pt))
        mach_cl = get_machines_disponibles("COMPL_LISSES", pt)
        print(f"    {pt:<8}  {d:>7.1f}h   ({nb} postes)  COMPL_LISSES={mach_cl}")

    print(f"\n  Machines totales : {len(ALL_MACHINES)}")
    print("  VALIDATION OK — FJSP_data.py prêt")
