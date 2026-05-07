from problem import *
from optimizer import *


# NOTE: check bugs.md to bugs to be fixed.


test_drive = EnsiaProblem("dataset/data_s2.json")

print(f"at beginning evaluation for now is {test_drive.evaluate(test_drive.state)}")

# Optimizer.Simulated_Annealing(Optimizer,test_drive, test_drive.evaluate, 2, 0.9, 20,"Linear")

# Works fine , no Optimization is made
# Optimizer.Hill_Climbing(None, test_drive, objective=test_drive.evaluate, strategy="steepest")

# Optimizer.Random_Restart_Hill_Climbing(Optimizer, test_drive,test_drive.evaluate, "steepest", num_restarts=50)

# Optimizer.Tabu_Search(Optimizer, test_drive, objective=test_drive.evaluate, restarts=3, iters=10, tabu_size=20)

print(f"Done , evaluation for now is {test_drive.evaluate(test_drive.state)}")
