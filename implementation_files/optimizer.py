
#defines functions and returns optimized states
class Optimizer:
    def Simulated_Annealing(self, problem, initial_temp, cooling_rate, max_iterations):
        # gets the problem's current state and returns an optimized one using SA
        pass

    def Hill_Climbing(self, problem, strategy="steepest"):
        # gets the problem's current state and returns an optimized one using the choosen HC variant
        pass

    def Random_Restart_Hill_Climbing(self, problem, base_strategy="steepest", num_restarts=50):
        # calls the choosen HC variant to optimize -num_restart- randomely choosen valid states and selects the best
        pass

    def Tabu_Search(self, problem):
        # gets the problem's current state and returns an optimized one using tabu search
        pass

