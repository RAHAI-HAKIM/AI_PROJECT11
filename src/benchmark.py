import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from problem import *
from optimizer import *
import copy

prob = EnsiaProblem("dataset/data_s2.json")
state = prob.state
c = prob.constraint_obj
slot_to_rooms, slot_to_groups, slot_to_teachers, teacher_events = \
    c._build_lookup_tables(state)

category_args = {
    "slot_to_rooms":    (slot_to_rooms,),
    "slot_to_groups":   (slot_to_groups,),
    "slot_to_teachers": (slot_to_teachers,),
    "state_based":      (state,),
    "teacher_based":    (teacher_events,),
}

print("=== Hard constraint violation breakdown ===")
for hc in prob.hard_constraints_list:
    if isinstance(hc, str): continue
    fn   = getattr(c, hc["rule"])
    args = category_args[hc["category"]]
    v    = fn(*args, count=True)
    if v > 0:
        print(f"  {hc['rule']:45s}  violations: {v}")
print("===========================================")

opt = Optimizer()

algorithms = {
    "Hill Climbing":      (opt.Hill_Climbing,                {"strategy": "steepest"}, "soft"),
    "Simulated Annealing":(opt.Simulated_Annealing,          {"initial_temp": 100, "cooling_rate": 0.9, "max_iterations": 100, "strategy": "Exponential"}, "soft"),
    "Random Restart HC":  (opt.Random_Restart_Hill_Climbing, {"base_strategy": "steepest", "num_restarts": 10}, "soft"),
    "Tabu Search":        (opt.Tabu_Search,                  {"restarts": 3, "iters": 10, "tabu_size": 20}, "soft"),
}

initial_eval = prob.evaluate(prob.state)
initial_hard = prob.evaluate_csp(prob.state)
print(f"--- Benchmark Start (Initial Eval: {initial_eval:.3f}, Initial Hard: {initial_hard}) ---\n")

for name, (func, kwargs, objective_type) in algorithms.items():
    test_prob = copy.deepcopy(prob)
    objective = test_prob.evaluate if objective_type == "soft" else test_prob.evaluate_csp
    next_state, _ = func(test_prob, objective=objective, **kwargs)
    final_eval = test_prob.evaluate(next_state)
    hard = test_prob.evaluate_csp(next_state)
    improvement = initial_eval - final_eval
    status = "VALID" if hard == 0 else "INVALID"
    print(f"[{name:20}] Before: {initial_eval:.3f} | After: {final_eval:.3f} | Change: {improvement:+.3f} | Hard: {hard} | {status}")

print("\n--- Benchmark Complete ---")