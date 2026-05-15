from math import exp
import random
from collections import deque
import streamlit as st
import pandas as pd
import numpy as np
from problem import EnsiaProblem
import matplotlib.pyplot as plt
import matplotlib

# defines functions and returns optimized states
class Optimizer:
    def Simulated_Annealing(self, problem, objective, initial_temp, cooling_rate, max_iterations,strategy="Linear",visualize=False,col=None,running_chart=None,running_info=None):
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
        if visualize:
                data = pd.DataFrame(
                        np.random.randn(0, 1),
                        columns=["Cost"]
                    )
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
            if visualize:
                    new_row = pd.DataFrame(
                        {"Cost": [current_state_eval]}
                    )
        
                    data = pd.concat([data, new_row], ignore_index=True)
                    if (t+1)%10==0:
                    # Update running chart
                        running_chart.line_chart(data)
        
                    current_partial_score = best_state_eval
        
                    running_info.metric(
                        label="Current Score",
                        value=f"{current_partial_score:.2f}"
                    )
        if visualize:
            return best_state_so_far, best_state_eval,data

        return best_state_so_far, best_state_eval

    def Hill_Climbing(self, problem, objective="opt", strategy="steepest",visualize=False,col=None,running_chart=None,running_info=None):
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
        if visualize:
                data = pd.DataFrame(
                        np.random.randn(0, 1),
                        columns=["Cost"]
                    )
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
            if visualize:
                    new_row = pd.DataFrame(
                        {"Cost": [current_eval]}
                    )
        
                    data = pd.concat([data, new_row], ignore_index=True)
                    # Update running chart
                    running_chart.line_chart(data)
        
                    current_partial_score = current_eval
        
                    running_info.metric(
                        label="Current Score",
                        value=f"{current_partial_score:.2f}"
                    )
        if visualize:
            return current_state, current_eval,data
        return current_state, current_eval

    def Random_Restart_Hill_Climbing(self, problem,objective="opt", base_strategy="steepest", num_restarts=50):
        """
        Runs Hill_Climbing multiple times from different starting points to escape local optima.
        First restart starts from problem.state, subsequent ones use a density-guided random state
        that is biased toward slots that performed well in previous restarts.
        """
        global_best_state = problem.state.copy()
        global_best_eval = float('inf')
        for every in range(num_restarts):
            problem.state = problem.generate_random_state()
            result_state, result_eval = self.Hill_Climbing(Optimizer,problem, objective=objective,strategy=base_strategy)

            if result_eval < global_best_eval:
                global_best_state = result_state
                global_best_eval = result_eval
        return global_best_state, global_best_eval

    def Tabu_Search(self, problem, objective=None, restarts=1, iters=300, tabu_size=20,visualize=False,col=None,running_chart=None,running_info=None):
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
            if visualize:
                data = pd.DataFrame(
                        np.random.randn(0, 1),
                        columns=["Cost"]
                    )
            for _ in range(iters):
                best_candidate     = None
                best_candidate_val = float("inf")

                valid_events = list(state.keys())
                # removed event_id getting ... risk of logic for algorithm
                neighbors = get_neighbors(state,size=20)
                    
                for nei in neighbors:
                    t = tuple(sorted(nei.items()))
                    if t not in tabu_set:
                        val = eval_func(nei)
                        if val < best_candidate_val:
                            best_candidate     = nei
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

                if visualize:
                    new_row = pd.DataFrame(
                        {"Cost": [best_candidate_val]}
                    )
        
                    data = pd.concat([data, new_row], ignore_index=True)
                    if (_+1)%10==0:
                    # Update running chart
                        running_chart.line_chart(data)
        
                    current_partial_score = best_val
        
                    running_info.metric(
                        label="Current Score",
                        value=f"{current_partial_score:.2f}"
                    )

            if best_val < global_best_val:
                global_best     = dict(best)
                global_best_val = best_val
        if visualize:
            return global_best, global_best_val,data

        return global_best, global_best_val
    
    def random_restart(self,problem,search,restarts,iterations):
        
        st.set_page_config(layout="wide")
        
        st.title(f"Graph Cost VS Iteration of {search}")
        
        # Main container
        main_container = st.container()
        
        # Track best run
        best_score = float("inf")
        best_data = None
        best_run_id = None
        
        TOTAL_RUNS = restarts
        if restarts==1:
            
            col1 = st.columns(1)[0]
        
            with col1:
                st.subheader("Current Run")
                running_chart1 = st.empty()
                running_info1 = st.empty()

            match search:
                    case "Hill Climbing Steepest":
                        result=self.Hill_Climbing(problem,"opt","steepest",visualize=True,col=col1,running_chart=running_chart1,running_info=running_info1)
                    case "Hill Climbing First Choice":
                        result=self.Hill_Climbing(problem,"opt","first_choice",visualize=True,col=col1,running_chart=running_chart1,running_info=running_info1)
                    case "Hill Climbing Stochastic":
                        result=self.Hill_Climbing(problem,"opt","stochastic",visualize=True,col=col1,running_chart=running_chart1,running_info=running_info1)
                    case "Simulated Annealing Exponential":
                        result=self.Simulated_Annealing(problem, "opt", 1000, 0.95, iterations,strategy="Exponential",visualize=True,col=col1,running_chart=running_chart1,running_info=running_info1)
                    case "Simulated Annealing Linear":
                        result=self.Simulated_Annealing(problem, "opt", 1000, 0.95, iterations,strategy="Linear",visualize=True,col=col1,running_chart=running_chart1,running_info=running_info1)
                    case "Tabu":
                        result=self.Tabu_Search(problem, objective="opt", restarts=1, iters=iterations, tabu_size=30,visualize=True,col=col1,running_chart=running_chart1,running_info=running_info1)

            best_data = result[2].copy()
            best_state=result[0].copy()
            return (best_data,best_state)
        
        # -----------------------------
        # LIVE MODE (2 CHARTS)
        # -----------------------------
        with main_container:
        
            col1, col2 = st.columns(2)
        
            with col1:
                st.subheader("Current Run")
                running_chart1 = st.empty()
                running_info1 = st.empty()
        
            with col2:
                st.subheader("Best Run So Far")
                best_chart = st.empty()
                best_info = st.empty()
        
            for run in range(TOTAL_RUNS):
                match search:
                    case "Hill Climbing Steepest":
                        result=self.Hill_Climbing(problem,"opt","steepest",visualize=True,col=col1,running_chart=running_chart1,running_info=running_info1)
                    case "Hill Climbing First Choice":
                        result=self.Hill_Climbing(problem,"opt","first_choice",visualize=True,col=col1,running_chart=running_chart1,running_info=running_info1)
                    case "Hill Climbing  Stochastic":
                        result=self.Hill_Climbing(problem,"opt","stochastic",visualize=True,col=col1,running_chart=running_chart1,running_info=running_info1)
                    case "Simulated Annealing Exponential":
                        result=self.Simulated_Annealing(problem, "opt", 1000, 0.95, iterations,strategy="Exponential",visualize=True,col=col1,running_chart=running_chart1,running_info=running_info1)
                    case "Simulated Annealing Linear":
                        result=self.Simulated_Annealing(problem, "opt", 1000, 0.95, iterations,strategy="Linear",visualize=True,col=col1,running_chart=running_chart1,running_info=running_info1)
                    case "Tabu":
                        result=self.Tabu_Search(problem, objective="opt", restarts=1, iters=iterations, tabu_size=30,visualize=True,col=col1,running_chart=running_chart1,running_info=running_info1)
                    # Keep best chart visible

                # Final score of this run
                final_score = result[1]
        
                # Update best run
                if final_score < best_score:
                    best_score = final_score
                    best_data = result[2].copy()
                    best_state= result[0].copy()
                    best_run_id = run + 1
                if best_data is not None:

                    best_chart.line_chart(best_data)

                    best_info.metric(
                        label=f"Best Run → #{best_run_id}",
                        value=f"{best_score:.2f}"
                    )
        
        # -----------------------------
        # FINAL MODE (1 FULL-WIDTH CHART)
        # -----------------------------
        
        # Remove the whole 2-column section
        main_container.empty()
        
        # Full-width final result
        st.subheader(f"Best Run → #{best_run_id}")
        
        st.metric(
            label="Best Score",
            value=f"{best_score:.2f}"
        )
        
        st.line_chart(best_data)
        
        st.success(
            f"Optimization finished. Best result came from Run #{best_run_id}."
        )
        return (best_data,best_state)
    
    def compare(self, problem, restarts, iterations):
            
        y1 = self.random_restart(
            problem=problem,
            search="Hill Climbing Steepest",
            restarts=restarts,
            iterations=iterations
        )[0]
        y2 = self.random_restart(
            problem=problem,
            search="Hill Climbing First Choice",
            restarts=restarts,
            iterations=iterations
        )[0]
        y3 = self.random_restart(
            problem=problem,
            search="Hill Climbing Stochastic",
            restarts=restarts,
            iterations=iterations
        )[0]
        y4 = self.random_restart(
            problem=problem,
            search="Simulated Annealing Exponential",
            restarts=restarts,
            iterations=iterations
        )[0]
        y5 = self.random_restart(
            problem=problem,
            search="Simulated Annealing Linear",
            restarts=restarts,
            iterations=iterations
        )[0]
        y6 = self.random_restart(
            problem=problem,
            search="Tabu",
            restarts=restarts,
            iterations=iterations
        )[0]
        
        y1 = y1["Cost"].values
        y2 = y2["Cost"].values
        y3 = y3["Cost"].values
        y4 = y4["Cost"].values
        y5 = y5["Cost"].values
        y6 = y6["Cost"].values
        
        fig, ax = plt.subplots(figsize=(10, 4))
        y_all = np.concatenate([y1, y2, y3, y4, y5,y6])
        ax.plot(y1, label="Hill Climbing Steepest")
        ax.plot(y2, label="Hill Climbing First Choice")
        ax.plot(y3, label="Hill Climbing  Stochastic")
        ax.plot(y4, label="Simulated Annealing Exponential")
        ax.plot(y5, label="Simulated Annealing Linear")
        ax.plot(y6, label="Tabu")
        ax.set_title("Cost vs Iteration")
        ax.set_xlabel("Iteration")
        ax.set_ylabel("Cost")
        
        ax.set_ylim(0, np.max(y_all) * 1.1)
        
        ax.yaxis.set_major_locator(matplotlib.ticker.MultipleLocator(50))
        ax.legend()
        st.pyplot(fig)


