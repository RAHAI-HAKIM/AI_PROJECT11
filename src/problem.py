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

    def _is_room_compatible(self, room_id, event_id):
        """
        Returns True iff the room satisfies the event's hard structural
        requirements (type match + capacity).  Used by every move operator
        to pre-screen rooms in O(1) instead of running the full is_consistent
        scan for a change that is guaranteed to violate those two constraints.
        """
        room  = self.rooms_by_id[room_id]
        event = self.events_by_id[event_id]
        return (
            room["room_type_id"] == event["required_room_type_id"]
            and room["capacity"] >= event["headcount"]
        )

    def _get_event_groups(self, event):
        """
        Retrieves the list of student group IDs associated with a specific event.
        If the event is a lecture, it fetches all groups within that section.
        Otherwise, it returns the single group targeted by the event.
        
        Args:
            event (dict): The event dictionary containing 'type_id' and 'target_id'.
            
        Returns:
            list: A list of student group IDs attending this event.
        """
        if event["type_id"] == 1:
            return self.section_to_group[event["target_id"]]
        
        return [event["target_id"]]

    def _precompute_neighbours(self, event_ids):
        """
        Builds an adjacency graph of events to facilitate rapid constraint checking.
        Events are considered neighbors if they share a teacher, course, or student group.
        
        Args:
            event_ids (iterable): A list or set of event IDs to process.
            
        Returns:
            dict: A mapping of each event ID to a set of neighboring event IDs.
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
        """
        Generates the initial domain of all valid (room, time_slot) pairs for a given event.
        
        Args:
            event_id (int/str): The unique identifier for the event.
            
        Returns:
            set: A set of tuples formatted as (room_id, slot_index), checking across all 30 slots.
        """
        event        = self.events_by_id[event_id]
        compat_rooms = self.event_compatible_rooms[event_id]
        
        return {(r, s) for r in compat_rooms for s in range(30)}

    def _removed_by_assignment(self, assigned_eid, roomid, slot, unassigned_set, neighbours):
        """
        Performs forward checking by finding and pruning domain values from unassigned 
        neighboring events that are invalidated by the current assignment.
        
        Args:
            assigned_eid (int/str): The ID of the event just assigned.
            roomid (int/str): The room ID assigned to the event.
            slot (int): The time slot (0-29) assigned to the event.
            unassigned_set (set): The current set of unassigned event IDs.
            neighbours (dict): The precomputed event adjacency graph.
            
        Returns:
            dict: A mapping of neighbor IDs to the set of (room, slot) tuples that must be removed.
        """
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
        """
        Executes a recursive backtracking search to assign rooms and time slots to all events.
        Uses Minimum Remaining Values (MRV) to pick the next event and Forward Checking to 
        fail early if a domain wipeout occurs.
        
        Args:
            unassigned_set (set): Event IDs that still need assignments.
            state (dict): The current partial schedule mapping event_ids to (room, slot).
            neighbours (dict): The precomputed event adjacency graph.
            
        Returns:
            dict or None: The completed state dictionary if successful, or None if no valid assignment exists.
        """
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
        """
        Initializes the CSP solver, precomputes valid rooms, divides the problem into 
        sub-problems by student year, and runs the backtracking algorithm to generate 
        the full schedule.
        
        Args:
            None
            
        Returns:
            dict: The complete valid schedule mapping event_ids to (room, slot).
            
        Raises:
            RuntimeError: If an event has no compatible rooms or a valid schedule cannot be found.
        """
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

            if self.busy_rooms:
                for eid in eids:
                    self._domains[eid] -= self.busy_rooms

            unassigned = set(eids)
            sub_state  = {}

            result = self._backtrack(unassigned, sub_state, neighbours)
            if result is None:
                raise RuntimeError(
                    f"No valid schedule found for year {year} — constraints may be too tight."
                )
                
            full_state.update(result)

        if not self.is_consistent(full_state, is_complete=True):
            raise RuntimeError(
                "Generated schedule violates hard constraints"
            )

        return full_state

    def is_consistent(self, state, is_complete=False):
        """
        Validates the current state against hard constraints.

        During backtracking (is_complete=False), rules already enforced by
        forward-checking are skipped for efficiency, they cannot be violated
        because the domain pruner prevents it.

        When called on the "final" complete schedule (is_complete=True), every
        hard constraint is re-evaluated for safety. This catches anything
        that forward-checking might have missed (e.g. cross-year room conflicts
        that were outside the per-year neighbour graph).

        Args:
            state (dict): The current schedule mapping event_ids to (room, slot).
            is_complete (bool): True iff every event has been assigned.

        Returns:
            bool: True if no hard constraint is violated, False otherwise.
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

        forward_checked_rules = [
            "NO_ROOM_DOUBLE_BOOKING",
            "NO_GROUP_DOUBLE_BOOKING",
            "NO_TEACHER_DOUBLE_BOOKING",
            "ROOM_CAPACITY_GEQ_HEADCOUNT",
            "MATCH_ROOM_TYPE",
            "CONSECUTIVE_SECTION_LECTURES",
            "SEPARATE_LECTURE_PRACTICE",
            "MAX_CONSECUTIVE_STUDENT_SLOTS_3",
        ]

        for hc in self.hard_constraints_list:
            if isinstance(hc, str):
                continue

            rule = hc["rule"]

            if not is_complete and rule in forward_checked_rules:
                continue

            fn   = getattr(c, rule)
            args = category_args[hc["category"]]
            if not fn(*args, count=False):
                return False

        return True

    # CSP Local

    def generate_random_state(self):
        self.event_compatible_rooms = {}
        for event in self.events:
            compat = set()
            for r_id in self.rooms_by_id:
                if self._is_room_compatible(r_id, event["id"]):
                    compat.add(r_id)
            self.event_compatible_rooms[event["id"]] = compat
            
        import random
        shuffled_slots = random.sample(self.slots, len(self.events))
        return {event["id"]: slot for event, slot in zip(self.events, shuffled_slots)}

    def swap_events_operator(self, state, iteration=10):
        """
        Swaps the TIME SLOTS of two randomly chosen events, keeping each
        event in its original room.
    
        Why slots-only?
        ───────────────
        The only hard constraints reachable by a slot-swap are double-booking
        and scheduling-structure rules.  We check those once at the end with
        the cheap lookup-table path inside is_consistent(is_complete=False).
        If the full batch fails we return the original — but because we do
        ALL `iteration` swaps before checking.
        """
        temp_state = state.copy()
        events     = list(temp_state.keys())
    
        for _ in range(iteration):
            if len(events) < 2:
                break
            e1, e2 = random.sample(events, 2)
            r1, s1 = temp_state[e1]
            r2, s2 = temp_state[e2]
            # swap only slots — rooms stay with their original event
            temp_state[e1] = (r1, s2)
            temp_state[e2] = (r2, s1)
    
        # is_consistent(is_complete=False) checks only the three double-booking
        # rules — exactly the ones a slot-swap can violate.  It does NOT check
        # room-type or capacity because those cannot be broken here.
        if not self.is_consistent(temp_state, is_complete=True):
            return state
    
        return temp_state
 
 
