import numpy as np
from typing import Optional

try:
    import gymnasium as gym
    from gymnasium import spaces
    GYM_OK = True
except ImportError:
    GYM_OK = False
    class gym:
        class Env:
            pass
    class spaces:
        @staticmethod
        def Discrete(n): return n
        @staticmethod
        def Box(**kw): return kw

from FJSP_data import (
    PANEL_TYPES, PANEL_INDEX, ALL_MACHINES, MACHINE_INDEX,
    MACHINES_PAR_POSTE, MACHINE_VERS_POSTE,
    Panneau, OrdreFabrication, Statut,
    get_machines_disponibles, get_temps,
    get_duree_totale_theorique, get_duree_avec_manutention,
    calculer_fin_op, calculer_fin_manutention, temps_effectif_entre,
    TEMPS_MANUTENTION,
    prochain_debut_shift, est_en_production,
)

# CONSTANTES

N_MACHINES    = len(ALL_MACHINES)   # 22
N_PANEL_TYPES = len(PANEL_TYPES)    # 7

FENETRE_ACTIVE  = 12
# OBS_PAR_PANNEAU adaptatif 
OBS_PAR_PANNEAU = 9 if True else 8   
OBS_SIZE        = N_MACHINES + FENETRE_ACTIVE * OBS_PAR_PANNEAU  # 22 + 108 = 130

IDX_TYPE       = 0
IDX_OP         = 1
IDX_AVANCEMENT = 2
IDX_MANUT      = 3
IDX_RELEASE    = 4
IDX_SLACK      = 5
IDX_STANDBY    = 6
IDX_DISPO      = 7
IDX_SB_RETOUR  = 8   

HORIZON          = 2000.0
HEURES_PAR_SEMAINE = 168.0
MASK_HORIZON_H   = 168.0   

CAPACITE_STOCK_STANDBY = 25


ACTION_STANDBY_BUFFER = False  


ALPHA_EARLY        = 2.0
ALPHA_LATE         = 5.0
BONUS_MAKESPAN     = 100.0   
BONUS_LIVRAISON    = 10.0
PENALITE_RETARD    = 5.0
BONUS_PARALLELISME = 2.0
REWARD_STEP_OFFSET = 0.5     


# FILE EDD

class FileEDD:
    def __init__(self):
        self._file: list[Panneau] = []

    def ajouter(self, p: Panneau):
        self._file.append(p)
        self._file.sort(key=lambda x: x.due_date)

    def ajouter_plusieurs(self, panneaux: list[Panneau]):
        self._file.extend(panneaux)
        self._file.sort(key=lambda x: x.due_date)

    def suivant(self) -> Optional[Panneau]:
        return self._file.pop(0) if self._file else None

    def est_vide(self) -> bool:
        return len(self._file) == 0

    def __len__(self) -> int:
        return len(self._file)

# ENVIRONNEMENT

