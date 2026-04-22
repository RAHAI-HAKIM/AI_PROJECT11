
# This is the class that implements main problem method, specific data-driven problems will enhirit from it 
class Problem:
    pass


class Constraints:
    # includes the constraints functions, seperated for clean structure
    pass

# ensia specific problem class
class EnsiaProblem(Problem):
    def __init__(self, dataset, cspmethod="global_search"):
        super().__init__()

        # load data elements
        data = self.load_data(dataset)
        self.events = data[0]
        self.rooms = data[1]
        # access data elements by their id
        self.events_by_id = {e["id"]: e for e in self.events}
        self.rooms_by_id  = {r["id"]:  r for r in self.rooms}

        # fill the (room, time) tuple, assuming time is a number from 0-29
        slots = []
        for r in self.rooms:
            for t in range(30):
                slots.append((r["id"], t))
        self.slots = slots
        
        # get constraint list -not handled yet-
        self.hard_constraints_list = {con_name: (function)}
        self.soft_constraints_list = {con_name: (function, weight)}

        # the state of the problem is a dict in the form:
        #  eventid -> (roomid, timeslot(day, slot)) 
        if cspmethod == "local_search": 
            state = self.generate_random_state() # generate a random assignment that might violate hard constraints
            state = self.enhance(state) # does local search csp to resolve all hard constraints
            self.state = state
        else:
            if cspmethod != "global_search": print("invalid csp method, redirecting to GS csp ...\n")
            self.state = self.generate_valid_state()
        

        

    def load_data(self, filename):
        pass # returnes a list of 2 lists having events, rooms 


    def generate_valid_state(self): 
        # does csp
        pass 
        # and it's depending methods

    def backtrack():
        # used by csp
        pass

    def generate_random_state(self):
        # random assignment, not respecting any constraints
        pass
    
    def enhance(state):
        # this method is used after generating a random state to resolve constraints using local search
        padd

    def generate_neighbors(state, size=50): # returns at most size states
        pass
    def move_operator(self):
        return self.generate_neighbors(1)
    
    def evaluate(self, state):
        # returnes the cost of a state, may need other constraint-specific methodes
        pass

