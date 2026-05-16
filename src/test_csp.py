import time
from problem import EnsiaProblem
from optimizer import Optimizer

def print_student_timetable(state, prob, group_name="Y1_G1"):
    print(f"\nTimetable for Group: {group_name}")
    print("-" * 139)
    
    days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"]
    grid = [["" for _ in range(6)] for _ in range(5)]
    
    target_group = next((g['id'] for g in prob.groups if g['name'] == group_name), 1)
        
    for eid, (rid, slot) in state.items():
        event = prob.events_by_id[eid]
        is_lec = (event["type_id"] == 1)
        
        attends = False
        if is_lec and target_group in prob.section_to_group[event["target_id"]]:
            attends = True
        elif not is_lec and event["target_id"] == target_group:
            attends = True
                
        if attends:
            day = slot // 6
            time_idx = slot % 6
            abbrev = event['name'].split('_')[0]
            
            type_name = "TP"
            if event["type_id"] == 1: type_name = "Lec"
            elif event["type_id"] == 2: type_name = "TD"
                
            rname = prob.rooms_by_id[rid]['name'].replace("TUTORIAL", "TUTO").replace("AMPHI", "AMPHI").replace("CIRCUIT_LAB", "CIRC")
            if len(rname) > 7: rname = rname[:7]
            
            grid[day][time_idx] = f"{abbrev} {type_name} {rname}"

    col_w = 18
    times = ["08:30 - 10:00", "10:10 - 11:40", "11:50 - 13:20", "13:30 - 15:00", "15:10 - 16:40", "16:50 - 18:20"]
    header = f"{'Day':10} | " + " | ".join([f"{t:<{col_w}}" for t in times])
    print(header)
    print("-" * (13 + 6 * (col_w + 3)))
    
    for i in range(5):
        row = [f"{days[i]:10}"] + [f"{cell:<{col_w}}" for cell in grid[i]]
        print(" | ".join(row))
    print("-" * (13 + 6 * (col_w + 3)))

def violated_hard_constraints(prob, state):
    tbs = prob.constraint_obj._build_lookup_tables(state)
    category_args = {
        'slot_to_rooms': (tbs[0],), 'slot_to_groups': (tbs[1],), 
        'slot_to_teachers': (tbs[2],), 'state_based': (state,), 
        'teacher_based': (tbs[3],)
    }
    
    violated = 0
    for hc in prob.hard_constraints_list:
        if isinstance(hc, str): continue
        fn = getattr(prob.constraint_obj, hc['rule'])
        res = fn(*category_args[hc['category']], count=True)
        violated += res if isinstance(res, int) else (0 if res else 1)

    return violated

def prompt_groups(prob, state):
    all_groups = {g['name'] for g in prob.groups}

    while True:
        try:
            n = int(input(f"\nHow many group timetables would you like to view? ").strip())
            if n == 0:
                return None
            if n < 1:
                print("Please enter a positive number.")
                continue
            break
        except ValueError:
            print("Invalid input. Please enter a valid integer.")

    chosen = []
    for i in range(n):
        while True:
            raw = input(f"Enter group {i+1} (format YEAR_GROUP, e.g. 1_4 for Y1_G4): ").strip()
            try:
                year, group = raw.split("_")
                group_name = f"Y{int(year)}_G{int(group)}"
                if group_name not in all_groups:
                    print(f"Group '{group_name}' not found. Please try again.")
                    continue
                chosen.append(group_name)
                break
            except (ValueError, AttributeError):
                print("Invalid format. Please use YEAR_GROUP (e.g. 1_4).")

    for group_name in chosen:
        print_student_timetable(state, prob, group_name)

def get_param(prompt, default):
    val = input(f"{prompt} (enter 'd' for default value ({default})): ").strip().lower()
    if val == 'd' or val == '':
        return default
    try:
        return type(default)(val)
    except ValueError:
        return default

