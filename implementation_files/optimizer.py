from math import exp
import random
from collections import deque

# defines functions and returns optimized states
class Optimizer:
    def Simulated_Annealing(self, problem,objective, initial_temp, cooling_rate, max_iterations,strategy="Linear"):
        """
        gets the problem's current state and returns an optimized one using SA
        """
        eval_func = objective if objective is not None else problem.evaluate

        current_state = problem.generate_valid_state()
        current_state_eval = eval_func(current_state)

        best_state_so_far = current_state
        best_state_eval = current_state_eval

        T = initial_temp

        for t in range(max_iterations):
            # default behavior is Linear to avoid infinit loop
            if strategy == "Exponential":
                T *= cooling_rate
            else:
                T -= cooling_rate
            
            # in exp , 0 may never be reachd
            if T <= 1e-10:
                break

            next_state = problem.move_operator(current_state)
            next_state_eval = eval_func(next_state)

            Delta_E = next_state_eval - current_state_eval

            # we flip the logic here since we want to minimize the evaluation function
            if Delta_E < 0:
                current_state = next_state
                current_state_eval = next_state_eval
            else:
                proba = exp(-Delta_E/T)

                if random.random() < proba:
                    current_state = next_state
                    current_state_eval = next_state_eval

            if current_state_eval < best_state_eval:
                best_state_so_far = current_state
                best_state_eval = current_state_eval

        return best_state_so_far

    def Hill_Climbing(self, problem, strategy="steepest"):
        # gets the problem's current state and returns an optimized one using the choosen HC variant
        pass

    def Random_Restart_Hill_Climbing(self, problem, base_strategy="steepest", num_restarts=50):
        # calls the choosen HC variant to optimize -num_restart- randomely choosen valid states and selects the best
        pass

    def tabu_random_restarts(problem, restarts=5, iters=300, tabu_size=20):
    
        global_best = None
        global_best_val = float("inf")

        for _ in range(restarts):
            state = problem.random_state()
            best = state[:]
            best_val = problem.evaluate(state)

            tabu_queue = deque()
            tabu_set = set()

            for _ in range(iters):
                best_candidate = None
                best_candidate_val = float("inf")

                neighbors = problem.neighbors(state)

                for st in neighbors:
                    t = tuple(st)

                    if t not in tabu_set:
                        val = problem.evaluate(st)

                        if val < best_candidate_val:
                            best_candidate = st
                            best_candidate_val = val

                if best_candidate is None:
                    break

                state = best_candidate[:]
                t = tuple(state)

                tabu_queue.append(t)
                tabu_set.add(t)

                if len(tabu_queue) > tabu_size:
                    old = tabu_queue.popleft()
                    tabu_set.remove(old)

                if best_candidate_val < best_val:
                    best = state[:]
                    best_val = best_candidate_val


            if best_val < global_best_val:
                global_best = best[:]
                global_best_val = best_val

        return global_best


