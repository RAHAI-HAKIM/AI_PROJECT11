import time
from problem import EnsiaProblem
from optimizer import Optimizer
from test_csp_global import *

def main():
    print("Loading Dataset and Generating Random State (Local Search CSP)...")
    t0 = time.time()
    prob = EnsiaProblem("dataset/data_s2.json", cspmethod="local_search")
    elapsed = time.time() - t0

    print(f"Random state generated in {elapsed:.2f} seconds.")
    print(f"Total events scheduled: {len(prob.state)} / {len(prob.events)}")

    init_violations = violated_hard_constraints(prob, prob.state)
    print(f"Initial hard constraint violations: {init_violations}")

    prompt_groups(prob, prob.state)

    max_steps = get_param("\nEnter max steps for Min-Conflicts", 5000)

    print(f"\nRunning Min-Conflicts Local Search (max_steps={max_steps})...")
    t1 = time.time()
    final_state = prob.min_conflicts(max_steps=max_steps)
    elapsed = time.time() - t1

    print(f"\nMin-Conflicts completed in {elapsed:.2f} seconds.")

    final_violations = violated_hard_constraints(prob, final_state)
    print(f"Initial hard constraint violations: {init_violations}")
    print(f"Final hard constraint violations:   {final_violations}")
    print(f"Total violation reduction: {init_violations - final_violations}")

    if final_violations == 0:
        print("\nFeasible schedule found! Running soft constraint optimization...")

        print("\nSelect an optimization algorithm:")
        print("  1. Simulated Annealing")
        print("  2. Hill Climbing")
        print("  3. Random Restart Hill Climbing")
        print("  4. Tabu Search")

        while True:
            try:
                choice = int(input("Enter your choice (1-4): ").strip())
                if choice in (1, 2, 3, 4): break
                print("Please enter a number between 1 and 4.")
            except ValueError:
                print("Invalid input. Please enter a valid integer.")

        prob.state = final_state
        init_cost = prob.evaluate(prob.state)

        algo_labels = {1: "Simulated Annealing", 2: "Hill Climbing", 3: "Random Restart Hill Climbing", 4: "Tabu Search"}
        print(f"\nRunning Soft Constraints Optimization ({algo_labels[choice]})...")
        t2 = time.time()

        if choice == 1:
            temp = get_param("Enter initial temperature", 200.0)
            rate = get_param("Enter cooling rate", 0.999)
            iters = get_param("Enter max iterations", 2500)
            strat_choice = get_param("Select strategy (1: Linear, 2: Exponential)", 2)
            strat = "Exponential" if strat_choice == 2 else "Linear"
            opt_state, _ = Optimizer.Simulated_Annealing(Optimizer, prob, objective="opt",
                                                          initial_temp=temp, cooling_rate=rate,
                                                          max_iterations=iters, strategy=strat)
        elif choice == 2:
            print("\nSelect Hill Climbing strategy:\n  1. Steepest\n  2. First Choice\n  3. Stochastic")
            sc = get_param("Enter your choice (1-3)", 1)
            strategy_map = {1: "steepest", 2: "first_choice", 3: "stochastic"}
            opt_state, _ = Optimizer.Hill_Climbing(Optimizer, prob, objective="opt",
                                                    strategy=strategy_map.get(sc, "steepest"))
        elif choice == 3:
            print("\nSelect base Hill Climbing strategy:\n  1. Steepest\n  2. First Choice\n  3. Stochastic")
            sc = get_param("Enter your choice (1-3)", 1)
            restarts = get_param("Enter number of restarts", 50)
            strategy_map = {1: "steepest", 2: "first_choice", 3: "stochastic"}
            opt_state, _ = Optimizer.Random_Restart_Hill_Climbing(Optimizer, prob, objective="opt",
                                                                   base_strategy=strategy_map.get(sc, "steepest"),
                                                                   num_restarts=restarts)
        elif choice == 4:
            restarts = get_param("Enter number of restarts", 1)
            iters = get_param("Enter iterations per restart", 1000)
            size = get_param("Enter tabu list size", 50)
            opt_state, _ = Optimizer.Tabu_Search(Optimizer, prob, objective="opt",
                                                  restarts=restarts, iters=iters, tabu_size=size)

        elapsed_opt = time.time() - t2
        print(f"\nOptimization completed in {elapsed_opt:.2f} seconds.")

        final_cost = prob.evaluate(opt_state)
        print(f"Initial Cost: {init_cost:.2f}")
        print(f"Final Cost:   {final_cost:.2f}")
        print(f"Total Cost Improvement: {init_cost - final_cost:.2f}")

        violated = violated_hard_constraints(prob, opt_state)
        print(f"Violated hard constraints: {violated}")

        prompt_groups(prob, opt_state)
    else:
        print("\nNo fully feasible schedule found within the given steps.")
        print("You can view the best partial solution found:")
        prompt_groups(prob, final_state)

if __name__ == '__main__':
    main()
