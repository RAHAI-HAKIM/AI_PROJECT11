
# define some functionality to test experiment

def inspect_state(state):
    # build a reverse mapping to check collisions
    # (room_id,slot) -> [event_id]
    reverse_mapping = dict()
    for eid,val in state.items():
        if val not in reverse_mapping:
            reverse_mapping[val] = []
            reverse_mapping[val].append(eid)
    for key,val in reverse_mapping.items():
        print(f"assigned {key} to {val}")
