# Bounty file
The bounty file is a ledger for requested stuff to be implimented and fixed by all

## Rules 
- each one bounty must be completed at a time (we wont merge more then one bounty at a time).
- if you complete a bounty mark it as done in the markdown.
- anyone can add a bounty as long as it is a real one and not a task.
- before pushing ANYTHING, make sure to run `run_tests.sh` to make sure you didnt break any feature.

# Bounties 
## Bugs
- [ ] solving CSP using local search is not working (because generate neighbors assumes state is valid need new versions for those).
- [X] evaluate CSP is a mess, please invistigate and create more bounties to fix the issue.
- [X] invistigate evaluate solving csp using local search does not make much progress.
- [X] In Simuated_annealing > move_operator -- function takes a long time not progress is made.
- [X] In tabo search > generate neighbors -- generates only 2 neighbors no optimization is made.
- [X] In Hill_climbing -- works fine but no optimization is made.
## Additionals
- [ ] logging in each optimazation function.
- [ ] documentation.
- [ ] cleaner problem with better comments.
- [ ] add `self.constraint_violation_cost` to trach the violated constraints while solving using csp.