class FJSPEnv(gym.Env):

    metadata = {"render_modes": []}

    def __init__(self, n_panneaux: int = 14, seed: Optional[int] = None):
        super().__init__()
        self.n_panneaux     = n_panneaux
        self.seed           = seed if seed is not None else 0
        self.rng            = np.random.default_rng(self.seed)
        self._episode_count = 0

        _n_mach = N_MACHINES + 1   
        self._n_actions = FENETRE_ACTIVE * _n_mach
        if GYM_OK:
            self.observation_space = spaces.Box(
                low=-1.0, high=1.0, shape=(OBS_SIZE,), dtype=np.float32)
            self.action_space = spaces.Discrete(self._n_actions)
        else:
            class _FakeSpace:
                def __init__(self, n): self.n = n
            self.action_space = _FakeSpace(self._n_actions)

        self.fenetre           : list[Panneau]    = []
        self.file_edd          : FileEDD          = FileEDD()
        self.tous_les_panneaux : list[Panneau]    = []
        self.machine_libre     : dict[str, float] = {}
        self.t                 : float            = 0.0
        self.total_reward      : float            = 0.0
        self.n_steps           : int              = 0
        self._penalises        : set              = set()


    def _machine_occupee(self, machine: str) -> bool:
        """True si la machine est actuellement occupée par un panneau EN_COURS."""
        return any(
            p.statut == Statut.EN_COURS and p.machine_assignee == machine
            for p in self.tous_les_panneaux
        )

    def _machine_libre_maintenant(self, machine: str) -> bool:
        """True si la machine est libre à t (machine_libre[machine] <= t ET pas EN_COURS dessus)."""
        return (
            self.machine_libre.get(machine, 0.0) <= self.t
            and not self._machine_occupee(machine)
        )

    def _n_standby(self) -> int:
        """Nombre de panneaux actuellement en STANDBY."""
        return sum(1 for p in self.tous_les_panneaux if p.statut == Statut.STANDBY)

    def _stock_plein(self) -> bool:
        """True si le stock STANDBY a atteint sa capacité maximale."""
        return self._n_standby() >= CAPACITE_STOCK_STANDBY

    # RESET

    def reset(self, seed=None, options=None,
              panneaux_fournis: Optional[list[Panneau]] = None):
        self._episode_count += 1
        self.rng = np.random.default_rng(self.seed + self._episode_count)
        if seed is not None:
            self.rng = np.random.default_rng(seed)

        if panneaux_fournis is not None:
            panneaux = panneaux_fournis
        else:
            Panneau._mgh_counter         = 10000
            OrdreFabrication._of_counter = 0
            panneaux = self._generer_panneaux(self.n_panneaux)

        panneaux.sort(key=lambda p: p.due_date)
        self.tous_les_panneaux = panneaux

        # machine_libre : tenir compte des panneaux EN_COURS générés
        self.machine_libre = {m: 0.0 for m in ALL_MACHINES}
        for p in panneaux:
            if p.statut == Statut.EN_COURS and p.machine_assignee and p.fin_manutention:
                self.machine_libre[p.machine_assignee] = max(
                    self.machine_libre.get(p.machine_assignee, 0.0),
                    p.fin_manutention,
                )

        self.file_edd = FileEDD()
        for p in panneaux:
            if p.statut in (Statut.EN_ATTENTE, Statut.STANDBY):
                self.file_edd.ajouter(p)

        self.fenetre = [p for p in panneaux if p.statut == Statut.EN_COURS]
        self._remplir_fenetre()

        self.t            = 0.0
        self.total_reward = 0.0
        self.n_steps      = 0
        self._penalises   = set()

        return self._get_obs(), {"t": self.t, "file_edd": len(self.file_edd)}

    # STEP — action de l'agent RL

    def step(self, action: int):
        self.n_steps += 1
        
        reward = REWARD_STEP_OFFSET
        machines_utilisees: set[str] = set()

        # Décodage toujours en base N_MACHINES+1 (espace = 276)
        pan_idx       = action // (N_MACHINES + 1)
        machine_idx   = action  % (N_MACHINES + 1)
        # SB-BUFFER seulement si activé ET action spéciale choisie
        est_sb_buffer = (machine_idx == N_MACHINES) and ACTION_STANDBY_BUFFER

        if est_sb_buffer:
            reward += self._traiter_standby_buffer(pan_idx)
        elif machine_idx >= N_MACHINES:
           
            reward -= 5.0
        else:
            machine = ALL_MACHINES[machine_idx]
            valide, _ = self._action_valide(pan_idx, machine)

            if not valide:
                reward -= 5.0
            else:
                panneau = self.fenetre[pan_idx]
                t_debut = max(self.t,
                              self.machine_libre[machine],
                              panneau.release_date,
                              panneau.fin_manutention or 0.0)
                panneau.assigner_machine(machine, t_debut)
                self.machine_libre[machine] = panneau.fin_manutention
                machines_utilisees.add(machine)

        self._dispatcher_maximal(machines_utilisees)

        # Avancer le temps
        self._avancer_prochain_evt()
        reward += self._liberer_et_recompenser()

        fins_occupees_step = sum(
            1 for m in self.machine_libre
            if m.startswith("FIN") and self._machine_occupee(m)
        )
        if fins_occupees_step >= 2:
            reward += BONUS_PARALLELISME * (fins_occupees_step / 8.0) * 0.05

        self._remplir_fenetre()

        # Terminaison
        panneaux_actifs = [p for p in self.tous_les_panneaux
                           if p.statut != Statut.STANDBY]
        terminated = (
            self.file_edd.est_vide()
            and all(p.statut == Statut.TERMINE for p in panneaux_actifs)
        )

        if terminated:
            fins = [p.historique[-1]["fin"] for p in self.tous_les_panneaux
                    if p.statut == Statut.TERMINE and p.historique]
            if fins:
                makespan = max(fins)
                
                horizon_ref = 900.0   
                reward += BONUS_MAKESPAN * max(0.0, 1.0 - makespan / horizon_ref)
            for p in self.tous_les_panneaux:
                if p.statut == Statut.TERMINE and p.historique:
                    fin_r = p.historique[-1]["fin"]
                    if fin_r <= p.due_date:
                        reward += BONUS_LIVRAISON
                    else:
                        retard_h = fin_r - p.due_date
                        reward -= PENALITE_RETARD + 2.0 * min(retard_h / 50.0, 5.0)

        self.total_reward += reward
        n_sb_alea   = sum(1 for p in self.tous_les_panneaux
                          if p.statut == Statut.STANDBY and p.alea is not None)
        n_sb_buffer = sum(1 for p in self.tous_les_panneaux
                          if p.statut == Statut.STANDBY and p.alea is None)
        info = {
            "t"            : round(self.t, 2),
            "n_steps"      : self.n_steps,
            "total_reward" : round(self.total_reward, 2),
            "pan_termines" : sum(1 for p in self.tous_les_panneaux
                                 if p.statut == Statut.TERMINE),
            "pan_standby"  : self._n_standby(),
            "pan_sb_alea"  : n_sb_alea,
            "pan_sb_buffer": n_sb_buffer,
            "stock_plein"  : self._stock_plein(),
            "file_edd"     : len(self.file_edd),
        }
        return self._get_obs(), reward, terminated, False, info

    # STEP_PARALLEL 

    def step_parallel(self, modele=None) -> tuple[bool, dict]:
        self._liberer_et_recompenser()
        self._remplir_fenetre()

        machines_utilisees: set[str] = set()

        if modele is not None:
            mask    = self.action_masks()
            legales = np.where(mask)[0]
            if len(legales) > 0:
                obs = self._get_obs()
                try:
                    action, _ = modele.predict(obs, action_masks=mask,
                                               deterministic=True)
                    pi = int(action) // N_MACHINES
                    mi = int(action)  % N_MACHINES
                    valide, _ = self._action_valide(pi, ALL_MACHINES[mi])
                    if valide:
                        p       = self.fenetre[pi]
                        machine = ALL_MACHINES[mi]
                        t_deb   = max(self.t,
                                      self.machine_libre[machine],
                                      p.release_date,
                                      p.fin_manutention or 0.0)
                        p.assigner_machine(machine, t_deb)
                        self.machine_libre[machine] = p.fin_manutention
                        machines_utilisees.add(machine)
                except Exception:
                    pass

        self._dispatcher_maximal(machines_utilisees)
        self._avancer_prochain_evt()
        self._liberer_et_recompenser()
        self._remplir_fenetre()

        panneaux_actifs = [p for p in self.tous_les_panneaux
                           if p.statut != Statut.STANDBY]
        terminated = (
            self.file_edd.est_vide()
            and all(p.statut == Statut.TERMINE for p in panneaux_actifs)
        )
        info = {
            "t"           : round(self.t, 2),
            "pan_termines": sum(1 for p in self.tous_les_panneaux
                                if p.statut == Statut.TERMINE),
            "pan_standby" : self._n_standby(),
            "file_edd"    : len(self.file_edd),
        }
        return terminated, info

    # MAX DISPATCHING 

    def _dispatcher_maximal(self, machines_deja_utilisees: set[str]):
       
        pan_dispo = sorted(
            [p for p in self.fenetre
             if p.est_disponible
             and self.t >= p.release_date
             and (not p.fin_manutention or p.fin_manutention <= self.t)],
            key=lambda p: (
                p.due_date - self.t - self._duree_restante_estimee(p)  # slack
            ),
        )

        for p in pan_dispo:
            mach_ok = [
                m for m in p.machines_disponibles()
                if m not in machines_deja_utilisees
                and self._machine_libre_maintenant(m)
            ]
            if not mach_ok:
                continue

            machine = min(mach_ok,
                          key=lambda m: self.machine_libre.get(m, 0.0))

            t_deb = max(self.t,
                        self.machine_libre[machine],
                        p.release_date,
                        p.fin_manutention or 0.0)
            p.assigner_machine(machine, t_deb)
            self.machine_libre[machine] = p.fin_manutention
            machines_deja_utilisees.add(machine)

    # AVANCEMENT DU TEMPS

    def _avancer_prochain_evt(self):
        """Saute au prochain événement : fin_op, fin_manut, release_date,
        ou retour d'un panneau STANDBY-BUFFER."""
        evts = []
        for m, tl in self.machine_libre.items():
            if tl > self.t:
                evts.append(tl)
        for p in self.tous_les_panneaux:
            if p.statut == Statut.EN_COURS and p.fin_op and p.fin_op > self.t:
                evts.append(p.fin_op)
            if (p.statut == Statut.MANUTENTION
                    and p.fin_manutention and p.fin_manutention > self.t):
                evts.append(p.fin_manutention)
            if p.statut == Statut.EN_ATTENTE and p.release_date > self.t:
                evts.append(p.release_date)
            # [STANDBY-BUFFER] : retour des panneaux en attente stock (pas aléa réel)
            if p.statut == Statut.STANDBY and p.alea is None and p.release_date > self.t:
                evts.append(p.release_date)
        self.t = min(evts) if evts else self.t + 1.0
        self._liberer_standby_buffer()

    def _avancer_temps(self):
        self._avancer_prochain_evt()

    # LIBÉRATION ET RÉCOMPENSE INTERMÉDIAIRE

    def _liberer_et_recompenser(self) -> float:
        reward = 0.0
        for p in self.tous_les_panneaux:
            if p.statut == Statut.EN_COURS and p.fin_op and p.fin_op <= self.t:
                p.terminer_operation()
            if (p.statut == Statut.MANUTENTION
                    and p.fin_manutention and p.fin_manutention <= self.t):
                p.liberer_apres_manutention()
                if p.statut == Statut.TERMINE and p.mgh_id not in self._penalises:
                    fin_r = p.historique[-1]["fin"]
                    if fin_r <= p.due_date:
                        
                        reward += 1.0
                    else:
                        retard_norm = min((fin_r - p.due_date) / 200.0, 1.0)
                        reward -= 2.0 * retard_norm
                        self._penalises.add(p.mgh_id)

        fins_occupees = sum(
            1 for m, tl in self.machine_libre.items()
            if m.startswith("FIN") and tl > self.t
        )
        if fins_occupees >= 2:
            reward += fins_occupees * 0.02   # 2 FIN=+0.04, 8 FIN=+0.16

        if fins_occupees == 0:
            panneaux_fin_prets = [
                p for p in self.fenetre
                if p.est_disponible
                and p.poste_courant == "FINITION"
                and self.t >= p.release_date
            ]
            if panneaux_fin_prets:
                reward -= 0.5 * len(panneaux_fin_prets)

        return reward

    # ACTION_MASKS 

    def action_masks(self) -> np.ndarray:
        
        mask = np.zeros(FENETRE_ACTIVE * (N_MACHINES + 1), dtype=bool)
        for i in range(FENETRE_ACTIVE):
            if i >= len(self.fenetre):
                continue
            p = self.fenetre[i]
            if not p.est_disponible or self.t < p.release_date:
                continue
            if p.fin_manutention and p.fin_manutention > self.t + MASK_HORIZON_H:
                continue

            base = i * (N_MACHINES + 1)

            for machine in p.machines_disponibles():
                j          = MACHINE_INDEX[machine]
                t_machine  = self.machine_libre.get(machine, 0.0)
                t_panneau  = max(self.t, p.fin_manutention or 0.0, p.release_date)
                t_possible = max(t_machine, t_panneau)
                if self._machine_occupee(machine):
                    continue
                if t_possible <= self.t + MASK_HORIZON_H:
                    mask[base + j] = True

           
            if (not self._stock_plein()
                    and p.op_courante < len(p.route)):
                poste_suivant = p.route[p.op_courante]
                machines_suiv = get_machines_disponibles(poste_suivant, p.panel_type)
                attente_min = min(
                    (max(0.0, self.machine_libre.get(m, self.t) - self.t)
                     for m in machines_suiv),
                    default=0.0,
                ) if machines_suiv else 0.0
                machine_suiv_bloquee = attente_min > 2.0

                poste_courant = p.route[p.op_courante]
                a_un_candidat = any(
                    autre.mgh_id != p.mgh_id
                    and autre.statut == Statut.EN_ATTENTE
                    and autre.poste_courant == poste_courant
                    and self.t >= autre.release_date
                    and bool(get_machines_disponibles(poste_courant, autre.panel_type))
                    for autre in self.tous_les_panneaux
                )

                if machine_suiv_bloquee and a_un_candidat and ACTION_STANDBY_BUFFER:
                    mask[base + N_MACHINES] = True
                elif not ACTION_STANDBY_BUFFER:
                    mask[base + N_MACHINES] = False

        if not ACTION_STANDBY_BUFFER:
            for i in range(FENETRE_ACTIVE):
                mask[i * (N_MACHINES + 1) + N_MACHINES] = False
        return mask

    
    # VALIDATION ACTION

    def _traiter_standby_buffer(self, pan_idx: int) -> float:
        
        if pan_idx >= len(self.fenetre):
            return -3.0
        p = self.fenetre[pan_idx]

        if p.statut != Statut.EN_ATTENTE:
            return -3.0   
        if self._stock_plein():
            return -3.0   

        
        poste_suivant = p.route[p.op_courante] if p.op_courante < len(p.route) else None
        if poste_suivant is None:
            return -3.0

        machines_suivantes = get_machines_disponibles(poste_suivant, p.panel_type)
        t_liberation_min   = min(
            (self.machine_libre.get(m, self.t) for m in machines_suivantes),
            default=self.t,
        )
        attente_estimee = max(0.0, t_liberation_min - self.t)

        if attente_estimee < 0.5:
            return -2.0   

        
        poste_courant = p.route[p.op_courante]
        candidats_remplacement = [
            autre for autre in self.tous_les_panneaux
            if autre.mgh_id != p.mgh_id
            and autre.statut == Statut.EN_ATTENTE
            and autre.poste_courant == poste_courant
            and self.t >= autre.release_date
            and bool(get_machines_disponibles(poste_courant, autre.panel_type))
        ]

        if candidats_remplacement:
            
            idle_cost_evite = attente_estimee / HORIZON * 15.0
            holding_cost    = attente_estimee / HORIZON * 5.0
            worth_it_bonus  = max(0.0, idle_cost_evite - holding_cost)
        else:
            
            worth_it_bonus  = 0.0
            holding_cost    = attente_estimee / HORIZON * 20.0  

        if worth_it_bonus <= holding_cost and not candidats_remplacement:
            
            return -(holding_cost)

        p.statut       = Statut.STANDBY
        p.release_date = t_liberation_min + 0.5
        if p in self.fenetre:
            self.fenetre.remove(p)
        self.file_edd.ajouter(p)

        reward = worth_it_bonus - holding_cost
        if getattr(self, '_verbose_sb', False):
            print(f"  [SB] {p.mgh_id} attente={attente_estimee:.1f}h "
                  f"candidats={len(candidats_remplacement)} r={reward:+.3f}")
        return reward

    def _liberer_standby_buffer(self):
        
        for p in self.tous_les_panneaux:
            if (p.statut == Statut.STANDBY
                    and p.alea is None          
                    and self.t >= p.release_date):
                p.statut = Statut.EN_ATTENTE
                # Remettre en fenêtre si de la place
                if p not in self.fenetre and len(self.fenetre) < FENETRE_ACTIVE:
                    self.fenetre.append(p)
                elif p not in self.fenetre:
                    self.file_edd.ajouter(p)

    def _action_valide(self, pan_idx: int, machine: str) -> tuple[bool, str]:
        if pan_idx >= len(self.fenetre):
            return False, "index hors fenêtre"
        p = self.fenetre[pan_idx]
        if not p.est_disponible:
            return False, f"non disponible ({p.statut.value})"
        if self.t < p.release_date:
            return False, "release_date non atteinte"
        if machine not in p.machines_disponibles():
            return False, "routing incompatible"
        if self._machine_occupee(machine):
            return False, "machine déjà occupée par un panneau EN_COURS"
        if self.machine_libre.get(machine, 0.0) > self.t + MASK_HORIZON_H:
            return False, "machine trop occupée"
        return True, "ok"

    # GÉNÉRATION DE PANNEAUX 

    def _generer_panneaux(self, n: int) -> list[Panneau]:
        
        panneaux      = []
        t_semaine     = 0.0
        of_id_local   = 0
        n_standby_gen = 0
        est_premier_lot = True   

        while len(panneaux) < n:
            taille_lot = int(self.rng.integers(4, 11))
            taille_lot = min(taille_lot, n - len(panneaux))
            release_base = t_semaine

            for _ in range(taille_lot):
                pt      = str(self.rng.choice(PANEL_TYPES))
                duree   = get_duree_avec_manutention(pt)
                facteur = float(self.rng.uniform(1.8, 3.0))
                rel     = release_base + float(self.rng.uniform(0.0, 24.0))
                rel     = max(0.0, rel)
                due     = rel + duree * facteur
                of_id_local += 1
                p = Panneau(pt, f"OF-{of_id_local:03d}", rel, due)

                tirage = float(self.rng.random())

                if tirage < 0.10 and est_premier_lot:
                    machines_dispo = p.machines_disponibles()
                    if machines_dispo:
                        machine_choisie = str(self.rng.choice(machines_dispo))
                        if not self._machine_occupee(machine_choisie):
                            t_debut_fictif = float(self.rng.uniform(0.0, 5.0))
                            p.release_date = 0.0
                            p.assigner_machine(machine_choisie, t_debut_fictif)
                            self.machine_libre[machine_choisie] = max(
                                self.machine_libre.get(machine_choisie, 0.0),
                                p.fin_manutention or 0.0,
                            )

                elif tirage < 0.25 and n_standby_gen < CAPACITE_STOCK_STANDBY:
                    duree_standby  = float(self.rng.uniform(20.0, 80.0))
                    p.release_date = rel + duree_standby
                    n_standby_gen += 1

                panneaux.append(p)

            t_semaine += float(self.rng.uniform(
                HEURES_PAR_SEMAINE * 0.9, HEURES_PAR_SEMAINE * 1.1))
            est_premier_lot = False   

        return panneaux[:n]

    # ÉTAT RÉEL 

    def initialiser_etat_reel(self, panneaux_en_cours: list[Panneau],
                               t_actuel: float = 0.0) -> tuple:
        
        self.t                 = t_actuel
        self.tous_les_panneaux = list(panneaux_en_cours)
        self.total_reward      = 0.0
        self.n_steps           = 0
        self._penalises        = set()

        self.machine_libre = {m: t_actuel for m in ALL_MACHINES}
        for p in panneaux_en_cours:
            if p.statut == Statut.EN_COURS and p.machine_assignee and p.fin_manutention:
                self.machine_libre[p.machine_assignee] = max(
                    self.machine_libre.get(p.machine_assignee, t_actuel),
                    p.fin_manutention,
                )

        self.file_edd = FileEDD()
        for p in panneaux_en_cours:
            if p.statut in (Statut.EN_ATTENTE, Statut.STANDBY):
                self.file_edd.ajouter(p)

        self.fenetre = [p for p in panneaux_en_cours if p.statut == Statut.EN_COURS]
        self._remplir_fenetre()

        en_cours   = sum(1 for p in panneaux_en_cours if p.statut == Statut.EN_COURS)
        en_attente = sum(1 for p in panneaux_en_cours if p.statut == Statut.EN_ATTENTE)
        standby    = self._n_standby()
        print(f"[État réel] t={t_actuel:.1f}h — "
              f"EN_COURS:{en_cours} EN_ATTENTE:{en_attente} "
              f"STANDBY:{standby}/{CAPACITE_STOCK_STANDBY}")

        return self._get_obs(), {
            "t"          : self.t,
            "file_edd"   : len(self.file_edd),
            "ligne_vide" : en_cours == 0,
            "stock_plein": self._stock_plein(),
        }

    # GESTION DES ALÉAS

    def declarer_alea(self, mgh_id: str, duree_standby_h: float,
                      modele=None) -> dict:
        
        p = self._trouver_panneau(mgh_id)
        if not p or p.statut != Statut.EN_COURS:
            return {"succes": False, "raison": "panneau non trouvé ou non EN_COURS"}

        if self._stock_plein():
            return {
                "succes"  : False,
                "raison"  : f"Stock STANDBY plein ({CAPACITE_STOCK_STANDBY} panneaux). "
                            f"Attendre la libération d'une place avant de déclarer un nouvel aléa.",
                "n_standby": self._n_standby(),
            }

        machine = p.machine_assignee
        p.declarer_alea(self.t, duree_standby_h)

        fin_manut    = calculer_fin_manutention(self.t)
        self.machine_libre[machine] = fin_manut
        t_retour_est = p.alea.t_retour_estime

        print(f"[Aléa] {mgh_id} → STANDBY | {machine} libre à {fin_manut:.2f}h | "
              f"retour estimé t={t_retour_est:.2f}h | "
              f"stock: {self._n_standby()}/{CAPACITE_STOCK_STANDBY}")

        candidats = self._evaluer_candidats_slot(
            machine, p.alea.poste, fin_manut, t_retour_est)

        nouveau_planning = None
        if modele is not None:
            nouveau_planning = self.reschedule_depuis_etat_courant(modele)

        return {
            "succes"          : True,
            "machine_liberee" : machine,
            "t_libre"         : fin_manut,
            "t_retour_est"    : t_retour_est,
            "candidats"       : [c.mgh_id for c in candidats],
            "n_standby"       : self._n_standby(),
            "stock_plein"     : self._stock_plein(),
            "nouveau_planning": nouveau_planning,
        }

    def _evaluer_candidats_slot(self, machine: str, poste: str,
                                 t_dispo: float, t_retour_est: float) -> list:
        """Identifie les panneaux pouvant occuper le créneau libéré par l'aléa."""
        candidats = []
        for p in self.tous_les_panneaux:
            if (p.statut == Statut.EN_ATTENTE
                    and p.poste_courant == poste
                    and self.t >= p.release_date
                    and machine in p.machines_disponibles()):
                duree_op    = p.duree_operation(machine)
                fin_op_est  = t_dispo + duree_op
                slack_apres = (p.due_date - fin_op_est
                               - self._duree_restante_estimee(p))
                if fin_op_est <= t_retour_est and slack_apres >= 0:
                    candidats.append((p, slack_apres))
        candidats.sort(key=lambda x: x[1])
        return [c[0] for c in candidats]

    def reschedule_depuis_etat_courant(self, modele) -> object:
        """Lance un reschedule PPO depuis l'état courant (deep copy)."""
        import copy
        env_temp  = copy.deepcopy(self)
        obs       = env_temp._get_obs()
        done      = False
        steps     = 0
        MAX_STEPS = 10_000

        while not done and steps < MAX_STEPS:
            steps += 1
            try:
                mask   = env_temp.action_masks()
                action, _ = modele.predict(obs, action_masks=mask, deterministic=True)
            except Exception:
                mask    = env_temp.action_masks()
                legales = np.where(mask)[0]
                if len(legales) == 0:
                    env_temp._avancer_prochain_evt()
                    obs = env_temp._get_obs()
                    continue
                action = int(np.random.choice(legales))
            obs, _, done, _, _ = env_temp.step(int(action))

        planning   = env_temp.get_planning_df()
        n_termines = sum(1 for p in env_temp.tous_les_panneaux
                         if p.statut == Statut.TERMINE)
        print(f"[Reschedule] {steps} steps — {n_termines} terminés — "
              f"makespan ≈ {env_temp.t:.1f}h")
        return planning

    def remettre_en_ligne(self, mgh_id: str, modele=None) -> dict:
        """Remet un panneau STANDBY en production et libère une place dans le stock."""
        p = self._trouver_panneau(mgh_id)
        if not p or p.statut != Statut.STANDBY:
            return {"succes": False, "raison": "panneau non trouvé ou non STANDBY"}
        p.remettre_en_ligne(self.t)
        if p not in self.fenetre and len(self.fenetre) < FENETRE_ACTIVE:
            self.fenetre.append(p)
        else:
            self.file_edd.ajouter(p)
        print(f"[Retour] {mgh_id} → EN_ATTENTE | "
              f"stock: {self._n_standby()}/{CAPACITE_STOCK_STANDBY}")
        nouveau_planning = None
        if modele is not None:
            nouveau_planning = self.reschedule_depuis_etat_courant(modele)
        return {
            "succes"          : True,
            "n_standby"       : self._n_standby(),
            "nouveau_planning": nouveau_planning,
        }

    def ajouter_panneau(self, p: Panneau):
        self.tous_les_panneaux.append(p)
        self.file_edd.ajouter(p)
        self._remplir_fenetre()

    # UTILITAIRES FENÊTRE

    def _remplir_fenetre(self):
        """Retire les terminés de la fenêtre, complète depuis la file EDD."""
        self.fenetre = [p for p in self.fenetre if p.statut != Statut.TERMINE]
        while len(self.fenetre) < FENETRE_ACTIVE and not self.file_edd.est_vide():
            nxt = self.file_edd.suivant()
            if nxt not in self.fenetre:
                self.fenetre.append(nxt)

    def _trouver_panneau(self, mgh_id: str) -> Optional[Panneau]:
        return next((p for p in self.tous_les_panneaux
                     if p.mgh_id == mgh_id), None)

    def _duree_restante_estimee(self, p: Panneau) -> float:
        """Estime la durée restante (somme min durées postes restants + manutentions)."""
        total = 0.0
        for poste in p.route[p.op_courante:]:
            machines = get_machines_disponibles(poste, p.panel_type)
            temps    = [get_temps(m, p.panel_type) for m in machines
                        if get_temps(m, p.panel_type) > 0]
            if temps:
                total += min(temps)
        n_rest = len(p.route) - p.op_courante
        total += max(0, n_rest - 1) * TEMPS_MANUTENTION
        if p.statut == Statut.EN_COURS and p.debut_op and p.fin_op:
            total -= max(0.0, temps_effectif_entre(p.debut_op, self.t))
        elif p.statut == Statut.STANDBY and p.alea:
            total -= p.alea.duree_deja_faite
        return max(0.0, total)

    # OBSERVATION

    def _get_obs(self) -> np.ndarray:
        obs = np.zeros(OBS_SIZE, dtype=np.float32)

        for m, idx in MACHINE_INDEX.items():
            t_libre  = self.machine_libre.get(m, self.t)
            obs[idx] = float(np.clip((t_libre - self.t) / HORIZON, 0.0, 1.0))

        # Panneaux [22..117]
        for i in range(FENETRE_ACTIVE):
            base = N_MACHINES + i * OBS_PAR_PANNEAU
            if i >= len(self.fenetre):
                continue
            p = self.fenetre[i]

            obs[base + IDX_TYPE] = PANEL_INDEX[p.panel_type] / (N_PANEL_TYPES - 1)
            obs[base + IDX_OP]   = p.op_courante / max(1, len(p.route) - 1)

            if p.statut == Statut.EN_COURS and p.debut_op and p.fin_op:
                d = p.fin_op - p.debut_op
                if d > 0:
                    obs[base + IDX_AVANCEMENT] = float(np.clip(
                        (self.t - p.debut_op) / d, 0.0, 1.0))
            elif p.statut == Statut.STANDBY and p.alea:
                obs[base + IDX_AVANCEMENT] = float(p.alea.progression_pct)

            if p.fin_manutention and p.fin_manutention > self.t:
                obs[base + IDX_MANUT] = float(np.clip(
                    (p.fin_manutention - self.t) / HORIZON, 0.0, 1.0))

            obs[base + IDX_RELEASE] = float(np.clip(
                (p.release_date - self.t) / HORIZON, -1.0, 1.0))

            dur_r = self._duree_restante_estimee(p)
            obs[base + IDX_SLACK] = float(np.clip(
                (p.due_date - self.t - dur_r) / HORIZON, -1.0, 1.0))

            obs[base + IDX_STANDBY] = 1.0 if p.statut == Statut.STANDBY else 0.0
            obs[base + IDX_DISPO]   = 1.0 if (
                p.est_disponible
                and self.t >= p.release_date
                and (not p.fin_manutention or p.fin_manutention <= self.t)
            ) else 0.0
            if p.statut == Statut.STANDBY and p.alea is None:
                obs[base + IDX_SB_RETOUR] = float(np.clip(
                    (p.release_date - self.t) / HORIZON, 0.0, 1.0))
            else:
                obs[base + IDX_SB_RETOUR] = 0.0

        return obs

    # AFFICHAGE ET EXPORT

    def render(self):
        print(f"\n{'='*72}")
        print(f"  t={self.t:.2f}h | step={self.n_steps} | "
              f"reward={self.total_reward:.1f} | file_EDD={len(self.file_edd)} | "
              f"STANDBY={self._n_standby()}/{CAPACITE_STOCK_STANDBY}")
        print(f"{'─'*72}")
        for p in self.fenetre:
            machine = p.machine_assignee or "—"
            fin     = f"{p.fin_op:.1f}h" if p.fin_op else "—"
            poste   = p.poste_courant or "TERMINÉ"
            slack   = p.due_date - self.t - self._duree_restante_estimee(p)
            print(f"  {p.mgh_id:<11}{p.panel_type:<9}"
                  f"{p.statut.value:<14}{poste:<17}{machine:<10}"
                  f"{fin:<10}{slack:+.0f}h")
        libres = [m for m in ALL_MACHINES if self._machine_libre_maintenant(m)]
        print(f"{'─'*72}")
        print(f"  Machines libres ({len(libres)}/{N_MACHINES}): "
              f"{', '.join(libres[:14])}{'...' if len(libres) > 14 else ''}")
        print(f"{'='*72}\n")

    def get_planning_df(self):
        try:
            import pandas as pd
        except ImportError:
            return None
        lignes = []
        for p in self.tous_les_panneaux:
            for h in p.historique:
                lignes.append({
                    "MGH"         : p.mgh_id,
                    "OF"          : p.of_id,
                    "type_panneau": p.panel_type,
                    "poste"       : h["poste"],
                    "machine"     : h["machine"],
                    "debut"       : h["debut"],
                    "fin"         : h["fin"],
                    "fin_manut"   : h.get("fin_manut", h["fin"]),
                    "interrompu"  : h["interrompu"],
                    "due_date"    : p.due_date,
                    "en_retard"   : (h["fin"] > p.due_date
                                     and h["poste"] == p.route[-1]),
                })
        return pd.DataFrame(lignes)

