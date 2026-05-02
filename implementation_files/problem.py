
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

    # TEACHER WORKLOAD

    def _teacher_total_hours(self, teacher_events):
        """
        Helper method to calculate the total assigned teaching hours for each teacher.

        Args:
            teacher_events (dict): Mapping of teacher IDs to lists of their assigned event IDs.

        Returns:
            dict: Mapping of teacher_id -> total_hours (float).
        """
        from collections import defaultdict
        hours = defaultdict(float)
        for teacher_id, event_ids in teacher_events.items():
            for eid in event_ids:
                hours[teacher_id] += self.problem.events_by_id[eid]["duration_hours"]
        return hours

    def TEACHER_MIN_HOURS_9(self, teacher_events, count=True):
        """
        Ensures each active teacher meets the minimum required workload of 9 hours.

        Args:
            teacher_events (dict): Mapping of teacher IDs to lists of their assigned event IDs.
            count (bool): If True, returns the violation count. If False, returns False on the first violation.

        Returns:
            int | bool: The number of violations, or a boolean indicating validity.
        """
        violations = 0
        hours = self._teacher_total_hours(teacher_events)
        for teacher_id, h in hours.items():
            if h < 9:
                if not count: return False
                violations += 1
        return violations if count else True

    def TEACHER_MAX_HOURS_17(self, teacher_events, count=True):
        """
        Ensures no teacher exceeds the maximum allowed workload of 17 hours.

        Args:
            teacher_events (dict): Mapping of teacher IDs to lists of their assigned event IDs.
            count (bool): If True, returns the violation count. If False, returns False on the first violation.

        Returns:
            int | bool: The number of violations, or a boolean indicating validity.
        """
        violations = 0
        hours = self._teacher_total_hours(teacher_events)
        for teacher_id, h in hours.items():
            if h > 17:
                if not count: return False
                violations += 1
        return violations if count else True

    def TEACHER_MAX_COURSES_2(self, teacher_events, count=True):
        """
        Ensures a teacher is not assigned to teach more than 2 distinct courses.

        Args:
            teacher_events (dict): Mapping of teacher IDs to lists of their assigned event IDs.
            count (bool): If True, returns the violation count. If False, returns False on the first violation.

        Returns:
            int | bool: The number of violations, or a boolean indicating validity.
        """
        violations = 0
        for teacher_id, event_ids in teacher_events.items():
            courses = {self.problem.events_by_id[eid]["course_name"] for eid in event_ids}
            if len(courses) > 2:
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
        slots = [] # 3 sessions of thursday afternoon
        for i in range(3):
            slots[i] = 1 if any(slots == 27 + i for room, slot in schedule) else 0
        return (slots[0] + 2*slots[1] + 3*slots[2]) * weight

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
        self.section_to_group = {section : [] for section in data[1]}
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
        self.hard_constraints_list = [con["hard"] for con in data[4] if "hard" in data[4]] # explicit list of hard constraints
        self.soft_constraints_list = [con["soft"] for con in data[4] if "soft" in data[4]] # list of soft constraints in the form (rule, weight)

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

    def is_consistent(self, state):
        """
        Evaluates a complete or partial state against all hard constraints.

        Args:
            state (dict): The current assignment mapping event_id -> (roomid, slot).

        Returns:
            bool: True if no hard constraints are violated, False otherwise.
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

        for hc in self.hard_constraints_list:
            fn   = getattr(c, hc["rule"])
            args = category_args[hc["category"]]
            if not fn(*args, count=False): 
                return False
        return True
    
    def generate_valid_state(self):
        """
        Initiates a backtracking search to find a schedule satisfying all hard constraints.
        Events are ordered by type and headcount to optimize the search tree.

        Returns:
            dict: A fully valid state mapping event_id -> (roomid, slot).

        Raises:
            RuntimeError: If no valid schedule can be mathematically found.
        """
        import random
        ordered_events = sorted(
            self.events,
            key=lambda e: (0 if e["type_id"] == 1 else 1, -e["headcount"])
        )
        random.shuffle(ordered_events) 
        state  = {}
        result = self._backtrack(ordered_events, 0, state)
        if result is None:
            raise RuntimeError("No valid schedule found — check your data.")
        return result

    def _backtrack(self, ordered_events, index, state):
        """
        Recursive helper method that performs depth-first search to assign events.

        Args:
            ordered_events (list): Events sorted by difficulty (lectures/large classes first).
            index (int): The current index in the ordered_events list being assigned.
            state (dict): The partial schedule assignment being built.

        Returns:
            dict | None: The completed valid state, or None if the current path fails.
        """
        import random

        if index == len(ordered_events):
            return state 

        event    = ordered_events[index]
        event_id = event["id"]

        if not state:
            candidates = [(r["id"], s) for r in self.rooms for s in range(30)]
            random.shuffle(candidates)
        else:
            candidates = [(r["id"], s) for r in self.rooms for s in range(30)]
            random.shuffle(candidates)

        for roomid, slot in candidates:
            state[event_id] = (roomid, slot)
            if self.is_consistent(state):                  
                result = self._backtrack(ordered_events, index + 1, state)
                if result is not None:
                    return result
            del state[event_id]

        return None

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

    def enhance(self, state, method="hill_climbing_steepest"):
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

        MAX_RESTARTS = 20
        current = dict(state)

        method_map = {
            "hill_climbing_steepest":        (opt.Hill_Climbing,               {"strategy": "steepest"}),
            "hill_climbing_first":           (opt.Hill_Climbing,               {"strategy": "first"}),
            "hill_climbing_stochastic":      (opt.Hill_Climbing,               {"strategy": "stochastic"}),
            "hill_climbing_random_restart":  (opt.Random_Restart_Hill_Climbing, {}),
            "simulated_annealing":           (opt.Simulated_Annealing,         {}),
            "tabu_search":                   (opt.Tabu_Search,                 {}),
        }
        if method not in method_map:
            raise ValueError(f"Unknown method '{method}'. Choose from {list(method_map)}")

        search_fn, kwargs = method_map[method]

        for _ in range(MAX_RESTARTS):
            self.state = current
            result, cost = search_fn(problem=self, objective=self.evaluate_csp, **kwargs)

            if cost == 0:
                return result

            import random
            kicked = dict(result)
            for _ in range(5):
                eid = random.choice(list(kicked.keys()))
                kicked[eid] = random.choice(self.slots)
            current = kicked

        return result


    def generate_neighbors(state, size=50): # returns at most size states
        pass
    def move_operator(self):
        return self.generate_neighbors(1)
    
    def evaluate(self, state):
        # returnes the cost of a state, may need other constraint-specific methodes
        groups_cost = 0
        profs_cost = 0
        add_cost = 0
        # initialize empty timetables for each group and prof
        group_schedules = {g : [] for g in self.groups_by_id}
        prof_schedules = {}
        # devide constraints
        external_constraints = [sc for sc in self.soft_constraints_list if sc["category"] == "external"]
        general_constraints = [sc for sc in self.soft_constraints_list if sc["category"] == "general"]
        group_constraints = [sc for sc in self.soft_constraints_list if sc["category"] == "group" or sc["category"] == "group-prof"]
        prof_constraints = [sc for sc in self.soft_constraints_list if sc["category"] == "prof" or sc["category"] == "group-prof"]

        for ec in external_constraints:
            constraint_function = getattr(self.constraint_obj, ec["rule"])
            add_cost += constraint_function(state, ec["weight"])


        for event_id, (roomid, slot) in state.items():
            event_data = self.events_by_id(event_id)
            if not event_data: continue

            prof_id = event_data["teacher_id"]
            target_id = event_data["target_id"] # may be a section

            # general constraits
            for gc in general_constraints: 
                constraint_function = getattr(self.constraint_obj, gc["rule"])
                add_cost += constraint_function(event_data, roomid, slot, gc["weight"])
            # fill in group and prof schedules
            if prof_id not in prof_schedules: prof_schedules[prof_id] = []
            prof_schedules[prof_id].append((roomid, slot))
            
            if event_data["type"] == 1: # if the event is a lecture, add it to all the groups of that section
                for group_id in self.section_to_group[target_id]:
                    group_schedules[group_id] = []
                    group_schedules[group_id] .append((roomid, slot))
            else:
                group_schedules[target_id] = []
                group_schedules[target_id] .append((roomid, slot))

            # handle each prof and group alone
        for prof_id, sched in prof_schedules.items():
            for pc in prof_constraints:
                constraint_function = getattr(self.constraint_obj, pc["rule"])
                profs_cost += constraint_obj.constraint_function(sched, pc["weight"])

        for group_id, sched in group_schedules.items():
            for grc in group_constraints:
                constraint_function = getattr(self.constraint_obj, gc["rule"])
                groups_cost += constraint_obj.constraint_function(sched, gc["weight"])

            # normalizing constants (may be modified)
            groups_cost /= len(group_schedules)
            profs_cost /= len(prof_schedules)
        return 0.6 * groups_cost + 0.4 * profs_cost + add_cost # parameters to be modified

    def evaluate_csp(self, state):

        slot_to_rooms, slot_to_groups, slot_to_teachers, teacher_events = self.constraint_obj._build_lookup_tables(state)
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
            fn   = getattr(c, hc["rule"])
            args = category_args[hc["category"]]
            violations += fn(*args, count=True)
        return violations # parameters to be modified
        

