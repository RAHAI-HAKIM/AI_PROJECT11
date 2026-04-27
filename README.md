# AI_PROJECT11
Project Statement:
Project 11: University Course-to-Room Allocator

Aim: Distinct from Exam Scheduling, this project focuses on the semester-long assignment of lectures to
physical classrooms. The goal is to optimize space usage and minimize campus travel for students/faculty
using Local Search.
a. Data Collection & Research:
• Dataset Overview:
o Bonus (Local Data): Get the Room Inventory (Floor plans, capacity, type: Lab/Lecture)
and Course Offerings (Expected attendance) from the ENSIA administration.
o Standard (International): Use the ITC2007 (International Timetabling Competition)
dataset track for "Curriculum-based Course Timetabling."

• External Resources:
o Research Simulated Annealing and Tabu Search for resource allocation.
o Study "Room Stability" (keeping a course in the same room all semester).

b. Problem Definition:
Assign a (Room, TimeSlot) tuple to every Course Event for the entire semester.

c. Constraints & Objective Function:
• Constraints:
o Hard: Room Capacity ≥ Course Enrollment. Room Type match (Electronics in Lab). No
double-booking of rooms.
o Soft: Professor Preference (consecutive classes in same room), etc.
• Objective Function:
o Minimize Penalty: The penalty will take into account the
Distance, CapacityWaste, and RoomChange.

d. Search Strategy Implementation:
• Simulated Annealing (SA):
o Start with a random valid allocation.
o Move Operator: Select a course at random and move it to a different valid room.
o Temperature: Start high (allow bad moves) and cool down (strict optimization).
• Hill Climbing with Random Restart:
o Run Hill Climbing 50 times from different random starting points and pick the best result.
• Constraint Satisfaction (CSP):
o Use CSP only to generate the initial valid solution (finding a feasible start point), then use
SA to optimize it.
e. Comparative Evaluation:
• Performance Comparison:
o Compare Hill Climbing vs. Simulated Annealing.
o Show a graph of "Cost vs. Iterations."
• Success Criteria:
o Zero Hard Constraint violations.
o Demonstrable reduction in "wasted seats" compared to the current manual schedule used
by the department.