# def is_good_trajectory(traj):
#     return (
#         traj["total_reward"] >= 0.8 and
#         traj["invalid_actions"] == 0 and
#         traj["dependency_violations"] <= 1 and
#         traj["completed"]
#     )

def keep_trajectory(traj: dict) -> bool:
    return (
        traj["total_reward"] >= 1.0 and
        traj["failures"] == 0 and
        traj["refinements"] <= 1 and
        traj["completed"]
    )