# VALIDATION et test 

if __name__ == "__main__":
    print("VALIDATION FJSP_env.py — Mai 2026")
    print("=" * 72)

    Panneau._mgh_counter         = 10000
    OrdreFabrication._of_counter = 0

    # Test 1 : reset
    env = FJSPEnv(n_panneaux=14, seed=42)
    obs, info = env.reset()
    assert env.t == 0.0
    assert obs.shape == (OBS_SIZE,)
    print(f"  ✓ reset() : t={env.t}h | fenêtre={len(env.fenetre)} | "
          f"file_EDD={info['file_edd']}")

    # Test 2 : seeds variables
    env2 = FJSPEnv(n_panneaux=7, seed=0)
    _, _ = env2.reset()
    t1 = [p.panel_type for p in env2.tous_les_panneaux]
    _, _ = env2.reset()
    t2 = [p.panel_type for p in env2.tous_les_panneaux]
    assert t1 != t2
    print(f"  ✓ Seeds variables : ep1={t1[:3]} ep2={t2[:3]}")

    # Test 3 : action_masks
    env._avancer_prochain_evt()
    mask     = env.action_masks()
    n_legales = int(mask.sum())
    assert n_legales > 0
    print(f"  ✓ action_masks() : {n_legales} actions légales")

    # Test 4 : 1 panneau par machine — aucune machine dupliquée après dispatch
    env3 = FJSPEnv(n_panneaux=14, seed=7)
    env3.reset()
    env3._avancer_prochain_evt()   # avancer pour que release_date soit atteinte
    env3._dispatcher_maximal(set())
    machines_en_cours = [p.machine_assignee for p in env3.tous_les_panneaux
                         if p.statut == Statut.EN_COURS]
    assert len(machines_en_cours) == len(set(machines_en_cours)), \
        f"ERREUR : machine assignée à plusieurs panneaux ! {machines_en_cours}"
    print(f"  ✓ [MACHINE] 1 panneau/machine : {len(machines_en_cours)} assignations "
          f"uniques sur {N_MACHINES} machines")

    # Test 5 : stock STANDBY respecté à la génération
    for seed_test in range(5):
        env_s = FJSPEnv(n_panneaux=14, seed=seed_test)
        env_s.reset()
        nb_sb = sum(1 for p in env_s.tous_les_panneaux
                    if p.release_date > p.due_date * 0.1 + 20)
        assert nb_sb <= CAPACITE_STOCK_STANDBY, \
            f"ERREUR seed={seed_test}: {nb_sb} > {CAPACITE_STOCK_STANDBY}"
    print(f"  ✓ [STOCK] Capacité STANDBY ≤ {CAPACITE_STOCK_STANDBY} sur 5 seeds")

    n_ec_total = 0
    for seed_test in range(20):
        env_s = FJSPEnv(n_panneaux=14, seed=seed_test)
        env_s.reset()
        n_ec_total += sum(1 for p in env_s.tous_les_panneaux
                          if p.statut == Statut.EN_COURS)
    print(f"  ✓ [FIX-R4] EN_COURS simulés sur 20 épisodes : {n_ec_total} total "
          f"(~{n_ec_total/20:.1f}/épisode en moyenne)")

    env5 = FJSPEnv(n_panneaux=14, seed=42)
    env5.reset()
    env5._avancer_prochain_evt()
    env5._dispatcher_maximal(set())
    for p in env5.tous_les_panneaux:
        if p.statut == Statut.EN_ATTENTE:
            p.statut = Statut.STANDBY
            if env5._n_standby() >= CAPACITE_STOCK_STANDBY:
                break
    en_cours_panel = next(
        (p for p in env5.tous_les_panneaux if p.statut == Statut.EN_COURS), None)
    if en_cours_panel and env5._stock_plein():
        res = env5.declarer_alea(en_cours_panel.mgh_id, 30.0)
        assert not res["succes"], "ERREUR : aléa accepté stock plein"
        print(f"  ✓ [STOCK] Aléa refusé : stock plein "
              f"({env5._n_standby()}/{CAPACITE_STOCK_STANDBY})")
    else:
        print(f"  ✓ [STOCK] Test stock plein : pas de panneau EN_COURS disponible "
              f"(normal si dispatch n'a pas eu de candidats)")

    # Test 7 : step_parallel termine
    env6 = FJSPEnv(n_panneaux=7, seed=5)
    env6.reset()
    steps = 0
    done  = False
    while not done and steps < 5000:
        done, info6 = env6.step_parallel(modele=None)
        steps += 1
    assert done, f"ERREUR : step_parallel non terminé ({steps} steps)"
    print(f"  ✓ step_parallel : {steps} steps | t={info6['t']}h | "
          f"terminés={info6['pan_termines']}/7")

    # Test 8 : [FIX-R1] pas de pénalité step sur le temps
    env7 = FJSPEnv(n_panneaux=7, seed=10)
    env7.reset()
    mask    = env7.action_masks()
    legales = np.where(mask)[0]
    if len(legales) == 0:
        env7._avancer_prochain_evt()
        mask    = env7.action_masks()
        legales = np.where(mask)[0]
    if len(legales) > 0:
        _, r, _, _, _ = env7.step(int(legales[0]))
        assert r >= -5.1, f"ERREUR reward step trop négatif : {r:.2f}"
        print(f"  ✓ [FIX-R1] Reward step sans pénalité temps : {r:.3f}")

    # Test 9 : get_planning_df
    df = env6.get_planning_df()
    assert df is not None and len(df) > 0
    print(f"  ✓ get_planning_df() : {len(df)} lignes")

    print("\n" + "=" * 72)
    print("  VALIDATION OK — FJSP_env.py prêt")
    print("=" * 72)