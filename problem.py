class Problem:
    #defines a universisty event scheduling problem
    pass


class Constraints:
    # includes the constraints functions


class EnsiaProblem(Problem):
    def __init__(self):
        super().__init__()

        self.event_ids = set()
        self.roomids = set()
        self.hard_constraints_list = {con_name: (function)}
        self.soft_constraints_list = {con_name: (function, weight)}
        self.state = self.generate_random_state() #eventid -> (roomid, timeslot(day, slot)) # get timeslot from dataset

        

    def load_data(self, filename):
        pass # fills the sets and clears the old ones


    def generate_valid_state(self): 
        # does csp
        pass 
        # and it's depending methods

    def backtrack():
        # used by csp
        pass

    def generate_random_state(self):
        # local search
        pass

    def generate_neighbors(state, size=10): # returns at most size states
        pass
    def move_operator(self):
        return self.generate_neighbors(1)
    
    def evaluate(self, state):
        # returns float

