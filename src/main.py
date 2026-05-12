from problem import EnsiaProblem
from optimizer import Optimizer


# Testing global search csp
global_search = EnsiaProblem('dataset/data_s2.json', 'global_search')
print(global_search.is_consistent(global_search.state))

opt = Optimizer()
st, ev = opt.Simulated_Annealing(global_search)
print(ev)
st, ev = opt.Tabu_Search(global_search)
print(ev)