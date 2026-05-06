# This is the class that implements main problem method, specific data-driven problems will enhirit from it 
class Problem:
    pass

class Constraints:
    # includes the constraints functions, seperated for clean structure
    def __init__(self, problem):
        self.problem = problem
    
    # build lookup tables once before looping, then check per constraint.
    def _build_lookup_tables(self, state):
        """
        Preprocesses the current schedule state into resource-centric lookup tables 
        for highly efficient constraint evaluation.

        Args:
            state (dict): The current assignment mapping event_id -> (roomid, slot).

        Returns:
            tuple: Four dictionaries mapping slots to rooms, groups, and teachers, 
                   plus a mapping of teachers to their assigned events.
        """
        from collections import defaultdict
        slot_to_rooms    = defaultdict(list)  
        slot_to_groups   = defaultdict(list)  
        slot_to_teachers = defaultdict(list)
        teacher_events   = defaultdict(list) 

        for event_id, (roomid, slot) in state.items():
            event = self.problem.events_by_id[event_id]
            teacher_id = event["teacher_id"]

            slot_to_rooms[slot].append(roomid)
            slot_to_teachers[slot].append(teacher_id)
            teacher_events[teacher_id].append(event_id)

            if event["type_id"] == 1: 
                for gid in self.problem.section_to_group[event["target_id"]]:
                    slot_to_groups[slot].append(gid)
            else:                      
                slot_to_groups[slot].append(event["target_id"])

        return slot_to_rooms, slot_to_groups, slot_to_teachers, teacher_events
    
    # Hard constraints methods
    # DOUBLE BOOKING

    def NO_ROOM_DOUBLE_BOOKING(self, slot_to_rooms, count=True):
        """
        Checks if any room is assigned to more than one event during the same timeslot.

        Args:
            slot_to_rooms (dict): Mapping of timeslots to lists of assigned room IDs.
            count (bool): If True, returns the total violation count. If False, returns False on the first violation.

        Returns:
            int | bool: The number of violations, or a boolean indicating validity.
        """
        violations = 0
        for slot, rooms in slot_to_rooms.items():
            v = len(rooms) - len(set(rooms))
            if not count and v > 0: return False
            violations += v
        return violations if count else True

    def NO_GROUP_DOUBLE_BOOKING(self, slot_to_groups, count=True):
        """
        Checks if any student group is scheduled for multiple events during the same timeslot.

        Args:
            slot_to_groups (dict): Mapping of timeslots to lists of assigned group IDs.
            count (bool): If True, returns the total violation count. If False, returns False on the first violation.

        Returns:
            int | bool: The number of violations, or a boolean indicating validity.
        """
        violations = 0
        for slot, groups in slot_to_groups.items():
            v = len(groups) - len(set(groups))
            if not count and v > 0: return False
            violations += v
        return violations if count else True

    def NO_TEACHER_DOUBLE_BOOKING(self, slot_to_teachers, count=True):
        """
        Checks if any teacher is scheduled to teach multiple events during the same timeslot.

        Args:
            slot_to_teachers (dict): Mapping of timeslots to lists of assigned teacher IDs.
            count (bool): If True, returns the total violation count. If False, returns False on the first violation.

        Returns:
            int | bool: The number of violations, or a boolean indicating validity.
        """
        violations = 0
        for slot, teachers in slot_to_teachers.items():
            v = len(teachers) - len(set(teachers))
            if not count and v > 0: return False
            violations += v
        return violations if count else True

    # ROOM SUITABILITY

    def ROOM_CAPACITY_GEQ_HEADCOUNT(self, state, count=True):
        """
        Ensures the assigned room's capacity is greater than or equal to the event's student headcount.

        Args:
            state (dict): The current schedule assignment.
            count (bool): If True, returns the violation count. If False, returns False on the first violation.

        Returns:
            int | bool: The number of violations, or a boolean indicating validity.
        """
        violations = 0
        for event_id, (roomid, slot) in state.items():
            event = self.problem.events_by_id[event_id]
            room  = self.problem.rooms_by_id[roomid]
            if room["capacity"] < event["headcount"]:
                if not count: return False
                violations += 1
        return violations if count else True

    def MATCH_ROOM_TYPE(self, state, count=True):
        """
        Ensures the assigned room type matches the required room type for the event (e.g., lecture hall vs lab).

        Args:
            state (dict): The current schedule assignment.
            count (bool): If True, returns the violation count. If False, returns False on the first violation.

        Returns:
            int | bool: The number of violations, or a boolean indicating validity.
        """
        violations = 0
        for event_id, (roomid, slot) in state.items():
            event = self.problem.events_by_id[event_id]
            room  = self.problem.rooms_by_id[roomid]
            if room["room_type_id"] != event["required_room_type_id"]:
                if not count: return False
                violations += 1
        return violations if count else True

    # SCHEDULING STRUCTURE

    def SEPARATE_LECTURE_PRACTICE(self, state, count=True):
        """
        Prevents scheduling a lecture and a practice session for the same course and group on the same day.

        Args:
            state (dict): The current schedule assignment.
            count (bool): If True, returns the violation count. If False, returns False on the first violation.

        Returns:
            int | bool: The number of violations, or a boolean indicating validity.
        """
        from collections import defaultdict
        key_to_types = defaultdict(list)
        for event_id, (roomid, slot) in state.items():
            event = self.problem.events_by_id[event_id]
            day   = slot // 6
            groups = (self.problem.section_to_group[event["target_id"]]
                    if event["type_id"] == 1 else [event["target_id"]])
            for gid in groups:
                key_to_types[(gid, event["course_name"], day)].append(event["type_id"])

        violations = 0
        for (gid, course, day), types in key_to_types.items():
            if any(t == 1 for t in types) and any(t != 1 for t in types):
                if not count: return False
                violations += 1
        return violations if count else True

    def CONSECUTIVE_SECTION_LECTURES(self, state, count=True):
        """
        Ensures that if a course has multiple lectures for a section, they are scheduled in consecutive slots.

        Args:
            state (dict): The current schedule assignment.
            count (bool): If True, returns the violation count. If False, returns False on the first violation.

        Returns:
            int | bool: The number of violations, or a boolean indicating validity.
        """
        from collections import defaultdict
        course_slots = defaultdict(list)
        for event_id, (roomid, slot) in state.items():
            event = self.problem.events_by_id[event_id]
            if event["type_id"] == 1:
                course_slots[event["course_name"]].append(slot)

        violations = 0
        for course, slots in course_slots.items():
            if len(slots) < 2: continue
            for i in range(len(slots)):
                for j in range(i + 1, len(slots)):
                    if not ((slots[i] // 6) == (slots[j] // 6) and abs(slots[i] - slots[j]) == 1):
                        if not count: return False
                        violations += 1
        return violations if count else True

    def MAX_CONSECUTIVE_STUDENT_SLOTS_3(self, state, count=True):
        """
        Ensures no student group is scheduled for more than 3 consecutive timeslots without a break.

        Args:
            state (dict): The current schedule assignment.
            count (bool): If True, returns the violation count. If False, returns False on the first violation.

        Returns:
            int | bool: The number of violations, or a boolean indicating validity.
        """
        from collections import defaultdict
        group_day_slots = defaultdict(lambda: defaultdict(set))
        for event_id, (roomid, slot) in state.items():
            event = self.problem.events_by_id[event_id]
            day, time = slot // 6, slot % 6
            groups = (self.problem.section_to_group[event["target_id"]]
                    if event["type_id"] == 1 else [event["target_id"]])
            for gid in groups:
                group_day_slots[gid][day].add(time)

        violations = 0
        for gid, days in group_day_slots.items():
            for day, times in days.items():
                sorted_times = sorted(times)
                run = max_run = 1
                for k in range(1, len(sorted_times)):
                    run = run + 1 if sorted_times[k] == sorted_times[k-1] + 1 else 1
                    max_run = max(max_run, run)
                if max_run > 3:
                    if not count: return False
                    violations += 1
        return violations if count else True

    # soft constraints methods

    # external constraints
    def SIMILAR_ACTIVITIES(self, state, weight):
        from collections import defaultdict

        course_slots = defaultdict(list)
        # O(n)
        for event_id, (roomid, slot) in state.items():
            event_data = self.problem.events_by_id[event_id]
            if event_data["type_id"] != 1: continue
            course_slots[event_data["course_name"]].append(slot)

        non_similar = 0
        for c, s in course_slots.items():
            if len(s) < 2: continue # only one section
            # check for evey pair of secrions (useful if ensia will have many per year)
            # O(k^2) where k is section count which is 2-3 so not costly
            for i in range(len(s)):
                for j in range(i+1, len(s)):
                    diff = abs(s[i] - s[j])
                    same_day = (s[i] // 6) == (s[j] // 6)
                    if not (diff == 1 and same_day):
                        non_similar += 1
        return non_similar * weight

    def MINIMIZE_WASTED_SEATS(self, state, weight):
        # O(n) per call
        wasted = 0
        for event_id, (roomid, slot) in state.items():
            event_data = self.problem.events_by_id[event_id]
            room_data = self.problem.rooms_by_id[roomid]
            wasted += (room_data["capacity"] - event_data["headcount"]) / room_data["capacity"] # take the percentage wasted 
        return wasted * weight

    # general constraints
    def MORNING_LECTURES(self, event, roomid, slot, weight):
        # give a penalty as the lectures go to the afternoon
        parameter = 0
        time = slot % 6
        if time == 0 or time == 1: return 0
        match time:
            case 2: parameter = 1
            case 3: parameter = 1.5
            case 4: parameter = 2
            case 5: parameter = 2.5
        return parameter * weight

    # group an teacher constraints
    def MINIMIZE_GAPS(self, schedule, weight):
        gaps = 0
        days_active = {0: [], 1: [], 2: [], 3: [], 4: []}
        for room, slot in schedule: days_active[slot // 6].append((room, slot % 6))
        # traversing sessions to look for gaps
        for day, classes in days_active.items():
            classes.sort(key=lambda x: x[1])
            for i in range(len(classes) - 1):
                time1 = classes[i][1]
                time2 = classes[i+1][1]
                diff = time2 - time1  # the diffrence between any two session
                if diff <= 1: continue # no gaps
                if diff == 2 and (time2 == 2 or time2 == 5): gaps += 1 # penalize one session gaps that doesn't fall in lunch break
                elif diff == 3 and time2 != 4: gaps += 1 # penalize two session gaps unless thay are in the break period 11:50-15:00
                else: gaps += 1.5 # penalize more the 4 and 5 session gaps
        return gaps * weight

    def AVOID_THURSDAY_AFTERNOON(self, schedule, weight):
        thursday_afternoon = {27, 28, 29}
        slots = [0, 0, 0]
        for room, slot in schedule:
            if slot in thursday_afternoon:
                slots[slot - 27] = 1
        return (slots[0] + 2 * slots[1] + 3 * slots[2]) * weight

    def AVOID_LAST_SLOT(self, schedule, weight):
        count = 0
        for room, slot in schedule:
            if slot % 6 == 5: count += 1
        return count * weight

    def MINIMIZE_ROOM_CHANGES(self, schedule, weight):
        room_change_cost = 0
        days_active = {0: [], 1: [], 2: [], 3: [], 4: []}
        for room, slot in schedule: days_active[slot // 6].append((room, slot % 6))
        # traversing sessions to look for consecutive sessions
        for day, classes in days_active.items():
            classes.sort(key=lambda x: x[1])
            for i in range(len(classes) - 1):
                room1, time1 = classes[i]
                room2, time2 = classes[i+1]
                diff = time2 - time1  # the diffrence between any two session
                if diff != 1: continue
                if room1 == room2: continue # 0 cost for staying at the same room
                # load rooms data
                room1_data = self.problem.rooms_by_id[room1]
                room2_data = self.problem.rooms_by_id[room2]

                r1_type, r1_floor = room1_data["room_type_id"], room1_data["floor"]
                r2_type, r2_floor = room2_data["room_type_id"], room2_data["floor"]
                # we compute the cost to travel from room1 to room2
                if r1_type == r2_type and r1_floor == r2_floor: room_change_cost += 0.5  #same zone
                elif r1_type != r2_type and r1_floor != r2_floor: room_change_cost += 2 # totaly different zone
                else: room_change_cost += 1 # partially different zone

        return room_change_cost * weight

    def MINIMIZE_TEACHER_DAYS(self, schedule, weight):
        days_active = {0: [], 1: [], 2: [], 3: [], 4: []}
        for room, slot in schedule: days_active[slot // 6].append((room, slot % 6))
        num_days = sum(1 for day in days_active.values() if day)
        num_sessions = sum(len(day) for day in days_active.values())
        if num_days < num_sessions // 3: return 0
        return weight * (num_days + 1 - (num_sessions // 3)) # the penalty increases with every additional day


# ensia specific problem class
class EnsiaProblem(Problem):
    def __init__(self, dataset, cspmethod="global_search"):
        super().__init__()

        # load data elements
        data = self.load_data(dataset)
        self.rooms = data[0]
        self.events = data[3]
        self.groups = data[2]
        # a table that stores the assignment of groups to section section_id => [group_id, group_id, ..]
        self.section_to_group = {section["id"] : [] for section in data[1]}
        for group in self.groups: self.section_to_group[group["section_id"]].append(group["id"])
        # access data elements by their id
        self.events_by_id = {e["id"]: e for e in self.events}
        self.rooms_by_id  = {r["id"]:  r for r in self.rooms}
        self.groups_by_id  = {r["id"]:  r for r in self.groups}

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
            state = self.enhance(state) # does local search csp to resolve all hard constraints
            self.state = state
        else:
            if cspmethod != "global_search": print("invalid csp method, redirecting to GS csp ...\n")
            self.state = self.generate_valid_state()
        

        

    def load_data(self, filename):
        """
        Loads the semester JSON data and converts the dictionary structure into 
        an indexed list format compatible with the constructor.
        
        Args:
            filename (str): Path to the data_sX.json file.
            
        Returns:
            list: [rooms, sections, groups, events, constraints]
        """
        import json
        import os

        # Check if file exists to avoid crashes
        if not os.path.exists(filename):
            raise FileNotFoundError(f"Dataset file {filename} not found.")
        
        with open(filename, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
        
        # Mapping dict keys to the specific list order expected by __init__
        # data[0]=rooms, [1]=sections, [2]=groups, [3]=events, [4]=constraints
        return [
            raw_data.get("rooms", []),
            raw_data.get("sections", []),
            raw_data.get("groups", []),
            raw_data.get("activities", []),
            raw_data.get("constraints", {})
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
        from collections import defaultdict
        
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

        import random
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

        from collections import defaultdict

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
        import random
        shuffled_slots = random.sample(self.slots, len(self.events))
        return {event["id"]: slot for event, slot in zip(self.events, shuffled_slots)}

    def enhance(self, state, method="hill_climbing_steepest", objective=None):
        """
        Applies a local search algorithm to iteratively improve a schedule 
        by resolving hard constraint violations. Includes random restarts to escape local optima.

        Args:
            state (dict): The initial schedule assignment.
            method (str): The local search heuristic to use (default: "hill_climbing_steepest").

        Returns:
            dict: The optimized state with minimized (ideally zero) constraint violations.

        Raises:
            ValueError: If an unknown search method is provided.
        """
        from optimizer import Optimizer
        opt = Optimizer()

        if objective is None:
            objective = self.evaluate_csp  # default to hard constraints

        MAX_RESTARTS = 20
        current = dict(state)

        method_map = {
            "hill_climbing_steepest":        (opt.Hill_Climbing,                {"strategy": "steepest"}),
            "hill_climbing_first":           (opt.Hill_Climbing,                {"strategy": "first_choice"}),
            "hill_climbing_stochastic":      (opt.Hill_Climbing,                {"strategy": "stochastic"}),
            "hill_climbing_random_restart":  (opt.Random_Restart_Hill_Climbing, {}),
            "simulated_annealing":           (opt.Simulated_Annealing,         {"initial_temp": 100.0, "cooling_rate": 0.1, "max_iterations": 1000}),
            "tabu_search":                   (opt.Tabu_Search,                 {}),
        }
        if method not in method_map:
            raise ValueError(f"Unknown method '{method}'. Choose from {list(method_map)}")

        search_fn, kwargs = method_map[method]

        for _ in range(MAX_RESTARTS):
            self.state = current
            result, cost = search_fn(problem=self, objective=objective, **kwargs)

            if cost == 0:
                return result

            import random
            kicked = dict(result)
            for _ in range(5):
                eid = random.choice(list(kicked.keys()))
                kicked[eid] = random.choice(self.slots)
            current = kicked

        return result


    def generate_neighbors(self, state, event_id, size=50, shuffle=False):
        import random

        # returns at most size states by assigning possible slots to a state
        if shuffle:
            random.shuffle(self.slots)
        
        original_slot = state[event_id]

        for slot in self.slots:
            state[event_id] = slot
            for hc in self.hard_constraints_list:
                if isinstance(hc, str): continue 
                rule_function = getattr(self.constraint_obj, hc["rule"]) 
                if rule_function(state):
                    break
            else:
                # if no hard constraint is violated, i.e. for loop terminated without breaking
                yield state
                size -= 1
                if size <= 0:
                    break

        # last part on how this function is used and what is expected
        state[event_id] = original_slot

    def move_operator(self, state, shuffle=False):
        import random

        attempted = set()
        valid_events = list(state.keys())

        while len(attempted) < len(valid_events):
            event_id = random.choice(valid_events)
            while event_id in attempted:
                event_id = random.choice(valid_events)
            
            old_slot = state[event_id]
            state[event_id] = None
            
            for neighbor in self.generate_neighbors(state, event_id, size=2, shuffle=shuffle):
                state[event_id] = old_slot
                return neighbor
            
            state[event_id] = old_slot
            attempted.add(event_id)
            
        return state
    
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
            violations += fn(*args, count=True)
        return violations
