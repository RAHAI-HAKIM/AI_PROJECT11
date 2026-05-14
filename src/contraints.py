from collections import defaultdict


class Constraints:
    def __init__(self, problem):
        self.problem = problem

    # ------------------------------------------------------------------ #
    #  Lookup table builder                                                #
    # ------------------------------------------------------------------ #

    def _build_lookup_tables(self, state):
        """
        Preprocess the schedule into resource-centric lookup tables for
        efficient constraint evaluation.

        Returns:
            (slot_to_rooms, slot_to_groups, slot_to_teachers, teacher_events)
        """
        slot_to_rooms    = defaultdict(list)
        slot_to_groups   = defaultdict(list)
        slot_to_teachers = defaultdict(list)
        teacher_events   = defaultdict(list)

        for event_id, (roomid, slot) in state.items():
            event      = self.problem.events_by_id[event_id]
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

    # ------------------------------------------------------------------ #
    #  Hard constraints                                                    #
    # ------------------------------------------------------------------ #

    # --- Double-booking ---

    def NO_ROOM_DOUBLE_BOOKING(self, slot_to_rooms, count=True):
        violations = 0
        for slot, rooms in slot_to_rooms.items():
            v = len(rooms) - len(set(rooms))
            if not count and v > 0:
                return False
            violations += v
        return violations if count else True

    def NO_GROUP_DOUBLE_BOOKING(self, slot_to_groups, count=True):
        violations = 0
        for slot, groups in slot_to_groups.items():
            v = len(groups) - len(set(groups))
            if not count and v > 0:
                return False
            violations += v
        return violations if count else True

    def NO_TEACHER_DOUBLE_BOOKING(self, slot_to_teachers, count=True):
        violations = 0
        for slot, teachers in slot_to_teachers.items():
            v = len(teachers) - len(set(teachers))
            if not count and v > 0:
                return False
            violations += v
        return violations if count else True

    # --- Room suitability ---

    def ROOM_CAPACITY_GEQ_HEADCOUNT(self, state, count=True):
        violations = 0
        for event_id, (roomid, slot) in state.items():
            event = self.problem.events_by_id[event_id]
            room  = self.problem.rooms_by_id[roomid]
            if room["capacity"] < event["headcount"]:
                if not count:
                    return False
                violations += 1
        return violations if count else True

    def MATCH_ROOM_TYPE(self, state, count=True):
        violations = 0
        for event_id, (roomid, slot) in state.items():
            event = self.problem.events_by_id[event_id]
            room  = self.problem.rooms_by_id[roomid]
            if room["room_type_id"] != event["required_room_type_id"]:
                if not count:
                    return False
                violations += 1
        return violations if count else True

    # --- Scheduling structure ---

    def SEPARATE_LECTURE_PRACTICE(self, state, count=True):
        """
        A lecture and a practice session for the same course and overlapping
        groups must NOT fall on the same day.
        """
        key_to_types = defaultdict(list)
        for event_id, (roomid, slot) in state.items():
            event  = self.problem.events_by_id[event_id]
            day    = slot // 6
            groups = (self.problem.section_to_group[event["target_id"]]
                      if event["type_id"] == 1 else [event["target_id"]])
            for gid in groups:
                key_to_types[(gid, event["course_name"], day)].append(
                    event["type_id"])

        violations = 0
        for (gid, course, day), types in key_to_types.items():
            if any(t == 1 for t in types) and any(t != 1 for t in types):
                if not count:
                    return False
                violations += 1
        return violations if count else True

    def CONSECUTIVE_SECTION_LECTURES(self, state, count=True):
        """
        If a section has two lectures for the same course they must be in
        consecutive slots on the same day.

        FIX: group by (section/target_id, course_name) not just course_name,
        so lectures for *different* sections of the same course are not
        incorrectly forced to be consecutive with each other.
        """
        # key: (target_id, course_name)  →  list of slots
        section_course_slots = defaultdict(list)
        for event_id, (roomid, slot) in state.items():
            event = self.problem.events_by_id[event_id]
            if event["type_id"] != 1:
                continue
            key = (event["target_id"], event["course_name"])
            section_course_slots[key].append(slot)

        violations = 0
        for (section_id, course), slots in section_course_slots.items():
            if len(slots) < 2:
                continue
            for i in range(len(slots)):
                for j in range(i + 1, len(slots)):
                    si, sj = slots[i], slots[j]
                    same_day    = (si // 6) == (sj // 6)
                    consecutive = abs(si - sj) == 1
                    if not (same_day and consecutive):
                        if not count:
                            return False
                        violations += 1
        return violations if count else True

    def MAX_CONSECUTIVE_STUDENT_SLOTS_3(self, state, count=True):
        """No student group may have more than 3 consecutive time-slots."""
        group_day_slots = defaultdict(lambda: defaultdict(set))
        for event_id, (roomid, slot) in state.items():
            event  = self.problem.events_by_id[event_id]
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
                    if not count:
                        return False
                    violations += 1
        return violations if count else True

    # ------------------------------------------------------------------ #
    #  Soft constraints                                                    #
    # ------------------------------------------------------------------ #

    # --- External (whole-state) ---

    def SIMILAR_ACTIVITIES(self, state, weight):
        """
        Lectures for the same course across different sections should be
        scheduled at the same time (consecutive slots, same day).
        """
        course_slots = defaultdict(list)
        for event_id, (roomid, slot) in state.items():
            event_data = self.problem.events_by_id[event_id]
            if event_data["type_id"] != 1:
                continue
            course_slots[event_data["course_name"]].append(slot)

        non_similar = 0
        for c, slots in course_slots.items():
            if len(slots) < 2:
                continue
            for i in range(len(slots)):
                for j in range(i + 1, len(slots)):
                    diff     = abs(slots[i] - slots[j])
                    same_day = (slots[i] // 6) == (slots[j] // 6)
                    if not (diff == 1 and same_day):
                        non_similar += 1
        return non_similar * weight

    def MINIMIZE_WASTED_SEATS(self, state, weight):
        wasted = 0
        for event_id, (roomid, slot) in state.items():
            event_data = self.problem.events_by_id[event_id]
            room_data  = self.problem.rooms_by_id[roomid]
            wasted += ((room_data["capacity"] - event_data["headcount"])
                       / room_data["capacity"])
        return wasted * weight

    # --- General (per-event) ---

    def MORNING_LECTURES(self, event, roomid, slot, weight):
        time = slot % 6
        if time <= 1:
            return 0
        penalty = {2: 1.0, 3: 1.5, 4: 2.0, 5: 2.5}.get(time, 0)
        return penalty * weight

    # --- Group / teacher (per-schedule) ---

    def MINIMIZE_GAPS(self, schedule, weight):
        gaps = 0
        days_active = {d: [] for d in range(5)}
        for room, slot in schedule:
            days_active[slot // 6].append((room, slot % 6))

        for day, classes in days_active.items():
            classes.sort(key=lambda x: x[1])
            for i in range(len(classes) - 1):
                time1 = classes[i][1]
                time2 = classes[i + 1][1]
                diff  = time2 - time1
                if diff <= 1:
                    continue
                if diff == 2 and (time2 == 2 or time2 == 5):
                    gaps += 1
                elif diff == 3 and time2 != 4:
                    gaps += 1
                else:
                    gaps += 1.5
        return gaps * weight

    def AVOID_THURSDAY_AFTERNOON(self, schedule, weight):
        thursday_afternoon = {27, 28, 29}
        cost = 0
        for room, slot in schedule:
            if slot in thursday_afternoon:
                cost += (slot - 26)   # 27→1, 28→2, 29→3
        return cost * weight

    def AVOID_LAST_SLOT(self, schedule, weight):
        count = sum(1 for room, slot in schedule if slot % 6 == 5)
        return count * weight

    def MINIMIZE_ROOM_CHANGES(self, schedule, weight):
        room_change_cost = 0
        days_active = {d: [] for d in range(5)}
        for room, slot in schedule:
            days_active[slot // 6].append((room, slot % 6))

        for day, classes in days_active.items():
            classes.sort(key=lambda x: x[1])
            for i in range(len(classes) - 1):
                room1, time1 = classes[i]
                room2, time2 = classes[i + 1]
                if time2 - time1 != 1:
                    continue
                if room1 == room2:
                    continue
                r1 = self.problem.rooms_by_id[room1]
                r2 = self.problem.rooms_by_id[room2]
                same_type  = r1["room_type_id"] == r2["room_type_id"]
                same_floor = r1["floor"]        == r2["floor"]
                if same_type and same_floor:
                    room_change_cost += 0.5
                elif not same_type and not same_floor:
                    room_change_cost += 2.0
                else:
                    room_change_cost += 1.0

        return room_change_cost * weight

    def MINIMIZE_TEACHER_DAYS(self, schedule, weight):
        days_active = {d: [] for d in range(5)}
        for room, slot in schedule:
            days_active[slot // 6].append((room, slot % 6))
        num_days     = sum(1 for d in days_active.values() if d)
        num_sessions = sum(len(d) for d in days_active.values())
        if num_days < num_sessions // 3:
            return 0
        return weight * (num_days + 1 - (num_sessions // 3)) #penalty if more than 3 sessions are spread across too many days