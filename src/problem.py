from contraints import *
from collections import defaultdict
import copy 
import random
import json
import os

class Problem:
    pass

class EnsiaProblem(Problem):
    def __init__(self, dataset, cspmethod="global_search"):
        super().__init__()

        data = self.load_data(dataset)
        self.rooms = data[0]
        self.events = data[3]
        self.groups = data[2]
        self.teachers = data[5]
        self.section_to_group = {section["id"] : [] for section in data[1]}
        for group in self.groups: self.section_to_group[group["section_id"]].append(group["id"])
        self.events_by_id = {e["id"]: e for e in self.events}
        self.rooms_by_id  = {r["id"]:  r for r in self.rooms}
        self.groups_by_id  = {r["id"]:  r for r in self.groups}
        self.teachers_by_id = {t["id"]:  t for t in self.teachers}

        slots = []
        for r in self.rooms:
            for t in range(30):
                slots.append((r["id"], t))
        self.slots = slots
        
        self.hard_constraints_list = data[4].get("hard", [])
        self.soft_constraints_list = data[4].get("soft", [])

        self.constraint_obj = Constraints(self)

        self._lec_counts = defaultdict(int)
        for e in self.events:
            if e["type_id"] == 1:
                self._lec_counts[(e["course_name"], e["target_id"])] += 1

        if cspmethod == "local_search":
            self.state = self.generate_random_state()
        else:
            if cspmethod != "global_search": 
                print("invalid csp method, redirecting to GS csp ...\n")
            self.state = self.generate_valid_state()

    def load_data(self, filename):
        if not os.path.exists(filename):
            raise FileNotFoundError(f"Dataset file {filename} not found.")
        
        with open(filename, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
        
        return [
            raw_data.get("rooms", []),
            raw_data.get("sections", []),
            raw_data.get("groups", []),
            raw_data.get("activities", []),
            raw_data.get("constraints", {}),
            raw_data.get("teachers", {})
        ]

    def _get_event_groups(self, event):
        if event["type_id"] == 1:
            return self.section_to_group[event["target_id"]]
        return [event["target_id"]]

    def _precompute_neighbours(self, event_ids):
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
        event        = self.events_by_id[event_id]
        compat_rooms = self.event_compatible_rooms[event_id]
        return {(r, s) for r in compat_rooms for s in range(30)}

    def _removed_by_assignment(self, assigned_eid, roomid, slot, unassigned_set, neighbours):
        assigned_event   = self.events_by_id[assigned_eid]
        assigned_teacher = assigned_event["teacher_id"]
        assigned_groups  = set(self._get_event_groups(assigned_event))
        assigned_course  = assigned_event["course_name"]
        assigned_is_lec  = (assigned_event["type_id"] == 1)
        assigned_day     = slot // 6
        assigned_time    = slot % 6

        removals = {}

        for neid in neighbours[assigned_eid]:
            if neid not in unassigned_set:
                continue

            nevent      = self.events_by_id[neid]
            nteacher    = nevent["teacher_id"]
            ngroups     = set(self._get_event_groups(nevent))
            ncourse     = nevent["course_name"]
            n_is_lec    = (nevent["type_id"] == 1)
            shared_grps = assigned_groups & ngroups
            same_course = (ncourse == assigned_course)

            to_remove = set()
            domain    = self._domains[neid]

            for (nr, ns) in domain:
                nday  = ns // 6
                ntime = ns % 6
                bad   = False

                if nr == roomid and ns == slot:
                    bad = True
                elif nteacher == assigned_teacher and ns == slot:
                    bad = True
                elif shared_grps and ns == slot:
                    bad = True
                elif same_course and shared_grps:
                    if (assigned_is_lec and not n_is_lec) or \
                       (not assigned_is_lec and n_is_lec):
                        if nday == assigned_day:
                            bad = True
                    elif assigned_is_lec and n_is_lec:
                        course_lec_count = self._lec_counts.get((assigned_course, assigned_event["target_id"]), 0)
                        if course_lec_count == 2:
                            adj = {slot - 1, slot + 1}
                            adj = {a for a in adj if a // 6 == assigned_day and 0 <= a % 6 <= 5}
                            if ns not in adj:
                                bad = True

                if not bad and shared_grps and nday == assigned_day:
                    for gid in shared_grps:
                        times_set = self.group_day_times[gid][assigned_day]
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

        for neid in unassigned_set:
            if (roomid, slot) in self._domains[neid]:
                removals.setdefault(neid, set()).add((roomid, slot))

        return removals

    def _backtrack(self, unassigned_set, state, neighbours):
        if not unassigned_set:
            return state

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

            state[mrv_eid] = (roomid, slot)
            self.busy_rooms.add((roomid, slot))
            self.busy_teachers.add((teacher_id, slot))
            for gid in groups:
                self.busy_groups.add((gid, slot))
                self.group_day_times[gid][day].add(time)

            removals = self._removed_by_assignment(
                mrv_eid, roomid, slot, unassigned_set, neighbours
            )

            wipeout = any(
                len(self._domains[n] - rm) == 0
                for n, rm in removals.items()
            )

            if not wipeout:
                for n, rm in removals.items():
                    self._domains[n] -= rm

                result = self._backtrack(unassigned_set, state, neighbours)
                if result is not None:
                    return result

                for n, rm in removals.items():
                    self._domains[n] |= rm

            del state[mrv_eid]
            self.busy_rooms.discard((roomid, slot))
            self.busy_teachers.discard((teacher_id, slot))
            for gid in groups:
                self.busy_groups.discard((gid, slot))
                self.group_day_times[gid][day].discard(time)

        unassigned_set.add(mrv_eid)
        return None

    def generate_valid_state(self):
        self.event_compatible_rooms = {}
        for event in self.events:
            compat = [
                r["id"] for r in self.rooms
                if r["capacity"] >= event["headcount"]
                and r["room_type_id"] == event["required_room_type_id"]
            ]
            if not compat:
                raise RuntimeError(f"Event {event['id']} ({event['name']}) has no compatible rooms!")
            self.event_compatible_rooms[event["id"]] = compat

        self.busy_rooms    = set()
        self.busy_teachers = set()
        self.busy_groups   = set()
        self.group_day_times = {
            gid: {day: set() for day in range(5)}
            for gid in self.groups_by_id
        }

        year_of_group = {g["id"]: g["year"] for g in self.groups}
        year_of_section = {}
        for section_id, gids in self.section_to_group.items():
            if gids:
                year_of_section[section_id] = year_of_group[gids[0]]

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
            neighbours = self._precompute_neighbours(eids)
            self._domains = {eid: self._build_initial_domain(eid) for eid in eids}

            # Prune slots already used by previous years
            if self.busy_rooms:
                for eid in eids:
                    self._domains[eid] -= self.busy_rooms

            # Prune busy teachers and groups across different years
            for eid in eids:
                e = self.events_by_id[eid]
                teacher_id = e["teacher_id"]
                groups = self._get_event_groups(e)

                invalid_slots = set()
                for roomid, slot in list(self._domains[eid]):
                    if (teacher_id, slot) in self.busy_teachers:
                        invalid_slots.add((roomid, slot))
                    elif any((gid, slot) in self.busy_groups for gid in groups):
                        invalid_slots.add((roomid, slot))

                self._domains[eid] -= invalid_slots

            unassigned = set(eids)
            sub_state  = {}

            result = self._backtrack(unassigned, sub_state, neighbours)
            if result is None:
                raise RuntimeError(
                    f"No valid schedule found for year {year} — constraints may be too tight."
                )

            full_state.update(result)

        if not self.is_consistent(full_state, is_complete=True):
            raise RuntimeError("Generated schedule violates hard constraints")

        return full_state

    def is_consistent(self, state, is_complete=False):
        """
        Validates the current state against hard constraints.
        - is_complete=False: only checks booking conflicts (fast, used during local search)
        - is_complete=True: checks ALL hard constraints (used after full schedule generation)
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

        # Fast rules always checked
        fast_rules = {
            "NO_ROOM_DOUBLE_BOOKING",
            "NO_GROUP_DOUBLE_BOOKING",
            "NO_TEACHER_DOUBLE_BOOKING",
        }

        for hc in self.hard_constraints_list:
            if isinstance(hc, str):
                continue

            rule = hc["rule"]

            # During local search, only check fast booking rules
            if not is_complete and rule not in fast_rules:
                continue

            fn   = getattr(c, rule)
            args = category_args[hc["category"]]
            if not fn(*args, count=False):
                return False

        return True

    # CSP Local

    def generate_random_state(self):
        shuffled_slots = random.sample(self.slots, len(self.events))
        return {event["id"]: slot for event, slot in zip(self.events, shuffled_slots)}

    def swap_events_operator(self, state, iteration=10):
        course = list(state.keys())
        temp_state = state.copy()

        for i in range(iteration):
            selected1 = random.choice(course)
            selected2 = random.choice(course)
            values1 = temp_state[selected1]
            temp_state[selected1] = temp_state[selected2]
            temp_state[selected2] = values1

        if not self.is_consistent(temp_state):
            return state
        return temp_state

    def shift_events_operator(self, state, iteration=10, direction="left", amount=1):
        if direction not in ["left", "right"]:
            return state

        new_state = state.copy()
        room_availability = {rid: set(range(30)) for rid in self.rooms_by_id.keys()}
        for eid, (rid, slot) in new_state.items():
            if rid in room_availability:
                room_availability[rid].discard(slot)

        events = list(new_state.keys())

        for _ in range(iteration):
            target_event = random.choice(events)
            room_id, old_slot = new_state[target_event]

            shift = -amount if direction == "left" else amount
            ideal_slot = (old_slot + shift) % 30

            if ideal_slot in room_availability[room_id]:
                new_state[target_event] = (room_id, ideal_slot)
                room_availability[room_id].remove(ideal_slot)
                room_availability[room_id].add(old_slot)

                if self.is_consistent(new_state):
                    return new_state
                else:
                    new_state[target_event] = (room_id, old_slot)
                    room_availability[room_id].add(ideal_slot)
                    room_availability[room_id].remove(old_slot)

        return state

    def relocate_event_operator(self, state, iteration=10):
        temp_state = state.copy()
        all_rooms = [key for key, _ in self.rooms_by_id.items()]
        available_slots = dict()
        for room_id in all_rooms:
            available_slots[room_id] = set([i for i in range(5*6)])

        for key, (room_id, slot) in temp_state.items():
            if slot in available_slots:
                available_slots[room_id].discard(slot)

        events = list(temp_state.keys())

        for i in range(iteration):
            event = random.choice(events)
            (room_id, slot) = temp_state[event]
            if not available_slots[room_id]:
                continue
            next_slot = random.choice(list(available_slots[room_id]))
            temp_state[event] = (room_id, next_slot)
            available_slots[room_id].remove(next_slot)
            available_slots[room_id].add(slot)

        if not self.is_consistent(temp_state):
            return state
        return temp_state

    def pipeline_generate_neighbors(self, state, size=50):
        neighbors = []
        for _ in range(size):
            n = state.copy()
            n = self.shift_events_operator(n, iteration=10, direction="left", amount=4)
            n = self.shift_events_operator(n, iteration=10, direction="right", amount=4)
            neighbors.append(n)
        return neighbors

    def _relocate(self, state, n):
        event_sample = random.sample(list(state.keys()), k=n)
        used_slots = set(state.values())
        empty_slots = [s for s in self.slots if s not in used_slots]
        state_copy = state.copy()

        for event in event_sample:
            old_slot = state_copy[event]
            random.shuffle(empty_slots)
            assigned = False

            for slot in empty_slots:
                state_copy[event] = slot
                if self.is_consistent(state_copy):
                    empty_slots.remove(slot)
                    empty_slots.append(old_slot)
                    assigned = True
                    break

            if not assigned:
                state_copy[event] = old_slot

        return state_copy

    def generate_neighbors(self, state, size, n=5):
        neighbors = []
        for _ in range(size):
            next_state = self._relocate(state, n)
            next_state = self.shift_events_operator(next_state, iteration=10, direction="left", amount=4)
            next_state = self.shift_events_operator(next_state, iteration=10, direction="right", amount=4)
            neighbors.append(next_state)
        return neighbors

    def move_operator(self, state):
        return self.pipeline_generate_neighbors(self.generate_neighbors_csp(state)[0], size=1)[0]

    def generate_neighbors_csp(self, state, size=50):
        neighbors = []
        event_ids = list(state.keys())
        for _ in range(size):
            n = copy.deepcopy(state)
            for i in range(10):
                eid = random.choice(event_ids)
                n[eid] = random.choice(self.slots)
            neighbors.append(n)
        return neighbors

    def move_operator_csp(self, state):
        n = copy.deepcopy(state)
        eid = random.choice(list(state.keys()))
        n[eid] = random.choice(self.slots)
        return n

    def evaluate(self, state):
        groups_cost = 0.0
        profs_cost  = 0.0
        add_cost    = 0.0

        group_schedules = {g: [] for g in self.groups_by_id}
        prof_schedules  = {}

        external_constraints = [sc for sc in self.soft_constraints_list if sc["category"] == "external"]
        general_constraints  = [sc for sc in self.soft_constraints_list if sc["category"] == "general"]
        group_constraints    = [sc for sc in self.soft_constraints_list if sc["category"] in ("group", "group-prof")]
        prof_constraints     = [sc for sc in self.soft_constraints_list if sc["category"] in ("prof", "group-prof")]

        for ec in external_constraints:
            constraint_function = getattr(self.constraint_obj, ec["rule"])
            add_cost += constraint_function(state, ec["weight"])

        for event_id, (roomid, slot) in state.items():
            event_data = self.events_by_id[event_id]
            if not event_data: continue

            prof_id   = event_data["teacher_id"]
            target_id = event_data["target_id"]

            for gc in general_constraints:
                constraint_function = getattr(self.constraint_obj, gc["rule"])
                add_cost += constraint_function(event_data, roomid, slot, gc["weight"])

            if prof_id not in prof_schedules:
                prof_schedules[prof_id] = []
            prof_schedules[prof_id].append((roomid, slot))

            if event_data["type_id"] == 1:
                for group_id in self.section_to_group[target_id]:
                    group_schedules[group_id].append((roomid, slot))
            else:
                group_schedules[target_id].append((roomid, slot))

        for prof_id, sched in prof_schedules.items():
            for pc in prof_constraints:
                constraint_function = getattr(self.constraint_obj, pc["rule"])
                profs_cost += constraint_function(sched, pc["weight"])

        for group_id, sched in group_schedules.items():
            for grc in group_constraints:
                constraint_function = getattr(self.constraint_obj, grc["rule"])
                groups_cost += constraint_function(sched, grc["weight"])

        if group_schedules: groups_cost /= len(group_schedules)
        if prof_schedules:  profs_cost  /= len(prof_schedules)

        return 0.6 * groups_cost + 0.4 * profs_cost + add_cost

    def evaluate_csp(self, state):
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
            if isinstance(hc, str): continue
            fn   = getattr(c, hc["rule"])
            args = category_args[hc["category"]]
            violations += fn(*args, count=True)
        return violations
