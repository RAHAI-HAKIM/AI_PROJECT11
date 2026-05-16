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


def show_table(time_table):
    timeslots = [
        "08:30 - 10:00",
        "10:10 - 11:40",
        "11:50 - 13:20",
        "13:30 - 15:00",
        "15:10 - 16:40",
        "16:50 - 18:20",
    ]
    week_days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"]
    data = dict(zip(timeslots, time_table))
    df = pd.DataFrame(data, index=week_days)
    st.table(df)


st.title("AI Project 11")

st.sidebar.header("Start by Generating a Valid CSP Solution")
csp_button = st.sidebar.button("Solve CSP", type="primary")

if csp_button:
    with st.sidebar.spinner("Generating a valid CSP solution..."):
        st.session_state.problem = EnsiaProblem("dataset/data_s2.json")
        st.session_state.csp_tables = Tables(st.session_state.problem)
        st.session_state.optimizer = Optimizer()
elif "problem" not in st.session_state:
    st.stop()

problem = st.session_state.problem
csp_tables = st.session_state.csp_tables
optimizer = st.session_state.optimizer

if "groups" not in st.session_state:
    groups_in_year = {}
    for group in csp_tables.tables:
        year, group = group.split("_")
        if year not in groups_in_year:
            groups_in_year[year] = []
        groups_in_year[year].append(group)
    st.session_state.groups = groups_in_year
else:
    groups_in_year = st.session_state.groups

year = st.selectbox("Select Year", list(groups_in_year.keys()))
group = st.selectbox("Select Group", groups_in_year[year])
st.header("Solution using Global Search CSP")
show_table(csp_tables[f"{year}_{group}"])

st.sidebar.divider()
st.sidebar.header("Now optimize the solution with Local Search")
local_search_method = st.sidebar.selectbox(
    "Select Local Search Method",
    [
        "Hill Climbing Steepest",
        "Hill Climbing First Choice",
        "Hill Climbing Stochastic",
        "Simulated Annealing Exponential",
        "Simulated Annealing Linear",
        "Tabu",
        "All",
    ],
)
local_search_iterations = st.sidebar.number_input(
    "Number of Iterations", min_value=1, max_value=1000, value=100
)
local_search_restarts = st.sidebar.select_slider("Number of Restarts", range(1, 11))
local_search_button = st.sidebar.button(
    "Compare" if local_search_method == "All" else "Optimize Solution"
)

if local_search_button:
    with st.sidebar.spinner("Optimizing solution..."):
        if local_search_method == "All":
            optimizer.compare(
                problem=problem,
                iterations=local_search_iterations,
                restarts=local_search_restarts,
            )
            st.session_state.mode = "all"
        else:
            st.session_state.local_search_data, st.session_state.local_search_state = optimizer.random_restart(
                problem=problem,
                search=local_search_method,
                iterations=local_search_iterations,
                restarts=local_search_restarts,
            )
            st.session_state.local_search_tables = Tables(problem, st.session_state.local_search_state)
            st.session_state.mode = "single"
            st.rerun()

if "mode" not in st.session_state:
    st.stop()

if st.session_state.mode =="single":
    st.header(f"Optimized Solution Using {local_search_method}")
    show_table(st.session_state.local_search_tables[f"{year}_{group}"])
    
    st.header(f"Iterations vs Cost Graph for {local_search_method}")
    st.line_chart(st.session_state.local_search_data)