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
        eval_func = objective if objective is not None else problem.evaluate

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


        return best_state_so_far, best_state_eval

    def Hill_Climbing(self, problem, objective=None, strategy="steepest"):
        """
        Iteratively moves to a better neighbor until no improvement is found.
        strategy:
            'steepest'    — picks the best neighbor overall.
            'first_choice'— picks the first improving neighbor.
            'stochastic'  — picks a random improving neighbor.
        """
        import random
        
        eval_func     = objective if objective else problem.evaluate
        
        current_state = dict(problem.state)
        current_eval  = eval_func(current_state)

        while True:
            event_id  = random.choice(list(current_state.keys()))

            neighbors = list(problem.generate_neighbors(current_state, event_id, size=20))
            
    
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

    def Random_Restart_Hill_Climbing(self, problem,objective=None, base_strategy="steepest", num_restarts=50):
        """
        Runs Hill_Climbing multiple times from different starting points to escape local optima.
        First restart starts from problem.state, subsequent ones use a density-guided random state
        that is biased toward slots that performed well in previous restarts.
        """
        eval_func = objective if objective else problem.evaluate
        global_best_state = None
        global_best_eval = float('inf')
        num_events = len(problem.events)
        num_slots = len(problem.slots)
        density_map = nump.full((num_events, num_slots), 1.0 / num_slots)
        for every in range(num_restarts):
            current_state = {}
            for idx, event_id in enumerate(problem.events_by_id.keys()):
                slot_idx = nump.random.choice(num_slots, p=density_map[idx])
                current_state[event_id] = problem.slots[slot_idx]
            result_state, _  = self.Hill_Climbing(Optimizer,problem, objective=objective,strategy=base_strategy)
            result_eval = eval_func(result_state)
            if result_eval < global_best_eval:
                global_best_state = result_state
                global_best_eval = result_eval
                for idx, event_id in enumerate(problem.events_by_id.keys()):
                    assigned_pos = result_state[event_id]
                    slot_idx = problem.slots.index(assigned_pos)
                    density_map[idx][slot_idx] += 0.1 
                    density_map[idx] /= density_map[idx].sum()
        return global_best_state, global_best_eval
        
    def Tabu_Search(self, problem, objective=None, restarts=5, iters=300, tabu_size=20):
        """
        Explores neighbors while maintaining a tabu list to avoid revisiting recent states.
        First restart starts from problem.state, subsequent ones use generate_random_state().
        tabu_size controls how many recent states are blacklisted at any time.
        """
        eval_func       = objective if objective else problem.evaluate
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
                event_id = random.choice(valid_events)
            
                neighbors = problem.generate_neighbors(state, event_id, size=20)
                    
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

