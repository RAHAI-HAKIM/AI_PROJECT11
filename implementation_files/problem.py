
# This is the class that implements main problem method, specific data-driven problems will enhirit from it 
class Problem:
    pass


class Constraints:
    # includes the constraints functions, seperated for clean structure
    def __init__(self, problem):
        self.problem = problem
    
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
        pass # returnes a list of 2 lists having events, rooms 


    def generate_valid_state(self): 
        # does csp
        pass 
        # and it's depending methods

    def backtrack():
        # used by csp
        pass

    def generate_random_state(self):
        # random assignment, not respecting any constraints
        pass
    
    def enhance(state):
        # this method is used after generating a random state to resolve constraints using local search
        pass

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

    def evaluate_csp(self,state):
        # returns the number of hard constraints violated, used for local search CSP
        # we use the Min-conflicts heuristic
        num_voilated_constraints = 0
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
            num_voilated_constraints += constraint_function(state)


        for event_id, (roomid, slot) in state.items():
            event_data = self.events_by_id(event_id)
            if not event_data: continue

            prof_id = event_data["teacher_id"]
            target_id = event_data["target_id"] # may be a section

            # general constraits
            for gc in general_constraints: 
                constraint_function = getattr(self.constraint_obj, gc["rule"])
                num_voilated_constraints += constraint_function(event_data, roomid, slot)
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
                num_voilated_constraints += constraint_obj.constraint_function(sched)

        for group_id, sched in group_schedules.items():
            for grc in group_constraints:
                constraint_function = getattr(self.constraint_obj, gc["rule"])
                num_voilated_constraints += constraint_obj.constraint_function(sched)

        return num_voilated_constraints # parameters to be modified
        