def select_algorithm():
    print("\nSelect an optimization algorithm:")
    print("  1. Simulated Annealing")
    print("  2. Hill Climbing")
    print("  3. Random Restart Hill Climbing")
    print("  4. Tabu Search")

    while True:
        try:
            choice = int(input("Enter your choice (1-4): ").strip())
            if choice not in (1, 2, 3, 4):
                print("Please enter a number between 1 and 4.")
                continue
            break
        except ValueError:
            print("Invalid input. Please enter a valid integer.")

    if choice == 1:
        temp = get_param("Enter initial temperature", 500.0)
        rate = get_param("Enter cooling rate", 0.99)
        iters = get_param("Enter max iterations", 1000)
        strat_choice = get_param("Select strategy (1: Linear, 2: Exponential)", 2)
        strat = "Exponential" if strat_choice == 2 else "Linear"
        return "sa", {"initial_temp": temp, "cooling_rate": rate, "max_iterations": iters, "strategy": strat}

    elif choice == 2:
        print("\nSelect Hill Climbing strategy:")
        print("  1. Steepest\n  2. First Choice\n  3. Stochastic")
        sc = get_param("Enter your choice (1-3)", 1)
        strategy_map = {1: "steepest", 2: "first_choice", 3: "stochastic"}
        return "hc", {"strategy": strategy_map.get(sc, "steepest")}

    elif choice == 3:
        print("\nSelect base Hill Climbing strategy for Random Restart:")
        print("  1. Steepest\n  2. First Choice\n  3. Stochastic")
        sc = get_param("Enter your choice (1-3)", 1)
        restarts = get_param("Enter number of restarts", 50)
        strategy_map = {1: "steepest", 2: "first_choice", 3: "stochastic"}
        return "rrhc", {"base_strategy": strategy_map.get(sc, "steepest"), "num_restarts": restarts}

    elif choice == 4:
        restarts = get_param("Enter number of restarts", 5)
        iters = get_param("Enter iterations per restart", 300)
        size = get_param("Enter tabu list size", 20)
        return "tabu", {"restarts": restarts, "iters": iters, "tabu_size": size}

def run_optimizer(prob, algo, kwargs):
    init_cost = prob.evaluate(prob.state)

    algo_labels = {
        "sa": "Simulated Annealing",
        "hc": "Hill Climbing",
        "rrhc": "Random Restart Hill Climbing",
        "tabu": "Tabu Search"
    }
    print(f"\nRunning Soft Constraints Optimization ({algo_labels[algo]})...")

    if algo == "sa":
        opt_state, _ = Optimizer.Simulated_Annealing(Optimizer, prob, objective="opt", **kwargs)
    elif algo == "hc":
        opt_state, _ = Optimizer.Hill_Climbing(Optimizer, prob, objective="opt", **kwargs)
    elif algo == "rrhc":
        opt_state, _ = Optimizer.Random_Restart_Hill_Climbing(Optimizer, prob, objective="opt", **kwargs)
    elif algo == "tabu":
        opt_state, _ = Optimizer.Tabu_Search(Optimizer, prob, objective="opt", **kwargs)

    final_cost = prob.evaluate(opt_state)
    print(f"\nInitial Cost: {init_cost:.2f}")
    print(f"Final Cost: {final_cost:.2f}")
    print(f"Total Cost Improvement: {init_cost - final_cost:.2f}")

    violated = violated_hard_constraints(prob, opt_state)
    print(f"Violated hard constraints: {violated}")

    return opt_state

def main():
    print("Loading Dataset and Running CSP Backtracking...")
    t0 = time.time()
    prob = EnsiaProblem("dataset/data_s2.json", cspmethod="global_search")
    elapsed = time.time() - t0
    
    print(f"Solver completed in {elapsed:.2f} seconds.")
    print(f"Total events scheduled: {len(prob.state)} / {len(prob.events)}")
    
    violated = violated_hard_constraints(prob, prob.state)
    print(f"Violated hard constraints: {violated}")

    prompt_groups(prob, prob.state)

    algo, kwargs = select_algorithm()
    opt_state = run_optimizer(prob, algo, kwargs)

    prompt_groups(prob, opt_state)

if __name__ == '__main__':
    main()