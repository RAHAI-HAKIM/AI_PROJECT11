from problem import *
from optimizer import *
import copy
import sys

prob = EnsiaProblem("dataset/data_s2.json",cspmethod="local_search")

def print_state(obj):
    print("printing the state ....")
    for key,value in obj.items():
        print(f"{key} => {value}")

# Crucial: Start each alg with a fresh clone of the problem
# so they don't modify the global prob.state in place
test_prob = copy.deepcopy(prob)

# Execute the algorithm
# Note: Using *args/**kwargs style if your Optimizer methods allow it
next_state, _ = func(Optimizer, test_prob, objective=test_prob.evaluate, **kwargs)



