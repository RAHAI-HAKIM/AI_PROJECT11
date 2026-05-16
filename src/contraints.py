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


    # this constraint is NOT well-written + the functionality is implemented in soft constraints => removed for now


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
    
    def SEPARATE_LECTURE_PRACTICE(self, state, weight=1.0, count=True):
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
        return violations * weight

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



