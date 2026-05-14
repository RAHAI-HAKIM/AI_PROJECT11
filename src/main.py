import sys

from problem import *
from optimizer import *
from utils import *
import copy


goal = "opt"
prob = None 
obj_func = None

if goal == "opt":
    prob = EnsiaProblem("dataset/data_s2.json")
    obj_func = prob.evaluate
else:
    prob = EnsiaProblem("dataset/data_s2.json","local_search")
    obj_func = prob.evaluate_csp


# 1. Define the algorithms to test
# Format: "Name": (Function, kwargs)
algorithms = {
    "Hill Climbing": (Optimizer.Hill_Climbing, {"strategy": "steepest"}),
    "Simulated Annealing": (Optimizer.Simulated_Annealing, {
        "initial_temp": 1000, "cooling_rate": 0.95, "max_iterations": 1000, "strategy": "Exponential"
    }),
    "Random Restart HC": (Optimizer.Random_Restart_Hill_Climbing, {
        "base_strategy": "steepest", "num_restarts": 10
    }),
    "Tabu Search": (Optimizer.Tabu_Search, {
        "restarts": 5, "iters": 80, "tabu_size": 10
    })
}




initial_eval = obj_func(prob.state)
print(f"--- Benchmark Start (Initial Eval: {initial_eval}) ---")

results = {}

for name, (func, kwargs) in algorithms.items():
    # Crucial: Start each alg with a fresh clone of the problem
    # so they don't modify the global prob.state in place
    test_prob = copy.deepcopy(prob)

    # Execute the algorithm
    # Note: Using *args/**kwargs style if your Optimizer methods allow it
    next_state, _ = func(Optimizer, test_prob, objective=goal, **kwargs)

    final_eval = obj_func(next_state)
    improvement = initial_eval - final_eval # Assuming lower is better

    results[name] = final_eval

    print(f"[{name:20}] -> Before: {initial_eval} | After: {final_eval} | Change: {improvement:-}")

    inspect_state(next_state)

print("--- Benchmark Complete ---")



