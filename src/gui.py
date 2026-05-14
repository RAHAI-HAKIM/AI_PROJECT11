import streamlit as st
import pandas as pd
from problem import EnsiaProblem
from optimizer import Optimizer
from dataclasses import dataclass
from copy import deepcopy


@dataclass
class Activity:
    id: int
    name: str
    type: str
    room: str
    teacher: str
    
    def __repr__(self):
        return (
            f"{self.name}\n"
            f"{self.type}\n"
            # f"{self.room}\n"
            # f"{self.teacher}\n"
        )
    
    def __hash__(self):
        return hash(self.id)

class Tables:
    type_names = {1: "Lecture", 2: "Tutorial", 3: "Lab"}
    
    def __init__(self, problem: EnsiaProblem, state: dict | None = None):
        self.problem = problem
        self.state = state or problem.state
        self.tables = self.create_tables()
    
    def create_tables(self):
        problem = self.problem
        tables = {group["name"]: [[None]*5 for _ in range(6)] for group in problem.groups}
        
        for eid, slot, in self.state.items():
            event = problem.events_by_id[eid]
            room = problem.rooms_by_id[slot[0]]
            teacher = problem.teachers_by_id[event["teacher_id"]]
            type_id = event["type_id"]
        
            activity = Activity(
                id=eid,
                name=event["course_name"],
                type=self.type_names[type_id],
                room=room["name"],
                teacher=teacher["name"]
            )
            
            day = (slot[1]-1) // 6
            timeslot = (slot[1]-1) % 6
            
            for gn in self.targeted_groups(event):
                tables[gn][timeslot][day] = deepcopy(activity)
        
        return tables
    
    def targeted_groups(self, event) -> list[str]:
        target_id = event["target_id"]
        if event["target_type_id"] == 1:
            return self.section_groups(target_id)
        else:
            return [self.problem.groups_by_id[target_id]["name"]]
    
    def section_groups(self, section_id):
        group_names = []
        for group in self.problem.groups:
            if group["section_id"] == section_id:
                group_names.append(group["name"])
        return group_names
    
    def __getitem__(self, key):
        return self.tables[key]

prb = EnsiaProblem("../dataset/data_s2.json", "global_search")
state = None
# opt = Optimizer()
# state, ev = opt.Tabu_Search(prb)
tab = Tables(prb, state)

timeslots = ["08:30 - 10:00", "10:10 - 11:40", "11:50 - 13:20", "13:30 - 15:00", "15:10 - 16:40", "16:50 - 18:20"]
week_days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"]
time_table = tab["Y2_G9"]
data = dict(zip(timeslots, time_table))
df = pd.DataFrame(data, index=week_days)
st.table(df, width="stretch")