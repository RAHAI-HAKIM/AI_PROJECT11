from problem import *
from optimizer import *
import copy
import sys

prob = EnsiaProblem("dataset/data_s2.json",cspmethod="local_search")

def print_state(obj):
    print("printing the state ....")
    for key,value in obj.items():
        print(f"{key} => {value}")


# print_state(prob.state)

cpy = copy.deepcopy(prob.state)

# next_state = prob.swapper_napper(prob.state,iteration=100)
# next_state = prob.shifter_nifter(prob.state,iteration=10,shift_rate=1,direction="right",amount=2)
# next_state = prob.move_to_another_slot(cpy,iteration=10)

# next_generation = prob.pipeline_generate_neighbors(cpy,size=10)

# next_state, _ =  Optimizer.Hill_Climbing(None, prob, objective=prob.evaluate_csp, strategy="steepest")
# next_state, _ = Optimizer.Simulated_Annealing(Optimizer,prob, objective=prob.evaluate_csp,initial_temp=100,cooling_rate=0.5,max_iterations=100,strategy="Linear")
#tst the rr.hc of youcef
opt = Optimizer()
next_state, _ = opt.Random_Restart_Hill_Climbing(prob, objective=prob.evaluate_csp, base_strategy="steepest", num_restarts=20)
#here the sa of ayoub 
next_state2, _ = opt.Simulated_Annealing(prob, objective=prob.evaluate_csp, initial_temp=100, cooling_rate=0.5, max_iterations=1000)
print(f"Simulated Annealing: before={prob.evaluate_csp(prob.state)} after={prob.evaluate_csp(next_state2)}")
# next_state, _ = Optimizer.Tabu_Search(Optimizer, prob, objective=prob.evaluate_csp, restarts=3, iters=100, tabu_size=20)

print(f"eval before {prob.evaluate_csp(prob.state)} eval after is {prob.evaluate_csp(next_state)}")
# print(f"eval before {prob.evaluate(prob.state)} eval after is {prob.evaluate(next_state)}")

sys.exit(0)

import copy

# 1. Define the algorithms to test
# Format: "Name": (Function, kwargs)
algorithms = {
    "Hill Climbing": (Optimizer.Hill_Climbing, {"strategy": "steepest"}),
    "Simulated Annealing": (Optimizer.Simulated_Annealing, {
        "initial_temp": 100, "cooling_rate": 0.9, "max_iterations": 100, "strategy": "Exponential"
    }),
    "Random Restart HC": (Optimizer.Random_Restart_Hill_Climbing, {
        "base_strategy": "steepest", "num_restarts": 10
    }),
    "Tabu Search": (Optimizer.Tabu_Search, {
        "restarts": 3, "iters": 10, "tabu_size": 20
    })
}

initial_eval = prob.evaluate(prob.state)
print(f"--- Benchmark Start (Initial Eval: {initial_eval}) ---")

results = {}

for name, (func, kwargs) in algorithms.items():
    # Crucial: Start each alg with a fresh clone of the problem
    # so they don't modify the global prob.state in place
    test_prob = copy.deepcopy(prob)
    
    # Execute the algorithm
    # Note: Using *args/**kwargs style if your Optimizer methods allow it
    next_state, _ = func(Optimizer, test_prob, objective=test_prob.evaluate, **kwargs)
    
    final_eval = test_prob.evaluate(next_state)
    improvement = initial_eval - final_eval # Assuming lower is better
    
    results[name] = final_eval
    
    print(f"[{name:20}] -> Before: {initial_eval} | After: {final_eval} | Change: {improvement:+}")

print("--- Benchmark Complete ---")
