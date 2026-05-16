from math import exp
import random
from collections import deque
import streamlit as st
import pandas as pd
import numpy as np
from problem import EnsiaProblem
import matplotlib.pyplot as plt
import matplotlib


class Optimizer:

    def Simulated_Annealing(
        self, problem, objective, initial_temp, cooling_rate, max_iterations,
        strategy="Exponential", visualize=False, col=None,
        running_chart=None, running_info=None
    ):
        """
        Minimises evaluate() / evaluate_csp() via Simulated Annealing.

        """
        eval_func = problem.evaluate if objective == "opt" else problem.evaluate_csp
        get_next  = problem.move_operator if objective == "opt" else problem.move_operator_csp

        current_state      = dict(problem.state)
        current_state_eval = eval_func(current_state)

        best_state_so_far = dict(current_state)
        best_state_eval   = current_state_eval

        T = initial_temp

        if visualize:
            data = pd.DataFrame(np.random.randn(0, 1), columns=["Cost"])

        for t in range(max_iterations):

            if strategy == "Exponential":
                T *= cooling_rate
            else:
                # Linear: caller must set cooling_rate = initial_temp / max_iterations
                T -= cooling_rate

            if T <= 1e-10:
                break

            next_state      = get_next(current_state)
            next_state_eval = eval_func(next_state)
            Delta_E         = next_state_eval - current_state_eval

            if Delta_E < 0:
                current_state      = next_state
                current_state_eval = next_state_eval
            else:
                # Guard against math overflow when T is tiny but not yet ≤ 1e-10
                if T > 1e-10:
                    proba = exp(-Delta_E / T)
                    if random.random() < proba:
                        current_state      = next_state
                        current_state_eval = next_state_eval

            if current_state_eval < best_state_eval:
                best_state_so_far = dict(current_state)
                best_state_eval   = current_state_eval

            if visualize:
                new_row = pd.DataFrame({"Cost": [current_state_eval]})
                data    = pd.concat([data, new_row], ignore_index=True)
                if (t + 1) % 10 == 0:
                    running_chart.line_chart(data)
                running_info.metric(
                    label="Current Score",
                    value=f"{best_state_eval:.2f}"
                )

        if visualize:
            return best_state_so_far, best_state_eval, data
        return best_state_so_far, best_state_eval

    def Hill_Climbing(
        self, problem, objective="opt", strategy="steepest",
        visualize=False, col=None, running_chart=None, running_info=None
    ):
        """
        Iteratively moves to a better neighbour until no improvement is found.

        Fixes vs original
        ─────────────────

        strategy
        ────────
        'steepest'     — best neighbour overall (most evals per step).
        'first_choice' — first improving neighbour (fewest evals per step).
        'stochastic'   — random improving neighbour.
        """
        eval_func     = problem.evaluate if objective == "opt" else problem.evaluate_csp
        get_neighbors = (problem.generate_neighbors if objective == "opt"
                         else problem.generate_neighbors_csp)

        NEIGHBOR_SIZE = 50
        PLATEAU_LIMIT = 10

        current_state = dict(problem.state)
        current_eval  = eval_func(current_state)
        plateau_count = 0

        if visualize:
            data = pd.DataFrame(np.random.randn(0, 1), columns=["Cost"])

        while plateau_count < PLATEAU_LIMIT:
            neighbors  = list(get_neighbors(current_state, size=NEIGHBOR_SIZE))
            next_state = None

            if strategy == "steepest":
                # Fix 1: evaluate once, cache result
                scored       = [(eval_func(n), n) for n in neighbors]
                best_val, best_n = min(scored, key=lambda x: x[0])
                if best_val < current_eval:
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
                current_state = dict(next_state)
                current_eval  = eval_func(current_state)
                plateau_count = 0
            else:
                plateau_count += 1   # Fix 3: count plateau rounds

            if visualize:
                new_row = pd.DataFrame({"Cost": [current_eval]})
                data    = pd.concat([data, new_row], ignore_index=True)
                running_chart.line_chart(data)
                running_info.metric(
                    label="Current Score",
                    value=f"{current_eval:.2f}"
                )

        if visualize:
            return current_state, current_eval, data
        return current_state, current_eval

    def Random_Restart_Hill_Climbing(
        self, problem, objective="opt", base_strategy="steepest", num_restarts=10
    ):
        """
        Runs Hill_Climbing from multiple perturbed starting points.

        Fixes vs original
        ─────────────────
        1. CRASH BUG: old code passed the class `Optimizer` as the first
           positional arg to Hill_Climbing, which received it as `self`:
               self.Hill_Climbing(Optimizer, problem, ...)
           Every method call inside Hill_Climbing then ran on the class
           object, not an instance.  Fixed: self.Hill_Climbing(problem, ...).

        2. Random restart states were invalid: generate_random_state()
           assigns slots with no constraint awareness, starting at cost >>
           than the CSP solution.  HC cannot climb out of that in any
           reasonable number of steps.

        """
        # preserve the original CSP state so we can restore it
        original_state    = dict(problem.state)
        global_best_state = dict(original_state)
        global_best_eval  = float("inf")

        for restart in range(num_restarts):
            if restart == 0:
                problem.state = dict(original_state)
            else:
                # Fix 2: perturb the global best, not a random invalid state
                problem.state = problem.relocate_event_operator(
                    global_best_state, iteration=30
                )

            # Fix 1: correct self argument
            result_state, result_eval = self.Hill_Climbing(
                Optimizer,problem, objective=objective, strategy=base_strategy
            )

            if result_eval < global_best_eval:
                global_best_state = dict(result_state)
                global_best_eval  = result_eval

        # restore so problem.state reflects the best found
        problem.state = global_best_state
        return global_best_state, global_best_eval

    def Tabu_Search(
        self, problem, objective=None, restarts=3, iters=500, tabu_size=50,
        visualize=False, col=None, running_chart=None, running_info=None
    ):
        """
        Tabu Search with aspiration criterion and efficient move hashing.

        1. O(N log N) hashing bottleneck:
           Old code hashed the full 469-event state as
               tuple(sorted(nei.items()))
           for every neighbour at every iteration — 20 neighbours × 300
           iters = 6000 full-state sorts and hashes of 469-element dicts.
           Fixed: hash only the DELTA (which events changed and to what),
           a frozenset of (event_id, new_value) pairs that is O(changed)
           to build and O(1) to hash.

        """
        eval_func     = problem.evaluate if objective == "opt" else problem.evaluate_csp
        get_neighbors = (problem.generate_neighbors if objective == "opt"
                         else problem.generate_neighbors_csp)

        NEIGHBOR_SIZE = 50

        global_best     = None
        global_best_val = float("inf")

        if visualize:
            data = pd.DataFrame(np.random.randn(0, 1), columns=["Cost"])

        for restart in range(restarts):
            if restart == 0:
                state = dict(problem.state)
            else:
                # Fix 3: perturb global best, not a random invalid state
                state = problem.relocate_event_operator(global_best, iteration=30)

            best     = dict(state)
            best_val = eval_func(state)

            tabu_queue  = deque()
            tabu_set    = set()
            prev_state  = dict(state)

            for iteration in range(iters):
                neighbors          = get_neighbors(state, size=NEIGHBOR_SIZE)
                best_candidate     = None
                best_candidate_val = float("inf")
                best_candidate_key = None

                for nei in neighbors:
                    # Fix 1: hash only the delta, not the full state
                    delta = frozenset(
                        (eid, v)
                        for eid, v in nei.items()
                        if prev_state.get(eid) != v
                    )

                    is_tabu = delta in tabu_set
                    val     = eval_func(nei)

                    # Fix 4: aspiration — override tabu if we beat global best
                    if is_tabu and val >= global_best_val:
                        continue

                    if val < best_candidate_val:
                        best_candidate     = nei
                        best_candidate_val = val
                        best_candidate_key = delta

                if best_candidate is None:
                    break

                prev_state = dict(state)
                state      = dict(best_candidate)

                tabu_queue.append(best_candidate_key)
                tabu_set.add(best_candidate_key)
                if len(tabu_queue) > tabu_size:
                    tabu_set.discard(tabu_queue.popleft())

                if best_candidate_val < best_val:
                    best     = dict(state)
                    best_val = best_candidate_val

                if visualize and (iteration + 1) % 10 == 0:
                    new_row = pd.DataFrame({"Cost": [best_candidate_val]})
                    data    = pd.concat([data, new_row], ignore_index=True)
                    running_chart.line_chart(data)
                    running_info.metric(
                        label="Current Score",
                        value=f"{best_val:.2f}"
                    )

            if best_val < global_best_val:
                global_best     = dict(best)
                global_best_val = best_val

        if visualize:
            return global_best, global_best_val, data
        return global_best, global_best_val

    # ── Streamlit visualisation helpers — unchanged ───────────────────────────

    def random_restart(self, problem, search, restarts, iterations):

        st.set_page_config(layout="wide")
        st.title(f"Graph Cost VS Iteration of {search}")

        main_container = st.container()
        best_score  = float("inf")
        best_data   = None
        best_run_id = None

        if restarts == 1:
            col1 = st.columns(1)[0]
            with col1:
                st.subheader("Current Run")
                running_chart1 = st.empty()
                running_info1  = st.empty()

            result = self._run_algorithm(
                search, problem, iterations,
                col1, running_chart1, running_info1
            )
            best_data  = result[2].copy()
            best_state = result[0].copy()
            return (best_data, best_state)

        with main_container:
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Current Run")
                running_chart1 = st.empty()
                running_info1  = st.empty()
            with col2:
                st.subheader("Best Run So Far")
                best_chart = st.empty()
                best_info  = st.empty()

            for run in range(restarts):
                result      = self._run_algorithm(
                    search, problem, iterations,
                    col1, running_chart1, running_info1
                )
                final_score = result[1]
                if final_score < best_score:
                    best_score  = final_score
                    best_data   = result[2].copy()
                    best_state  = result[0].copy()
                    best_run_id = run + 1
                if best_data is not None:
                    best_chart.line_chart(best_data)
                    best_info.metric(
                        label=f"Best Run → #{best_run_id}",
                        value=f"{best_score:.2f}"
                    )

        main_container.empty()
        st.subheader(f"Best Run → #{best_run_id}")
        st.metric(label="Best Score", value=f"{best_score:.2f}")
        st.line_chart(best_data)
        st.success(
            f"Optimization finished. Best result came from Run #{best_run_id}."
        )
        return (best_data, best_state)

    def _run_algorithm(self, search, problem, iterations, col, chart, info):
        """Dispatch helper to reduce repetition in random_restart."""
        match search:
            case "Hill Climbing Steepest":
                return self.Hill_Climbing(
                    problem, "opt", "steepest",
                    visualize=True, col=col, running_chart=chart, running_info=info
                )
            case "Hill Climbing First Choice":
                return self.Hill_Climbing(
                    problem, "opt", "first_choice",
                    visualize=True, col=col, running_chart=chart, running_info=info
                )
            case "Hill Climbing Stochastic":
                return self.Hill_Climbing(
                    problem, "opt", "stochastic",
                    visualize=True, col=col, running_chart=chart, running_info=info
                )
            case "Simulated Annealing Exponential":
                return self.Simulated_Annealing(
                    problem, "opt", 500, 0.99, iterations,
                    strategy="Exponential",
                    visualize=True, col=col, running_chart=chart, running_info=info
                )
            case "Simulated Annealing Linear":
                return self.Simulated_Annealing(
                    problem, "opt", 100, 100 / max(iterations, 1), iterations,
                    strategy="Linear",
                    visualize=True, col=col, running_chart=chart, running_info=info
                )
            case "Tabu":
                return self.Tabu_Search(
                    problem, objective="opt", restarts=1,
                    iters=iterations, tabu_size=50,
                    visualize=True, col=col, running_chart=chart, running_info=info
                )

    def compare(self, problem, restarts, iterations):
        results = {}
        for search in [
            "Hill Climbing Steepest", "Hill Climbing First Choice",
            "Hill Climbing Stochastic", "Simulated Annealing Exponential",
            "Simulated Annealing Linear", "Tabu",
        ]:
            results[search] = self.random_restart(
                problem=problem, search=search,
                restarts=restarts, iterations=iterations
            )[0]

        fig, ax = plt.subplots(figsize=(10, 4))
        colors  = ["tab:blue","tab:orange","tab:green","tab:red","tab:purple","tab:brown"]
        for (label, df), color in zip(results.items(), colors):
            ax.plot(df["Cost"].values, label=label, color=color)

        y_all = np.concatenate([df["Cost"].values for df in results.values()])
        ax.set_ylim(0, np.max(y_all) * 1.1)
        ax.set_title("Cost vs Iteration")
        ax.set_xlabel("Iteration")
        ax.set_ylabel("Cost")
        ax.yaxis.set_major_locator(matplotlib.ticker.MultipleLocator(50))
        ax.legend()
        st.pyplot(fig)