from contraints import *
import random
import copy
from collections import defaultdict


class Problem:
    pass


class EnsiaProblem(Problem):
    def __init__(self, dataset, cspmethod="global_search"):
        super().__init__()

        data = self.load_data(dataset)
        self.rooms  = data[0]
        self.events = data[3]
        self.groups = data[2]

        self.section_to_group = {section["id"]: [] for section in data[1]}
        for group in self.groups:
            self.section_to_group[group["section_id"]].append(group["id"])

        self.events_by_id = {e["id"]: e for e in self.events}
        self.rooms_by_id  = {r["id"]: r for r in self.rooms}
        self.groups_by_id = {g["id"]: g for g in self.groups}

        # (room_id, slot_index) pairs — slot_index 0-29
        self.slots = [(r["id"], t) for r in self.rooms for t in range(30)]

        self.hard_constraints_list = data[4].get("hard", [])
        self.soft_constraints_list = data[4].get("soft", [])
        self.constraint_obj        = Constraints(self)

        if cspmethod == "local_search":
            state = self.generate_random_state()
            self.state = self.enhance(state)
        else:
            if cspmethod != "global_search":
                print("invalid csp method, redirecting to GS csp ...\n")
            self.state = self.generate_valid_state()

    # ------------------------------------------------------------------ #
    #  Data loading                                                        #
    # ------------------------------------------------------------------ #

    def load_data(self, filename):
        import json, os
        if not os.path.exists(filename):
            raise FileNotFoundError(f"Dataset file '{filename}' not found.")
        with open(filename, 'r', encoding='utf-8') as f:
            raw = json.load(f)
        return [
            raw.get("rooms",       []),
            raw.get("sections",    []),
            raw.get("groups",      []),
            raw.get("activities",  []),
            raw.get("constraints", {}),
        ]

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    def _get_event_groups(self, event):
        """Return the list of group IDs that attend this event."""
        if event["type_id"] == 1:
            return self.section_to_group[event["target_id"]]
        return [event["target_id"]]

    # ------------------------------------------------------------------ #
    #  CSP — Global (backtracking + forward checking)                     #
    # ------------------------------------------------------------------ #

    def _precompute_neighbours(self, event_ids):
        """
        Two events are neighbours if they share a teacher, a student group,
        or the same course (so scheduling rules between them matter).
        """
        teacher_map = defaultdict(set)
        group_map   = defaultdict(set)
        course_map  = defaultdict(set)

        for eid in event_ids:
            e = self.events_by_id[eid]
            teacher_map[e["teacher_id"]].add(eid)
            course_map[e["course_name"]].add(eid)
            for gid in self._get_event_groups(e):
                group_map[gid].add(eid)

        neighbours = {eid: set() for eid in event_ids}
        for eid in event_ids:
            e = self.events_by_id[eid]
            neighbours[eid] |= teacher_map[e["teacher_id"]]
            neighbours[eid] |= course_map[e["course_name"]]
            for gid in self._get_event_groups(e):
                neighbours[eid] |= group_map[gid]
            neighbours[eid].discard(eid)

        return neighbours

    def _build_initial_domain(self, event_id):
        compat_rooms = self.event_compatible_rooms[event_id]
        return {(r, s) for r in compat_rooms for s in range(30)}

    def _removed_by_assignment(self, assigned_eid, roomid, slot,
                                unassigned_set, neighbours):
        """
        Forward-checking: return {neighbour_eid: set_of_(room,slot)_to_remove}.
        Only prunes values that provably violate a hard constraint.
        """
        ae          = self.events_by_id[assigned_eid]
        a_teacher   = ae["teacher_id"]
        a_groups    = set(self._get_event_groups(ae))
        a_course    = ae["course_name"]
        a_is_lec    = (ae["type_id"] == 1)
        a_section   = ae["target_id"] if a_is_lec else None
        a_day       = slot // 6

        removals = {}

        for neid in neighbours[assigned_eid]:
            if neid not in unassigned_set:
                continue

            ne        = self.events_by_id[neid]
            n_teacher = ne["teacher_id"]
            n_groups  = set(self._get_event_groups(ne))
            n_course  = ne["course_name"]
            n_is_lec  = (ne["type_id"] == 1)
            n_section = ne["target_id"] if n_is_lec else None

            shared_grps  = a_groups & n_groups
            same_course  = (n_course == a_course)
            # FIX: consecutive-lecture rule only applies when BOTH lectures
            # belong to the SAME section (same target_id).
            same_section = (a_is_lec and n_is_lec and a_section == n_section)

            to_remove = set()

            for (nr, ns) in self._domains[neid]:
                nday  = ns // 6
                ntime = ns % 6
                bad   = False

                # Hard: no room double-booking
                if nr == roomid and ns == slot:
                    bad = True

                # Hard: no teacher double-booking
                elif n_teacher == a_teacher and ns == slot:
                    bad = True

                # Hard: no group double-booking
                elif shared_grps and ns == slot:
                    bad = True

                elif same_course and shared_grps:
                    # Lecture + practice of same course & shared groups
                    # cannot be on the same day
                    if a_is_lec != n_is_lec:
                        if nday == a_day:
                            bad = True
                    # Two lectures of the SAME section must be consecutive
                    elif same_section:
                        adj = set()
                        for candidate in (slot - 1, slot + 1):
                            if candidate // 6 == a_day and 0 <= candidate % 6 < 6:
                                adj.add(candidate)
                        if ns not in adj:
                            bad = True

                # Hard: no group has > 3 consecutive slots in one day
                if not bad and shared_grps and nday == a_day:
                    for gid in shared_grps:
                        times_set = self.group_day_times[gid][a_day]
                        if len(times_set) >= 3:
                            ts = sorted(times_set | {ntime})
                            run = max_run = 1
                            for k in range(1, len(ts)):
                                run = run + 1 if ts[k] == ts[k-1] + 1 else 1
                                max_run = max(max_run, run)
                            if max_run > 3:
                                bad = True
                                break

                if bad:
                    to_remove.add((nr, ns))

            if to_remove:
                removals[neid] = to_remove

        return removals

    def _bt(self, unassigned_set, state, neighbours):
        """Recursive backtracking with MRV + forward checking."""
        if not unassigned_set:
            return state if self.is_consistent(state, is_complete=True) else None

        # MRV: pick the event with the smallest remaining domain
        mrv_eid = min(unassigned_set, key=lambda e: len(self._domains[e]))
        if not self._domains[mrv_eid]:
            return None

        unassigned_set.remove(mrv_eid)
        event      = self.events_by_id[mrv_eid]
        teacher_id = event["teacher_id"]
        groups     = self._get_event_groups(event)

        candidates = list(self._domains[mrv_eid])
        random.shuffle(candidates)

        for roomid, slot in candidates:
            day  = slot // 6
            time = slot % 6

            # Tentative assignment
            state[mrv_eid] = (roomid, slot)
            self.busy_rooms.add((roomid, slot))
            self.busy_teachers.add((teacher_id, slot))
            for gid in groups:
                self.busy_groups.add((gid, slot))
                self.group_day_times[gid][day].add(time)

            # Neighbour-based forward checking (teacher, group, course rules)
            removals = self._removed_by_assignment(
                mrv_eid, roomid, slot, unassigned_set, neighbours)

            # FIX: also prune (roomid, slot) from ALL unassigned events regardless
            # of neighbour relationship — two unrelated events can still clash in
            # the same room at the same time, and _removed_by_assignment only
            # iterates over neighbours so it would miss this.
            room_slot_pair = (roomid, slot)
            for neid in unassigned_set:
                if room_slot_pair in self._domains[neid]:
                    if neid in removals:
                        removals[neid].add(room_slot_pair)
                    else:
                        removals[neid] = {room_slot_pair}

            # Use set-difference to detect wipeout accurately
            wipeout = any(
                len(self._domains[n] - rm) == 0
                for n, rm in removals.items()
            )

            if not wipeout:
                for n, rm in removals.items():
                    self._domains[n] -= rm

                result = self._bt(unassigned_set, state, neighbours)
                if result is not None:
                    return result

                # Restore pruned domains on backtrack
                for n, rm in removals.items():
                    self._domains[n] |= rm

            # Undo tentative assignment
            del state[mrv_eid]
            self.busy_rooms.discard((roomid, slot))
            self.busy_teachers.discard((teacher_id, slot))
            for gid in groups:
                self.busy_groups.discard((gid, slot))
                self.group_day_times[gid][day].discard(time)

        unassigned_set.add(mrv_eid)
        return None

    def generate_valid_state(self):
        """
        Build a fully hard-constraint-satisfying schedule using
        backtracking + forward checking, solved year by year.
        """
        # Precompute compatible rooms per event
        self.event_compatible_rooms = {}
        for event in self.events:
            compat = [
                r["id"] for r in self.rooms
                if r["capacity"]      >= event["headcount"]
                and r["room_type_id"] == event["required_room_type_id"]
            ]
            if not compat:
                raise RuntimeError(
                    f"Event {event['id']} ('{event['name']}') has no compatible rooms!")
            self.event_compatible_rooms[event["id"]] = compat

        # Shared trackers across all years (cross-year conflict detection)
        self.busy_rooms    = set()
        self.busy_teachers = set()
        self.busy_groups   = set()
        self.group_day_times = {
            gid: {day: set() for day in range(5)}
            for gid in self.groups_by_id
        }

        # Group events by student year so we solve smaller sub-problems
        year_of_group   = {g["id"]: g["year"] for g in self.groups}
        year_of_section = {}
        for sid, gids in self.section_to_group.items():
            if gids:
                year_of_section[sid] = year_of_group[gids[0]]

        def event_year(eid):
            e = self.events_by_id[eid]
            if e["type_id"] == 1:
                return year_of_section.get(e["target_id"], 0)
            return year_of_group.get(e["target_id"], 0)

        by_year = defaultdict(list)
        for e in self.events:
            by_year[event_year(e["id"])].append(e["id"])

        full_state = {}

        for year, eids in sorted(by_year.items()):
            neighbours    = self._precompute_neighbours(eids)
            self._domains = {eid: self._build_initial_domain(eid) for eid in eids}

            # FIX: prune domains against slots already committed by earlier years
            # so cross-year room/teacher/group conflicts are eliminated upfront.
            for eid in eids:
                e          = self.events_by_id[eid]
                teacher_id = e["teacher_id"]
                groups     = self._get_event_groups(e)
                pruned     = set()
                for (r, s) in self._domains[eid]:
                    if   (r,          s) in self.busy_rooms:   pruned.add((r, s))
                    elif (teacher_id, s) in self.busy_teachers: pruned.add((r, s))
                    else:
                        for gid in groups:
                            if (gid, s) in self.busy_groups:
                                pruned.add((r, s))
                                break
                self._domains[eid] -= pruned

            unassigned = set(eids)
            sub_state  = {}
            result = self._bt(unassigned, sub_state, neighbours)
            if result is None:
                raise RuntimeError(
                    f"No valid schedule found for year {year} — "
                    "constraints may be too tight.")
            full_state.update(result)

        return full_state

    def is_consistent(self, state, is_complete=False):
        """
        Validate state against hard constraints NOT covered by forward-checking.
        """
        slot_to_rooms, slot_to_groups, slot_to_teachers, teacher_events = \
            self.constraint_obj._build_lookup_tables(state)
        c = self.constraint_obj

        category_args = {
            "slot_to_rooms":    (slot_to_rooms,),
            "slot_to_groups":   (slot_to_groups,),
            "slot_to_teachers": (slot_to_teachers,),
            "state_based":      (state,),
            "teacher_based":    (teacher_events,),
        }

        # Guaranteed by forward-checking; skip for speed
        forward_checked = {
            "NO_ROOM_DOUBLE_BOOKING",
            "NO_GROUP_DOUBLE_BOOKING",
            "NO_TEACHER_DOUBLE_BOOKING",
            "ROOM_CAPACITY_GEQ_HEADCOUNT",
            "MATCH_ROOM_TYPE",
            "CONSECUTIVE_SECTION_LECTURES",
            "SEPARATE_LECTURE_PRACTICE",
            "MAX_CONSECUTIVE_STUDENT_SLOTS_3",
        }

        for hc in self.hard_constraints_list:
            if isinstance(hc, str):
                continue
            if hc["rule"] in forward_checked:
                continue
            fn = getattr(c, hc["rule"])
            if not fn(*category_args[hc["category"]], count=False):
                return False

        return True

    # ------------------------------------------------------------------ #
    #  CSP — Local search                                                  #
    # ------------------------------------------------------------------ #

    def generate_random_state(self):
        """Random assignment with no duplicate (room, slot) pairs."""
        n = len(self.events)
        if n > len(self.slots):
            raise RuntimeError(
                f"Not enough slots ({len(self.slots)}) for {n} events.")
        sampled = random.sample(self.slots, n)
        return {event["id"]: slot for event, slot in zip(self.events, sampled)}

    def enhance(self, state, method="hill_climbing_steepest", objective=None):
        """
        Local search to drive hard violations to zero, with random restarts.
        Instance-level method overrides are cleaned up in a finally block so
        subsequent soft-optimisation calls use the correct neighbour functions.
        """
        from optimizer import Optimizer
        opt = Optimizer()

        if objective is None:
            objective = self.evaluate_csp

        # Temporarily patch neighbour generators for the CSP phase
        if objective == self.evaluate_csp:
            self.generate_neighbors = \
                lambda state, event_id=None, size=50, shuffle=False: \
                self.generate_neighbors_csp(state, size)
            self.move_operator = \
                lambda state, shuffle=False: self.move_operator_csp(state)

        method_map = {
            "hill_climbing_steepest":       (opt.Hill_Climbing,
                                             {"strategy": "steepest"}),
            "hill_climbing_first":          (opt.Hill_Climbing,
                                             {"strategy": "first_choice"}),
            "hill_climbing_stochastic":     (opt.Hill_Climbing,
                                             {"strategy": "stochastic"}),
            "hill_climbing_random_restart": (opt.Random_Restart_Hill_Climbing,
                                             {}),
            "simulated_annealing":          (opt.Simulated_Annealing,
                                             {"initial_temp": 100.0,
                                              "cooling_rate": 0.1,
                                              "max_iterations": 1000}),
            "tabu_search":                  (opt.Tabu_Search, {}),
        }
        if method not in method_map:
            raise ValueError(
                f"Unknown method '{method}'. Choose from {list(method_map)}")

        search_fn, kwargs = method_map[method]
        current = dict(state)
        result  = current

        try:
            for _ in range(50):
                self.state = current
                result, cost = search_fn(problem=self, objective=objective,
                                         **kwargs)
                if cost == 0:
                    return result

                # Random kick to escape local optimum
                kicked = dict(result)
                for _ in range(5):
                    eid = random.choice(list(kicked))
                    kicked[eid] = random.choice(self.slots)
                current = kicked
        finally:
            # FIX: always restore original class-level methods
            if objective == self.evaluate_csp:
                for attr in ("generate_neighbors", "move_operator"):
                    try:
                        delattr(self, attr)
                    except AttributeError:
                        pass

        return result

    # ------------------------------------------------------------------ #
    #  Violation helpers                                                   #
    # ------------------------------------------------------------------ #

    def _get_violating_events(self, state):
        slot_to_rooms    = defaultdict(list)
        slot_to_teachers = defaultdict(list)
        slot_to_groups   = defaultdict(list)

        for event_id, (roomid, slot) in state.items():
            event = self.events_by_id[event_id]
            slot_to_rooms[(roomid, slot)].append(event_id)
            slot_to_teachers[(event["teacher_id"], slot)].append(event_id)
            if event["type_id"] == 1:
                for gid in self.section_to_group[event["target_id"]]:
                    slot_to_groups[(gid, slot)].append(event_id)
            else:
                slot_to_groups[(event["target_id"], slot)].append(event_id)

        violating = set()
        for eids in slot_to_rooms.values():
            if len(eids) > 1: violating.update(eids)
        for eids in slot_to_teachers.values():
            if len(eids) > 1: violating.update(eids)
        for eids in slot_to_groups.values():
            if len(eids) > 1: violating.update(eids)

        return list(violating) if violating else list(state.keys())

    def _best_csp_assignment(self, state, eid):
        """Greedy single-event reassignment that minimises violation count."""
        event = self.events_by_id[eid]
        compat_rooms = [
            r["id"] for r in self.rooms
            if r["capacity"]      >= event["headcount"]
            and r["room_type_id"] == event["required_room_type_id"]
        ] or [r["id"] for r in self.rooms]

        current_violations = len(self._get_violating_events(state))
        best_assignment    = state[eid]
        best_violations    = current_violations

        rooms = compat_rooms[:]
        slots = list(range(30))
        random.shuffle(rooms)
        random.shuffle(slots)

        for room in rooms:
            for slot in slots:
                if (room, slot) == state[eid]:
                    continue
                trial = dict(state)
                trial[eid] = (room, slot)
                v = len(self._get_violating_events(trial))
                if v < best_violations:
                    best_violations = v
                    best_assignment = (room, slot)
                    if v == 0:
                        return best_assignment

        return best_assignment

    # ------------------------------------------------------------------ #
    #  Neighbour / move operators                                          #
    # ------------------------------------------------------------------ #

    def swapper_napper(self, state, iteration=10):
        """Swap (room, slot) of random event pairs. No recursion."""
        keys = list(state.keys())
        for _ in range(iteration * 10):
            s1 = random.choice(keys)
            s2 = random.choice(keys)
            if s1 == s2:
                continue
            state[s1], state[s2] = state[s2], state[s1]
            if self.is_consistent(state, is_complete=True):
                return state
            state[s1], state[s2] = state[s2], state[s1]   # undo
        return state

    def shifter_nifter(self, state, iteration=10, shift_rate=0.75,
                       direction="left", amount=6):
        """
        Shift a random event's slot by `amount` positions, clamped to [0, 29].
        FIX: removed the broken '% 6' that collapsed slots onto [0, 5].
        """
        if direction not in ("left", "right"):
            return state

        keys = list(state.keys())
        for _ in range(iteration):
            eid = random.choice(keys)
            room_id, cur_slot = state[eid]
            delta    = -amount if direction == "left" else amount
            new_slot = max(0, min(29, cur_slot + delta))
            if new_slot != cur_slot:
                state[eid] = (room_id, new_slot)

        return state   # return as-is; caller decides whether to accept

    def move_to_another_slot(self, state, iteration=10):
        """
        Move events to a different compatible slot.
        FIX: only target rooms that match the event's type and capacity.
        """
        used = defaultdict(set)
        for eid, (room_id, slot) in state.items():
            used[room_id].add(slot)

        available = {r["id"]: set(range(30)) - used[r["id"]] for r in self.rooms}
        events = list(state.keys())

        for _ in range(iteration):
            eid   = random.choice(events)
            event = self.events_by_id[eid]
            cur_room, cur_slot = state[eid]

            compat = [
                r["id"] for r in self.rooms
                if r["capacity"]      >= event["headcount"]
                and r["room_type_id"] == event["required_room_type_id"]
                and available[r["id"]]
            ]
            if not compat:
                continue

            new_room = random.choice(compat)
            new_slot = random.choice(list(available[new_room]))

            available[cur_room].add(cur_slot)
            available[new_room].discard(new_slot)
            state[eid] = (new_room, new_slot)

        return state

    def _find_valid_slot(self, state, eid):
        """
        Find a (room, slot) for event  that does not conflict with any
        other event already in .  Returns None if no slot found.
        Tries compatible rooms first; shuffles to avoid always picking the same slot.
        """
        event = self.events_by_id[eid]
        compat_rooms = [
            r["id"] for r in self.rooms
            if r["capacity"]      >= event["headcount"]
            and r["room_type_id"] == event["required_room_type_id"]
        ]
        if not compat_rooms:
            return None

        # Build occupied sets from the state (excluding the event being moved)
        occupied_rooms    = set()
        occupied_teachers = set()
        occupied_groups   = set()
        teacher_id = event["teacher_id"]
        my_groups  = set(self._get_event_groups(event))

        for other_eid, (other_room, other_slot) in state.items():
            if other_eid == eid:
                continue
            other_event = self.events_by_id[other_eid]
            occupied_rooms.add((other_room, other_slot))
            occupied_teachers.add((other_event["teacher_id"], other_slot))
            for gid in self._get_event_groups(other_event):
                occupied_groups.add((gid, other_slot))

        all_slots = list(range(30))
        random.shuffle(compat_rooms)
        random.shuffle(all_slots)

        for room in compat_rooms:
            for slot in all_slots:
                if (room, slot) == state[eid]:
                    continue  # skip current assignment
                if (room, slot) in occupied_rooms:
                    continue
                if (teacher_id, slot) in occupied_teachers:
                    continue
                if any((gid, slot) in occupied_groups for gid in my_groups):
                    continue
                return (room, slot)

        return None  # no conflict-free slot found

    def _try_swap(self, state, eid1, eid2):
        """
        Attempt to swap the (room, slot) assignments of two events.
        Returns the new state if valid, None otherwise.
        Swapping is cheap and produces more disruptive moves than single relocation.
        """
        r1, s1 = state[eid1]
        r2, s2 = state[eid2]
        e1 = self.events_by_id[eid1]
        e2 = self.events_by_id[eid2]

        # Check room compatibility after swap
        if e1["headcount"] > self.rooms_by_id[r2]["capacity"]:
            return None
        if e1["required_room_type_id"] != self.rooms_by_id[r2]["room_type_id"]:
            return None
        if e2["headcount"] > self.rooms_by_id[r1]["capacity"]:
            return None
        if e2["required_room_type_id"] != self.rooms_by_id[r1]["room_type_id"]:
            return None

        n = dict(state)
        n[eid1] = (r2, s2)
        n[eid2] = (r1, s1)
        return n if self.evaluate_csp(n) == 0 else None

    def pipeline_generate_neighbors(self, state, size=50):
        """
        Generate neighbors using three move types for better search diversity:
          1. Single relocation  — move one event to a new valid slot  (exploitation)
          2. Swap               — swap two events slot assignments     (medium disruption)
          3. Multi-relocation   — move 2-3 events at once             (exploration)
        Neighbors that violate any hard constraint are discarded.
        """
        neighbors = []
        event_ids = list(state.keys())
        attempts  = 0
        max_attempts = size * 15

        while len(neighbors) < size and attempts < max_attempts:
            attempts += 1
            move_type = random.randint(0, 2)

            if move_type == 0:
                # Single relocation
                eid = random.choice(event_ids)
                new_slot = self._find_valid_slot(state, eid)
                if new_slot is None:
                    continue
                n = dict(state)
                n[eid] = new_slot
                if self.evaluate_csp(n) == 0:
                    neighbors.append(n)

            elif move_type == 1:
                # Swap two events
                if len(event_ids) < 2:
                    continue
                eid1, eid2 = random.sample(event_ids, 2)
                n = self._try_swap(state, eid1, eid2)
                if n is not None:
                    neighbors.append(n)

            else:
                # Multi-relocation: move 2 or 3 events sequentially
                k = random.randint(2, 3)
                eids = random.sample(event_ids, min(k, len(event_ids)))
                n = dict(state)
                ok = True
                for eid in eids:
                    new_slot = self._find_valid_slot(n, eid)
                    if new_slot is None:
                        ok = False
                        break
                    n[eid] = new_slot
                if ok and self.evaluate_csp(n) == 0:
                    neighbors.append(n)

        if not neighbors:
            neighbors.append(dict(state))

        return neighbors

    def generate_neighbors(self, state, event_id=None, size=50, shuffle=False):
        if self.evaluate_csp(state) > 0:
            return self.generate_neighbors_csp(state, size)
        return self.pipeline_generate_neighbors(state, size=size)

    def move_operator(self, state, shuffle=False):
        if self.evaluate_csp(state) > 0:
            return self.move_operator_csp(state)
        return self.pipeline_generate_neighbors(state, size=1)[0]

    def generate_neighbors_csp(self, state, size=50):
        neighbors = []
        violating = self._get_violating_events(state)
        if not violating:
            return [copy.deepcopy(state) for _ in range(size)]
        for _ in range(size):
            eid = random.choice(violating)
            n   = copy.deepcopy(state)
            n[eid] = self._best_csp_assignment(state, eid)
            neighbors.append(n)
        return neighbors

    def move_operator_csp(self, state):
        if self.evaluate_csp(state) == 0:
            return copy.deepcopy(state)
        violating = self._get_violating_events(state)
        eid = random.choice(violating)
        n   = copy.deepcopy(state)
        n[eid] = self._best_csp_assignment(state, eid)
        return n

    # ------------------------------------------------------------------ #
    #  Objective functions                                                 #
    # ------------------------------------------------------------------ #

    def evaluate(self, state):
        groups_cost = 0.0
        profs_cost  = 0.0
        add_cost    = 0.0

        group_schedules = {g: [] for g in self.groups_by_id}
        prof_schedules  = {}

        external_constraints = [sc for sc in self.soft_constraints_list
                                 if sc["category"] == "external"]
        general_constraints  = [sc for sc in self.soft_constraints_list
                                 if sc["category"] == "general"]
        group_constraints    = [sc for sc in self.soft_constraints_list
                                 if sc["category"] in ("group", "group-prof")]
        prof_constraints     = [sc for sc in self.soft_constraints_list
                                 if sc["category"] in ("prof", "group-prof")]

        for ec in external_constraints:
            add_cost += getattr(self.constraint_obj, ec["rule"])(
                state, ec["weight"])

        for event_id, (roomid, slot) in state.items():
            event_data = self.events_by_id[event_id]
            if not event_data:
                continue

            prof_id   = event_data["teacher_id"]
            target_id = event_data["target_id"]

            for gc in general_constraints:
                add_cost += getattr(self.constraint_obj, gc["rule"])(
                    event_data, roomid, slot, gc["weight"])

            prof_schedules.setdefault(prof_id, []).append((roomid, slot))

            if event_data["type_id"] == 1:
                for gid in self.section_to_group[target_id]:
                    group_schedules[gid].append((roomid, slot))
            else:
                group_schedules[target_id].append((roomid, slot))

        for prof_id, sched in prof_schedules.items():
            for pc in prof_constraints:
                profs_cost += getattr(self.constraint_obj, pc["rule"])(
                    sched, pc["weight"])

        for group_id, sched in group_schedules.items():
            for grc in group_constraints:
                groups_cost += getattr(self.constraint_obj, grc["rule"])(
                    sched, grc["weight"])

        if group_schedules: groups_cost /= len(group_schedules)
        if prof_schedules:  profs_cost  /= len(prof_schedules)

        return 0.6 * groups_cost + 0.4 * profs_cost + add_cost

    def evaluate_csp(self, state, fast=True):
        """
        Count hard constraint violations.
        fast=True (default): return as soon as ANY violation is found (returns 1).
        fast=False: count all violations across every constraint (used for reporting).
        """
        slot_to_rooms, slot_to_groups, slot_to_teachers, teacher_events = \
            self.constraint_obj._build_lookup_tables(state)
        c = self.constraint_obj
        category_args = {
            "slot_to_rooms":    (slot_to_rooms,),
            "slot_to_groups":   (slot_to_groups,),
            "slot_to_teachers": (slot_to_teachers,),
            "state_based":      (state,),
            "teacher_based":    (teacher_events,),
        }
        violations = 0
        for hc in self.hard_constraints_list:
            if isinstance(hc, str):
                continue
            fn = getattr(c, hc["rule"])
            v  = fn(*category_args[hc["category"]], count=True)
            violations += v
            # Short-circuit: no need to check remaining constraints
            if fast and violations > 0:
                return violations
        return violations