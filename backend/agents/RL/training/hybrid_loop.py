from RL.utils.trajectory_filter import is_good_trajectory

offline_buffer = []

def hybrid_loop(ppo_trajectories):
    good = [t for t in ppo_trajectories if is_good_trajectory(t)]
    offline_buffer.extend(good)
