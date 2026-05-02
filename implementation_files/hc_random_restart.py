import numpy as np
import random

class MultiFlavorHeuristicEngine:
    def __init__(self, lectures, slots, rooms, learning_rate=0.15):
        self.lectures = lectures
        self.options = [(s, r) for s in slots for r in rooms]
        self.num_lectures = len(lectures)
        self.num_options = len(self.options)
        self.lr = learning_rate
        
        # --- THE DENSITY MAP (The Learning Brain) ---
        self.density_map = np.full((self.num_lectures, self.num_options), 1.0 / self.num_options)
        
        self.global_best_sched = None
        self.global_best_score = float('inf')

    def get_fitness(self, schedule):
        conflicts = 0
        used = set()
        for pos in schedule:
            if pos in used: conflicts += 1
            used.add(pos)
        return conflicts

    def get_distance(self, pos1, pos2):
        return np.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)

    def smart_restart(self):
        """Uses Optimized Randomness to pick a starting point."""
        return [self.options[np.random.choice(self.num_options, p=self.density_map[i])] 
                for i in range(self.num_lectures)]

    def move_operator(self, schedule, idx):
        """Distance-Gated Transformation Logic."""
        curr_p = schedule[idx]
        dists = [self.get_distance(curr_p, p) for p in schedule]
        avg_d = np.mean(dists)
        
        # find closest neighbor
        min_d = float('inf')
        c_idx = -1
        for i, p in enumerate(schedule):
            if i != idx:
                d = self.get_distance(curr_p, p)
                if d < min_d: min_d, c_idx = d, i

        new_s = list(schedule)
        if min_d < avg_d: # Local Swap
            new_s[idx], new_s[c_idx] = new_s[c_idx], new_s[idx]
        else: # Density Jump
            jump_idx = np.random.choice(self.num_options, p=self.density_map[idx])
            new_s[idx] = self.options[jump_idx]
        return new_s

    #les algos

    def steepest_ascent(self, schedule):
        curr_s = schedule
        curr_f = self.get_fitness(curr_s)
        while True:
            best_neighbor = None
            best_f = curr_f
            # Check every single lecture's best move
            for i in range(self.num_lectures):
                neighbor = self.move_operator(curr_s, i)
                nf = self.get_fitness(neighbor)
                if nf < best_f:
                    best_f = nf
                    best_neighbor = neighbor
            if best_neighbor:
                curr_s, curr_f = best_neighbor, best_f
            else: break # Local optimum reached
        return curr_s, curr_f

    def stochastic_hc(self, schedule, steps=200):
        curr_s = schedule
        curr_f = self.get_fitness(curr_s)
        for _ in range(steps):
            idx = random.randint(0, self.num_lectures - 1)
            neighbor = self.move_operator(curr_s, idx)
            nf = self.get_fitness(neighbor)
            if nf <= curr_f: # Accepts equal or better
                curr_s, curr_f = neighbor, nf
        return curr_s, curr_f

    def first_choice_hc(self, schedule, steps=200):
        curr_s = schedule
        curr_f = self.get_fitness(curr_s)
        for _ in range(steps):
            idx = random.randint(0, self.num_lectures - 1)
            neighbor = self.move_operator(curr_s, idx)
            nf = self.get_fitness(neighbor)
            if nf < curr_f: # Only accepts strictly better
                curr_s, curr_f = neighbor, nf
        return curr_s, curr_f

    #hna a sa7

    def solve(self, cycles=10):
        flavors = ['steepest', 'stochastic', 'first_choice']
        
        for c in range(cycles):
            for flavor in flavors:
                # 1. RESTART (Optimized Randomness)--hna sa7 tani
                start_node = self.smart_restart()
                
                # 2. clim (by using the current flavor)
                if flavor == 'steepest':
                    res, score = self.steepest_ascent(start_node)
                elif flavor == 'stochastic':
                    res, score = self.stochastic_hc(start_node)
                else:
                    res, score = self.first_choice_hc(start_node)
                
                # 3. update density
                if score < self.global_best_score:
                    self.global_best_score = score
                    self.global_best_sched = res
                    # update the map
                    for i, pos in enumerate(res):
                        opt_idx = self.options.index(pos)
                        self.density_map[i] *= (1 - self.lr)
                        self.density_map[i, opt_idx] += self.lr
                        self.density_map[i] /= self.density_map[i].sum()
                    
                    print(f"Cycle {c} [{flavor}]: New Best Score {score}")
                
                if self.global_best_score == 0: return self.global_best_sched

        return self.global_best_sched

# test khfif 
engine = MultiFlavorHeuristicEngine([f"L{i}" for i in range(30)], range(10), range(5))
engine.solve(cycles=50)