import streamlit as st
import pandas as pd
from problem import EnsiaProblem
from optimizer import Optimizer
from tables import Tables, Activity


css = f"""
<style>
table {{ table-layout: fixed; width: 100% !important; }}
th, td {{ width: {100 / 7}% !important; white-space: normal !important; }}
</style>
"""
st.markdown(css, unsafe_allow_html=True)
st.title("AI Project 11")

st.header("Finding a valid state with csp")


@st.cache_data
def load_tables(method) -> Tables:
    prb = EnsiaProblem("../dataset/data_s2.json", method)
    # opt = Optimizer()
    # state, ev = opt.Hill_Climbing(prb, strategy="stochastic")
    state = prb.state
    tables = Tables(prb, state)
    return tables


def show_table(tables, group_name):
    timeslots = [
        "08:30 - 10:00",
        "10:10 - 11:40",
        "11:50 - 13:20",
        "13:30 - 15:00",
        "15:10 - 16:40",
        "16:50 - 18:20",
    ]
    week_days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"]
    time_table = tables[group_name]
    data = dict(zip(timeslots, time_table))
    df = pd.DataFrame(data, index=week_days)
    st.table(df)


tables = load_tables("global_search").tables
group_names = list(tables.keys())
year = st.selectbox(
    "Select a year:", [1, 2, 3, 4, 5], format_func=lambda x: f"Year {x}"
)
group = st.selectbox(
    "Select a group:", [i for i in range(1, 13)], format_func=lambda x: f"Group {x}"
)
group_name = f"Y{year}_G{group}"
show_table(tables, group_name)
