# 🏫 SmartRoom: University Space Optimizer

> **Solving the "Musical Chairs" problem for campus classrooms.**

## 🎯 What is this?

Every semester, universities struggle to fit hundreds of classes into a limited number of rooms. **SmartRoom** is an AI-powered tool that automatically builds the perfect schedule. It ensures that every student has a seat, every lab has the right equipment, and professors don't have to hike across campus between lectures.

---

## 🧩 How it Solves the Puzzle

### 1. The Rules (Hard Constraints)

The app treats these as "deal-breakers." A schedule isn't finished until:

* 🪑 **No Crowding:** You can't put 50 students in a room with 30 chairs.
* 🧪 **Right Lab:** You can't teach Chemistry in a History hall.
* 🗓️ **No Double-Booking:** Two classes can't exist in the same room at the same time.

### 2. The Comforts (Soft Constraints)

Once the rules are met, the AI tries to make life better for everyone:

* 🚶 **Short Walks:** Keeps classes for the same group of students close together.
* 📍 **Consistency:** Tries to keep a specific course in the same room all semester.
* 📉 **No Waste:** Avoids putting a small 10-person seminar in a 300-seat auditorium.

---

## 🧠 The "Brain" (Our Strategy)

We use three different AI "styles" to find the best room layout:

* **The Explorer (Simulated Annealing):** Starts by trying random ideas, then slowly narrows down to the most efficient one.
* **The Grinder (Hill Climbing):** Makes small, constant improvements until it can’t find any more ways to get better.
* **The Memory Expert (Tabu Search):** Remembers where it has already looked so it doesn't waste time repeating the same mistakes.

---

## 📈 Success Goals

We aren't just making a schedule; we’re making it **better** than a human can.

1. **Zero Conflicts:** No more "Who is supposed to be in this room?" arguments.
2. **Less Walking:** Students spend more time learning and less time sprinting across campus.
3. **Space Efficiency:** Maximizing the use of every single room on campus.

---

## 📂 Data Sources

* **Real Data:** Floor plans and class lists from the **ENSIA** administration.
* **Global Benchmark:** Tested against the **ITC2007** (International Timetabling Competition) standard.
