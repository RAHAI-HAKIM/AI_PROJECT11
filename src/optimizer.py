from math import exp
import numpy as nump
import random
from collections import deque

# defines functions and returns optimized states
class Optimizer:
    def Simulated_Annealing(self, problem, objective, initial_temp, cooling_rate, max_iterations,strategy="Linear"):
        """
        gets the problem's current state and returns an optimized one using SA
        """
        eval_func = problem.evaluate if objective == "opt" else problem.evaluate_csp
        get_next = problem.move_operator if objective == "opt" else problem.move_operator_csp

        current_state      = dict(problem.state)
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

            next_state = get_next(current_state)
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


        return best_state_so_far, best_state_eval

    def Hill_Climbing(self, problem, objective="opt", strategy="steepest"):
        """
        Iteratively moves to a better neighbor until no improvement is found.
        strategy:
            'steepest'    — picks the best neighbor overall.
            'first_choice'— picks the first improving neighbor.
            'stochastic'  — picks a random improving neighbor.
        """
        import random
        
        eval_func = problem.evaluate if objective == "opt" else problem.evaluate_csp
        get_neighbors = problem.generate_neighbors if objective == "opt" else problem.generate_neighbors_csp

        current_state = dict(problem.state)
        current_eval  = eval_func(current_state)

        while True:
            neighbors = list(get_neighbors(current_state, size=20))

    
            if not neighbors:
                break

            next_state = None

            if strategy == "steepest":
                best_neighbor = min(neighbors, key=lambda n: eval_func(n))
                if eval_func(best_neighbor) < current_eval:
                    next_state = best_neighbor

            elif strategy == "first_choice":
                for n in neighbors:
                    if eval_func(n) < current_eval:
                        next_state = n
                        break

            elif strategy == "stochastic":
                improving = [n for n in neighbors if eval_func(n) < current_eval]
                if improving:
                    next_state = random.choice(improving)

            if next_state is not None:
                current_state = dict(next_state)
                current_eval  = eval_func(current_state)
            else:
                break

        return current_state, current_eval

    def Random_Restart_Hill_Climbing(self, problem,objective="opt", base_strategy="steepest", num_restarts=50):
        """
        Runs Hill_Climbing multiple times from different starting points to escape local optima.
        First restart starts from problem.state, subsequent ones use a density-guided random state
        that is biased toward slots that performed well in previous restarts.
        """
        global_best_state = None
        global_best_eval = float('inf')
        for every in range(num_restarts):
            problem.state = problem.generate_random_state()
            result_state, result_eval = self.Hill_Climbing(Optimizer,problem, objective=objective,strategy=base_strategy)

            if result_eval < global_best_eval:
                global_best_state = result_state
                global_best_eval = result_eval
        return global_best_state, global_best_eval

    def Tabu_Search(self, problem, objective=None, restarts=5, iters=300, tabu_size=20):
        """
        Explores neighbors while maintaining a tabu list to avoid revisiting recent states.
        First restart starts from problem.state, subsequent ones use generate_random_state().
        tabu_size controls how many recent states are blacklisted at any time.
        """
        eval_func = problem.evaluate if objective == "opt" else problem.evaluate_csp
        get_neighbors = problem.generate_neighbors if objective == "opt" else problem.generate_neighbors_csp

        global_best     = None
        global_best_val = float("inf")
    
        for restart in range(restarts):
            state    = dict(problem.state) if restart == 0 else dict(problem.generate_random_state())
            best     = dict(state)
            best_val = eval_func(state)

            tabu_queue = deque()
            tabu_set   = set()

            for _ in range(iters):
                best_candidate     = None
                best_candidate_val = float("inf")

                valid_events = list(state.keys())
                # removed event_id getting ... risk of logic for algorithm
                neighbors = get_neighbors(state,size=20)
                    
                for st in neighbors:
                    t = tuple(sorted(st.items()))
                    if t not in tabu_set:
                        val = eval_func(st)
                        if val < best_candidate_val:
                            best_candidate     = st
                            best_candidate_val = val
    
                if best_candidate is None:
                    break
    
                state = dict(best_candidate) 
                t     = tuple(sorted(state.items()))
                tabu_queue.append(t)
                tabu_set.add(t)
    
                if len(tabu_queue) > tabu_size:
                    tabu_set.discard(tabu_queue.popleft())
    
                if best_candidate_val < best_val:
                    best     = dict(state) 
                    best_val = best_candidate_val

            if best_val < global_best_val:
                global_best     = dict(best)
                global_best_val = best_val

        return global_best, global_best_val