# ── operator 2 : shift events within the same day ────────────────────────────
    def shift_events_operator(self, state, iteration=10, direction="left", amount=1):
        """
        Shifts up to `iteration` randomly chosen events by `amount` slots
        forward or backward, staying strictly within the same day.
    
        Fix 1 — day-boundary wrap:
            computes the new time within the day and rejects
            the move if it falls outside 0..5.
    
        Fix 2 — early return after first success:
            accumulates ALL
            valid shifts and checks once at the end.
    
        Fix 3 — is_consistent inside the loop:
            defers the check
            to a single call on the fully-modified state.
        """
        if direction not in ("left", "right"):
            return state
    
        shift     = -amount if direction == "left" else amount
        new_state = state.copy()
    
        # Track free slots per room (slots not currently occupied)
        room_avail = {rid: set(range(30)) for rid in self.rooms_by_id}
        for eid, (rid, slot) in new_state.items():
            room_avail[rid].discard(slot)
    
        events  = list(new_state.keys())
        changed = False
    
        for _ in range(iteration):
            target   = random.choice(events)
            rid, old = new_state[target]
    
            old_day  = old // 6
            old_time = old % 6
            new_time = old_time + shift
    
            # FIX 1: reject moves that cross day boundaries
            if new_time < 0 or new_time > 5:
                continue
    
            ideal = old_day * 6 + new_time
    
            if ideal not in room_avail[rid]:
                continue  # target slot is occupied — skip this attempt
    
            # apply the shift
            new_state[target] = (rid, ideal)
            room_avail[rid].discard(ideal)
            room_avail[rid].add(old)
            changed = True
            # FIX 2: do NOT return here — keep accumulating
    
        if not changed:
            return state
    
        # FIX 3: single consistency check at the end
        if not self.is_consistent(new_state, is_complete=True):
            return state
    
        return new_state
    
    
    # ── operator 3 : move events to a different compatible (room, slot) ───────────
    def relocate_event_operator(self, state, iteration=10):
        """
        Moves up to `iteration` randomly chosen events to a new (room, slot)
        pair, where the new room is compatible with the event (type + capacity).
    
        New approach:
            We maintain a per-room free-slot set that is updated on every
            successful move, so the available-slot view is always current.
            We also pre-screen rooms with _is_room_compatible so we never
            attempt a move that would break room-type or capacity constraints.
        """
        temp_state = state.copy()
    
        # Build per-room free-slot sets, updated incrementally
        room_avail = {rid: set(range(30)) for rid in self.rooms_by_id}
        for eid, (rid, slot) in temp_state.items():
            room_avail[rid].discard(slot)
    
        events  = list(temp_state.keys())
        changed = False
    
        for _ in range(iteration):
            event_id       = random.choice(events)
            old_rid, old_s = temp_state[event_id]
    
            # Only consider rooms that satisfy type + capacity for this event
            compat_rooms = [
                rid for rid in self.rooms_by_id
                if self._is_room_compatible(rid, event_id) and room_avail[rid]
            ]
            if not compat_rooms:
                continue
    
            new_rid  = random.choice(compat_rooms)
            new_slot = random.choice(list(room_avail[new_rid]))
    
            # Apply move and update availability
            temp_state[event_id] = (new_rid, new_slot)
            room_avail[new_rid].discard(new_slot)
            room_avail[old_rid].add(old_s)
            changed = True
    
        if not changed:
            return state
    
        # Full check here because room changes CAN affect all hard constraints
        if not self.is_consistent(temp_state, is_complete=True):
            return state
    
        return temp_state
        
    
    
    # ── pipeline : combine operators, emit `size` distinct neighbours ─────────────
    def pipeline_generate_neighbors(self, state, size=200):
        """
        Generates `size` neighbours by randomly choosing one operator per
        neighbour.
        New approach:
            Pick ONE operator randomly per neighbour attempt.  If that operator
            returns the unchanged state (rare — means every attempt inside it
            was rejected), try the next operator in a shuffled order.  This
            guarantees at least one operator gets a real chance per neighbour.
        """
        operators = [
            lambda s: self.relocate_event_operator(s, iteration=1),
            lambda s: self.swap_events_operator(s,    iteration=1),
            lambda s: self.shift_events_operator(s,   iteration=1, direction="left",  amount=1),
            lambda s: self.shift_events_operator(s,   iteration=1, direction="right", amount=1),
            lambda s: self.swap_events_operator(s,    iteration=2),
            lambda s: self.relocate_event_operator(s, iteration=2),
        ]
    
        neighbors = []
        for _ in range(size):
            candidate = state
            for op in random.sample(operators, len(operators)):
                result = op(state)
                if result is not state:   
                    candidate = result
                    break
            neighbors.append(candidate)
    
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

    def generate_neighbors(self, state, size=10):
        """
        Generates `size` neighbours for the opt objective (soft-constraint
        minimisation).  Delegates entirely to the pipeline.
    
        Old version threaded state through _relocate which had the corrupted
        slot-tracking bug described above, then chained two shift operators
        that cancelled each other.  Both issues are fixed in the pipeline.
        """
        return self.pipeline_generate_neighbors(state, size=size)
 
 
    def move_operator(self, state):
        """
        Returns a single neighbour for SA's per-iteration move.
    
        Old version bug:
            generate_neighbors_csp assigns RANDOM (room,slot) pairs to 10
            events with zero constraint awareness, so the starting point fed
            into the pipeline already had up to 10+ hard constraint violations.
            The pipeline's is_consistent check would then reject everything and
            return the corrupted CSP state unchanged — a state with violations.
    
        """
        candidates = self.pipeline_generate_neighbors(state, size=5)
        return min(candidates, key=lambda s: self.evaluate(s))

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

    def local_conflicts(self, event_id, roomid, slot, state, slot_to_events, group_day_times):
        """
        Calculates the number of hard constraint violations caused specifically by
        placing `event_id` at `(roomid, slot)`, using a pre-maintained
        `group_day_times` structure for O(1) consecutive-slot lookups.
        
        Args:
            event_id (int): The ID of the event being evaluated.
            roomid (int): Candidate room ID.
            slot (int): Candidate time slot (0-29).
            state (dict): The current complete schedule.
            slot_to_events (dict): Mapping of slot → set of event IDs in that slot.
            group_day_times (dict): Mapping of (group_id, day) → set of occupied time indices.
            
        Returns:
            int: The number of local conflicts detected.
        """
        conflicts = 0
        event     = self.events_by_id[event_id]
        groups    = self._get_event_groups(event)
        groups_set = frozenset(groups)
        teacher    = event["teacher_id"]
        day        = slot // 6
        time_idx   = slot % 6

        for eid in slot_to_events.get(slot, []):
            if eid == event_id: continue
            rid, _ = state[eid]
            if rid == roomid: conflicts += 1
            e2 = self.events_by_id[eid]
            if e2["teacher_id"] == teacher: conflicts += 1
            if groups_set.intersection(self._get_event_groups(e2)): conflicts += 1

        for g in groups:
            times = group_day_times.get((g, day), set()) - {time_idx}
            ts = sorted(times | {time_idx})
            run = max_run = 1
            for k in range(1, len(ts)):
                run = run + 1 if ts[k] == ts[k-1] + 1 else 1
                max_run = max(max_run, run)
            if max_run > 3:
                conflicts += 1

        return conflicts

    def min_conflicts(self, max_steps=5000):
        """
        Solves the CSP locally using the Min-Conflicts heuristic.
        Starts from a random complete assignment and iteratively repairs
        randomly chosen conflicted events by minimising local hard-constraint
        violations.  An incrementally maintained `group_day_times` index makes
        every conflict evaluation O(groups per event) instead of O(all events).
        
        Args:
            max_steps (int): Maximum number of repair iterations.
            
        Returns:
            dict: The fully feasible state if found, otherwise the state with
                  the fewest global hard-constraint violations seen.
        """
        import random
        from collections import defaultdict

        current = self.generate_random_state()

        slot_to_events  = defaultdict(set)
        group_day_times = defaultdict(set)
        for eid, (rid, slt) in current.items():
            slot_to_events[slt].add(eid)
            day = slt // 6
            t   = slt % 6
            for g in self._get_event_groups(self.events_by_id[eid]):
                group_day_times[(g, day)].add(t)

        conflicted = set()
        for eid in current:
            rid, slt = current[eid]
            if self.local_conflicts(eid, rid, slt, current, slot_to_events, group_day_times) > 0:
                conflicted.add(eid)

        min_global_violations = self.evaluate_csp(current)
        best_state = current.copy()

        for i in range(max_steps):
            if not conflicted:
                return current

            var = random.choice(list(conflicted))
            old_rid, old_slot = current[var]
            old_day  = old_slot // 6
            old_time = old_slot % 6

            slot_to_events[old_slot].discard(var)
            for g in self._get_event_groups(self.events_by_id[var]):
                group_day_times[(g, old_day)].discard(old_time)

            best_candidates = []
            min_c = float('inf')
            for new_rid in self.event_compatible_rooms[var]:
                for new_slot in range(30):
                    c = self.local_conflicts(var, new_rid, new_slot, current, slot_to_events, group_day_times)
                    if c < min_c:
                        min_c = c
                        best_candidates = [(new_rid, new_slot)]
                    elif c == min_c:
                        best_candidates.append((new_rid, new_slot))

            new_rid, new_slot = random.choice(best_candidates)
            new_day  = new_slot // 6
            new_time = new_slot % 6

            current[var] = (new_rid, new_slot)
            slot_to_events[new_slot].add(var)
            for g in self._get_event_groups(self.events_by_id[var]):
                group_day_times[(g, new_day)].add(new_time)

            affected = set(slot_to_events[old_slot]) | set(slot_to_events[new_slot]) | {var}
            for eid in affected:
                rid, slt = current[eid]
                if self.local_conflicts(eid, rid, slt, current, slot_to_events, group_day_times) > 0:
                    conflicted.add(eid)
                else:
                    conflicted.discard(eid)

            if i % 100 == 0:
                v = self.evaluate_csp(current)
                if v == 0:
                    return current
                if v < min_global_violations:
                    min_global_violations = v
                    best_state = current.copy()

        v = self.evaluate_csp(current)
        return current if v < min_global_violations else best_state
