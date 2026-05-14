from contraints import *
from collections import defaultdict
import copy 
import random
import json
import os

# This is the class that implements main problem method, specific data-driven problems will enhirit from it 
class Problem:
    pass

# ensia specific problem class
class EnsiaProblem(Problem):
    def __init__(self, dataset, cspmethod="global_search"):
        super().__init__()

        # load data elements
        data = self.load_data(dataset)
        self.rooms = data[0]
        self.events = data[3]
        self.groups = data[2]
        self.teachers = data[5]
        # a table that stores the assignment of groups to section section_id => [group_id, group_id, ..]
        self.section_to_group = {section["id"] : [] for section in data[1]}
        for group in self.groups: self.section_to_group[group["section_id"]].append(group["id"])
        # access data elements by their id
        self.events_by_id = {e["id"]: e for e in self.events}
        self.rooms_by_id  = {r["id"]:  r for r in self.rooms}
        self.groups_by_id  = {r["id"]:  r for r in self.groups}
        self.teachers_by_id = {t["id"]: t for t in self.teachers}

        # fill the (room, time) tuple, assuming time is a number from 0-29
        slots = []
        for r in self.rooms:
            for t in range(30):
                slots.append((r["id"], t))
        self.slots = slots
        
        # get constraint list -not handled yet-
        self.hard_constraints_list = data[4].get("hard", [])
        self.soft_constraints_list = data[4].get("soft", [])

        # constraint object to hold the methods
        self.constraint_obj = Constraints(self)

        # the state of the problem is a dict in the form:
        #  eventid -> (roomid, timeslot(day, slot)) 
        if cspmethod == "local_search":
            state = self.generate_random_state() # generate a random assignment that might violate hard constraints
            self.state = state
        else:
            if cspmethod != "global_search": 
                print("invalid csp method, redirecting to GS csp ...\n")
            self.state = self.generate_valid_state()
        
        


    def load_data(self, filename):
        """
        Loads the semester JSON data and converts the dictionary structure into 
        an indexed list format compatible with the constructor.
        
        Args:
            filename (str): Path to the data_sX.json file.
            
        Returns:
            list: [rooms, sections, groups, events, constraints, teachers]
        """

        # Check if file exists to avoid crashes
        if not os.path.exists(filename):
            raise FileNotFoundError(f"Dataset file {filename} not found.")
        
        with open(filename, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
        
        # Mapping dict keys to the specific list order expected by __init__
        # data[0]=rooms, [1]=sections, [2]=groups, [3]=events, [4]=constraints, [5]=teachers
        return [
            raw_data.get("rooms", []),
            raw_data.get("sections", []),
            raw_data.get("groups", []),
            raw_data.get("activities", []),
            raw_data.get("constraints", {}),
            raw_data.get("teachers", [])
        ]
    
    # CSP Global

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
        # Type ID 1 indicates a lecture, which targets an entire section
        if event["type_id"] == 1:
            return self.section_to_group[event["target_id"]]
        
        # Otherwise, the target is just a single group
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
        
        # Temporary mappings to group events by their shared properties
        teacher_map = defaultdict(set)
        group_map   = defaultdict(set)
        course_map  = defaultdict(set)

        for eid in event_ids:
            e = self.events_by_id[eid]
            teacher_map[e["teacher_id"]].add(eid)
            course_map[e["course_name"]].add(eid)
            for gid in self._get_event_groups(e):
                group_map[gid].add(eid)

        # Build the final neighbor sets using the temporary mappings
        neighbours = {eid: set() for eid in event_ids}
        for eid in event_ids:
            e = self.events_by_id[eid]
            neighbours[eid] |= teacher_map[e["teacher_id"]]
            neighbours[eid] |= course_map[e["course_name"]]
            for gid in self._get_event_groups(e):
                neighbours[eid] |= group_map[gid]
                
            # An event cannot be its own neighbor
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
        
        # Cross-product of all compatible rooms and all 30 weekly time slots
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
        # Extract properties of the newly assigned event
        assigned_event   = self.events_by_id[assigned_eid]
        assigned_teacher = assigned_event["teacher_id"]
        assigned_groups  = set(self._get_event_groups(assigned_event))
        assigned_course  = assigned_event["course_name"]
        assigned_is_lec  = (assigned_event["type_id"] == 1)
        
        # Calculate day (0-4) and time of day (0-5)
        assigned_day     = slot // 6
        assigned_time    = slot % 6

        removals = {}

        # Iterate only through neighbors that haven't been assigned yet
        for neid in neighbours[assigned_eid]:
            if neid not in unassigned_set:
                continue

            # Extract properties of the neighboring event
            nevent      = self.events_by_id[neid]
            nteacher    = nevent["teacher_id"]
            ngroups     = set(self._get_event_groups(nevent))
            ncourse     = nevent["course_name"]
            n_is_lec    = (nevent["type_id"] == 1)
            
            shared_grps = assigned_groups & ngroups
            same_course = (ncourse == assigned_course)

            to_remove = set()
            domain    = self._domains[neid]

            # Check each possibility in the neighbor's current domain
            for (nr, ns) in domain:
                nday  = ns // 6
                ntime = ns % 6
                bad   = False

                # Prevent double-booking the same room
                if nr == roomid and ns == slot:
                    bad = True

                # Prevent double-booking the same teacher
                elif nteacher == assigned_teacher and ns == slot:
                    bad = True

                # Prevent double-booking overlapping student groups
                elif shared_grps and ns == slot:
                    bad = True

                # Handle course-specific scheduling rules
                elif same_course and shared_grps:
                    # Lectures and practice sessions for the same course cannot be on the same day
                    if (assigned_is_lec and not n_is_lec) or \
                       (not assigned_is_lec and n_is_lec):
                        if nday == assigned_day:
                            bad = True

                    # Multiple lectures for the same course must be consecutive
                    elif assigned_is_lec and n_is_lec:
                        adj = {slot - 1, slot + 1}
                        adj = {a for a in adj if a // 6 == assigned_day and 0 <= a % 6 <= 5}
                        if ns not in adj:
                            bad = True

                # Prevent groups from having more than 3 consecutive classes
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

                # If the domain value violates a rule, mark it for removal
                if bad:
                    to_remove.add((nr, ns))

            if to_remove:
                removals[neid] = to_remove

        return removals

    def _bt(self, unassigned_set, state, neighbours):
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
        # Base case: All events are assigned
        if not unassigned_set:
            if self.is_consistent(state, is_complete=True):
                return state
            return None

        # MRV Heuristic: Pick the event with the fewest valid domain options left
        mrv_eid = min(unassigned_set, key=lambda e: len(self._domains[e]))

        # Domain wipeout: No valid options left for this event
        if not self._domains[mrv_eid]:
            return None     

        unassigned_set.remove(mrv_eid)
        event      = self.events_by_id[mrv_eid]
        teacher_id = event["teacher_id"]
        groups     = self._get_event_groups(event)

        # Shuffle candidates to introduce randomness in the final schedule
        candidates = list(self._domains[mrv_eid])
        random.shuffle(candidates)

        for roomid, slot in candidates:
            day  = slot // 6
            time = slot % 6

            # Apply the tentative assignment
            state[mrv_eid] = (roomid, slot)
            self.busy_rooms.add((roomid, slot))
            self.busy_teachers.add((teacher_id, slot))
            for gid in groups:
                self.busy_groups.add((gid, slot))
                self.group_day_times[gid][day].add(time)

            # Perform forward checking to prune neighbor domains
            removals = self._removed_by_assignment(
                mrv_eid, roomid, slot, unassigned_set, neighbours
            )
            
            # Check if applying these removals empties any neighbor's domain completely
            wipeout = any(
                len(self._domains[n]) - len(rm) == 0
                for n, rm in removals.items()
            )

            # If no wipeout, proceed with recursion
            if not wipeout:
                # Remove invalid options from neighbor domains
                for n, rm in removals.items():
                    self._domains[n] -= rm

                # Recursively solve the rest of the schedule
                result = self._bt(unassigned_set, state, neighbours)
                if result is not None:
                    return result

                # Backtrack: Restore neighbor domains if recursion failed
                for n, rm in removals.items():
                    self._domains[n] |= rm

            # Backtrack: Undo the tentative assignment and clean up trackers
            del state[mrv_eid]
            self.busy_rooms.discard((roomid, slot))
            self.busy_teachers.discard((teacher_id, slot))
            for gid in groups:
                self.busy_groups.discard((gid, slot))
                self.group_day_times[gid][day].discard(time)

        # Restore the event to the unassigned pool before returning failure
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
        # Precompute all compatible rooms for every event based on capacity and type
        # for each event id , we store the rooms that we are sure that we can book there
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

        # Initialize global tracking sets for fast collision detection
        self.busy_rooms    = set()
        self.busy_teachers = set()
        self.busy_groups   = set()
        self.group_day_times = {
            gid: {day: set() for day in range(5)}
            for gid in self.groups_by_id
        }


        # Helper mapping to determine which year an event belongs to
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

        # Group events by year to solve in smaller, isolated batches
        by_year = defaultdict(list)
        for e in self.events:
            by_year[event_year(e["id"])].append(e["id"])
            
        full_state = {}

        # Solve the schedule sequentially, year by year
        for year, eids in sorted(by_year.items()):
            neighbours = self._precompute_neighbours(eids)

            # Initialize domain for this subset of events
            self._domains = {eid: self._build_initial_domain(eid) for eid in eids}

            unassigned = set(eids)
            sub_state  = {}

            # Run backtracking on this specific year
            result = self._bt(unassigned, sub_state, neighbours)
            if result is None:
                raise RuntimeError(
                    f"No valid schedule found for year {year} — constraints may be too tight."
                )
                
            # Merge the sub-schedule into the full schedule
            full_state.update(result)

        return full_state

    def is_consistent(self, state, is_complete=False):
        """
        Validates the current state against all hard constraints that are not already handled 
        by the forward-checking logic.
        
        Args:
            state (dict): The current schedule mapping event_ids to (room, slot).
            is_complete (bool): Indicates if the state is complete (all events assigned).
            
        Returns:
            bool: True if the state violates no active hard constraints, False otherwise.
        """
        # Build lookup tables necessary for evaluating complex external constraints
        slot_to_rooms, slot_to_groups, slot_to_teachers, teacher_events = \
            self.constraint_obj._build_lookup_tables(state)
        c = self.constraint_obj

        # Map constraint categories to the required arguments for their specific functions
        category_args = {
            "slot_to_rooms":    (slot_to_rooms,),
            "slot_to_groups":   (slot_to_groups,),
            "slot_to_teachers": (slot_to_teachers,),
            "state_based":      (state,),
            "teacher_based":    (teacher_events,),
        }

        # These rules are enforced during domain pruning, so we skip them here for efficiency
        forward_checked_rules = [
            "NO_ROOM_DOUBLE_BOOKING", 
            "NO_GROUP_DOUBLE_BOOKING", 
            "NO_TEACHER_DOUBLE_BOOKING",
            "ROOM_CAPACITY_GEQ_HEADCOUNT", 
            "MATCH_ROOM_TYPE",
            "CONSECUTIVE_SECTION_LECTURES",
            "SEPARATE_LECTURE_PRACTICE",
            "MAX_CONSECUTIVE_STUDENT_SLOTS_3"
        ]

        # Evaluate all remaining hard constraints dynamically
        for hc in self.hard_constraints_list:
            if isinstance(hc, str): continue 
            
            rule = hc["rule"]
            if rule in forward_checked_rules:
                continue 

            # Dynamically call the constraint function and fail if it returns False
            fn   = getattr(c, rule)
            args = category_args[hc["category"]]
            if not fn(*args, count=False): 
                return False
                
        return True
    
    # CSP Local

    def generate_random_state(self):
        """
        Generates a random schedule assignment, but with no double booking.
        Used primarily as the initial starting point for local search algorithms.

        Returns:
            dict: A randomly generated state mapping event_id -> (roomid, slot).
        """
        shuffled_slots = random.sample(self.slots, len(self.events))
        return {event["id"]: slot for event, slot in zip(self.events, shuffled_slots)}

    # by the generator function for next states
    def swapper_napper(self,state,iteration=10):
        """
            given a state , returns a state there the some keys and there values are swapped
            only used for testing purposes for now.
        """
        course = list(state.keys())

        temp_state = state.copy()

        for i in range(iteration):
            selected1 = random.choice(course)
            selected2 = random.choice(course)

            values1 = temp_state[selected1]

            temp_state[selected1] = temp_state[selected2]
            temp_state[selected2] = values1

        if not self.is_consistent(temp_state,is_complete=True):
            return temp_state

        return temp_state

    def shifter_nifter(self, state, iteration=10, direction="left", amount=1):
        if direction not in ["left", "right"]:
            return state

        # i head doing this is faster idk
        new_state = state.copy()

        # pre-calculate available slots per room
        room_availability = {rid: set(range(30)) for rid in self.rooms_by_id.keys()}
        for eid, (rid, slot) in new_state.items():
            if rid in room_availability:
                room_availability[rid].discard(slot)

        events = list(new_state.keys())

        for _ in range(iteration):
            target_event = random.choice(events)
            room_id, old_slot = new_state[target_event]

            # calc the shifted slot based on parameters
            shift = -amount if direction == "left" else amount
            # wrap around the week/day
            ideal_slot = (old_slot + shift) % 30            
            # logic: if the ideal shifted slot is free, take it. 
            # otherwise, this specitic shift is invalid.
            if ideal_slot in room_availability[room_id]:
                # apply Move
                new_state[target_event] = (room_id, ideal_slot)
                room_availability[room_id].remove(ideal_slot)
                room_availability[room_id].add(old_slot)

                if self.is_consistent(new_state, is_complete=True):
                    return new_state
                else:
                    new_state[target_event] = (room_id, old_slot)
                    room_availability[room_id].add(ideal_slot)
                    room_availability[room_id].remove(old_slot)

        return state # Return original if no valid shifts were found

    def move_to_another_slot(self,state,iteration=10):
        """
            Returns another state where some events have there slots changed completly
        """

        all_rooms = [key for key,_ in self.rooms_by_id.items()]
        ## initial population
        available_slots = dict()
        for room_id in all_rooms:
            available_slots[room_id] = set([i for i in range(5*6)])

        # Purge the set of all slots and remove the onces used 
        # to get the onces available 
        for key, (room_id,slot) in state.items():
            if slot in available_slots:
                available_slots[room_id].remove(slot)

        events = list(state.keys())

        for i in range(iteration):
            # select to be swapped
            event = random.choice(events)
            # get previous data
            (roomd_id, slot) = state[event]
            # get next slot
            next_slot = random.choice(list(available_slots[roomd_id]))
            # update the state and the available_slots
            # print("moving rn rn")
            state[event] = (roomd_id, next_slot)

            available_slots[roomd_id].remove(next_slot)
            available_slots[roomd_id].add(slot)

        if not self.is_consistent(state):
            return self.move_to_another_slot(fall_back)

        return state


    def pipeline_generate_neighbors(self, state, size=50):
        """
            This function will return a list of next neighbors that will be passed 
            by reference through a pipeline of changes ... (basically is a generate_neighbors)

            WARNING: this function assumes the state given is a valid state , therefore it wont work as 
            expected in case of solving a CSP using local search
        """
        neighbors = []

        for _ in range(size):
            n = state.copy()

            n = self.move_to_another_slot(n, iteration=10)
            n = self.swapper_napper(n, iteration=5)
            n = self.shifter_nifter(n, iteration=10, direction="left", amount=4)
            n = self.shifter_nifter(n, iteration=10, direction="right", amount=4)

            neighbors.append(n)

        return neighbors

    def generate_neighbors(self, state, size=50):
        """
            Uses the pipeline generator to generate n neighbors
        """
        return self.pipeline_generate_neighbors(state,size=size)

    def move_operator(self, state):
        """
            Uses the pipeline to generate a single neighbor
        """
        return self.pipeline_generate_neighbors(state,size=1)[0]

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
        prof_constraints     = [sc for sc in self.soft_constraints_list if sc["category"] in ("prof",  "group-prof")]

        for ec in external_constraints:
            constraint_function = getattr(self.constraint_obj, ec["rule"])
            add_cost += constraint_function(state, ec["weight"])

        for event_id, (roomid, slot) in state.items():
            event_data = self.events_by_id[event_id]   # fix: [] not ()
            if not event_data: continue

            prof_id   = event_data["teacher_id"]
            target_id = event_data["target_id"]

            for gc in general_constraints:
                constraint_function = getattr(self.constraint_obj, gc["rule"])
                add_cost += constraint_function(event_data, roomid, slot, gc["weight"])

            if prof_id not in prof_schedules:
                prof_schedules[prof_id] = []
            prof_schedules[prof_id].append((roomid, slot))

            if event_data["type_id"] == 1:              # fix: type_id not type
                for group_id in self.section_to_group[target_id]:
                    group_schedules[group_id].append((roomid, slot))   # fix: no reset
            else:
                group_schedules[target_id].append((roomid, slot))      # fix: no reset

        for prof_id, sched in prof_schedules.items():
            for pc in prof_constraints:
                constraint_function = getattr(self.constraint_obj, pc["rule"])
                profs_cost += constraint_function(sched, pc["weight"])  # fix: local fn

        for group_id, sched in group_schedules.items():
            for grc in group_constraints:
                constraint_function = getattr(self.constraint_obj, grc["rule"])  # fix: grc
                groups_cost += constraint_function(sched, grc["weight"])

        # fix: normalise outside the loop, guard against empty
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
            violations += fn(*args, count=True)  # here were we fixed and the explanation is gonna be in report 
        return violations
