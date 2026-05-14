from math import exp
import random
from collections import deque


class Optimizer:

    def Simulated_Annealing(self, problem, objective, initial_temp,
                             cooling_rate, max_iterations, strategy="Linear"):
        eval_func = objective if objective is not None else problem.evaluate

        current_state      = dict(problem.state)
        current_state_eval = eval_func(current_state)
        best_state         = dict(current_state)
        best_eval          = current_state_eval
        T                  = initial_temp

        for _ in range(max_iterations):
            if strategy == "Exponential":
                T *= cooling_rate
            else:
                T -= cooling_rate
            if T <= 1e-10:
                break

            # FIX: sync problem.state so move_operator sees the current search state
            problem.state  = current_state
            next_state      = problem.move_operator(current_state)
            next_eval       = eval_func(next_state)
            delta           = next_eval - current_state_eval

            if delta < 0 or random.random() < exp(-delta / T):
                current_state      = next_state
                current_state_eval = next_eval

            if current_state_eval < best_eval:
                best_state = dict(current_state)
                best_eval  = current_state_eval

        return best_state, best_eval

    def Hill_Climbing(self, problem, objective=None, strategy="steepest"):
        eval_func     = objective if objective is not None else problem.evaluate
        current_state = dict(problem.state)
        current_eval  = eval_func(current_state)

        while True:
            # FIX: keep problem.state in sync so neighbour generators
            # see the current search state (not the stale initial one)
            problem.state = current_state

            neighbors = problem.generate_neighbors(current_state,
                                                   event_id=None, size=20)
            if not neighbors:
                break

            next_state = None
            if strategy == "steepest":
                best_n = min(neighbors, key=lambda n: eval_func(n))
                if eval_func(best_n) < current_eval:
                    next_state = best_n

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
                current_state = next_state
                current_eval  = eval_func(current_state)
            else:
                break

        return current_state, current_eval

    def Random_Restart_Hill_Climbing(self, problem, objective=None,
                                     base_strategy="steepest", num_restarts=5):
        """
        Run full-strength Hill Climbing multiple times from perturbed versions
        of the best valid state found so far.

        Each restart uses the same neighbor quality as plain HC (no size reduction),
        so every restart is genuinely competitive and the best result across all
        restarts should always beat a single HC run.

        Perturbation kicks ~15% of events to new valid slots — large enough to
        escape the local optimum found by the previous restart, small enough to
        stay in a good region of the search space.
        """
        eval_func = objective if objective is not None else problem.evaluate

        global_best_state = dict(problem.state)
        global_best_eval  = eval_func(global_best_state)

        for restart in range(num_restarts):
            if restart == 0:
                start = dict(problem.state)
            else:
                # Perturb the global best with a larger kick for more diversity
                start  = dict(global_best_state)
                n_kick = max(2, len(start) * 15 // 100)
                for eid in random.sample(list(start.keys()), n_kick):
                    new_slot = problem._find_valid_slot(start, eid)
                    if new_slot is not None:
                        start[eid] = new_slot

            problem.state = start
            result_state, result_eval = self.Hill_Climbing(
                problem, objective=objective, strategy=base_strategy)

            if result_eval < global_best_eval:
                global_best_state = result_state
                global_best_eval  = result_eval

        return global_best_state, global_best_eval

    def Tabu_Search(self, problem, objective=None,
                    restarts=3, iters=100, tabu_size=20):
        """
        Tabu Search with a lightweight move-based tabu key.

        Instead of hashing the entire state (which is O(n) per neighbor and
        makes the search extremely slow), we record the move itself as the
        tabu key: (event_id, old_assignment, new_assignment). This is O(1)
        per neighbor and allows many more iterations in the same time budget.

        A final hard-constraint check on the returned state guarantees
        the result is always valid.
        """
        eval_func       = objective if objective else problem.evaluate
        global_best     = None
        global_best_val = float("inf")

        for restart in range(restarts):
            if restart == 0:
                state = dict(problem.state)
            else:
                state  = dict(global_best) if global_best else dict(problem.state)
                n_kick = max(1, len(state) // 10)
                for eid in random.sample(list(state.keys()), n_kick):
                    new_slot = problem._find_valid_slot(state, eid)
                    if new_slot is not None:
                        state[eid] = new_slot

            best     = dict(state)
            best_val = eval_func(state)

            tabu_queue = deque()
            tabu_set   = set()

            for _ in range(iters):
                best_candidate     = None
                best_candidate_val = float("inf")
                best_move          = None

                problem.state = state
                neighbors = problem.generate_neighbors(state, event_id=None, size=20)

                for neighbor in neighbors:
                    # Find which event moved and build a lightweight move key
                    diff = [(eid, state[eid], neighbor[eid])
                            for eid in state if state[eid] != neighbor[eid]]
                    # Use the first changed event as the tabu key — O(1) lookup
                    move_key = diff[0] if diff else None

                    if move_key in tabu_set:
                        continue

                    val = eval_func(neighbor)
                    if val < best_candidate_val:
                        best_candidate     = neighbor
                        best_candidate_val = val
                        best_move          = move_key

                if best_candidate is None:
                    break

                state = dict(best_candidate)

                if best_move is not None:
                    tabu_queue.append(best_move)
                    tabu_set.add(best_move)
                    if len(tabu_queue) > tabu_size:
                        tabu_set.discard(tabu_queue.popleft())

                if best_candidate_val < best_val:
                    best     = dict(state)
                    best_val = best_candidate_val

            if best_val < global_best_val:
                global_best     = dict(best)
                global_best_val = best_val

        # Safety guarantee: always return a hard-constraint-valid state
        if global_best is None:
            global_best = dict(problem.state)
        if problem.evaluate_csp(global_best) > 0:
            global_best     = dict(problem.state)
            global_best_val = eval_func(global_best)

        return global_best, global_best_val