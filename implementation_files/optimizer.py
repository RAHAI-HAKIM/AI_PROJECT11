from math import exp
import random

#defines functions and returns optimized states
class Optimizer:
    def Simulated_Annealing(self, problem, initial_temp, cooling_rate, max_iterations,strategy="Linear"):
        """
        gets the problem's current state and returns an optimized one using SA
        """

        current_state = problem.generate_valid_state()
        current_state_eval = problem.evaluate(current_state)

        best_state_so_far = current_state
        best_state_eval = current_state_eval

        T = initial_temp

        for t in range(max_iterations):
            # default behavior is Linear to avoid infinit loop
            if strategy == "Exponential":
                T *= cooling_rate
            else:
                T -= cooling_rate

            if T <= 0:
                break

            next_state = problem.move_operator(current_state)
            next_state_eval = problem.evaluate(next_state)
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

    def Tabu_Search(self, problem):
        # gets the problem's current state and returns an optimized one using tabu search
        pass

