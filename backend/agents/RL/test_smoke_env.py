import traceback

print('Starting RL env smoke test')
try:
    from backend.agents.RL.environment import YUSR_UI_MultiAgentEnv
    print('Imported YUSR_UI_MultiAgentEnv')
    env = YUSR_UI_MultiAgentEnv(env_config={})
    print('Instantiated env')
    obs, info = env.reset()
    print('reset OK. obs keys:', list(obs.keys()))
    print('nav_agent obs keys:', list(obs['nav_agent'].keys()))
    actions = {'nav_agent': 0, 'pers_agent': 0, 'llm_agent': 0}
    obs2, rewards, terminated, truncated, info2 = env.step(actions)
    print('step OK. rewards:', rewards)
    print('terminated __all__:', terminated.get('__all__'))
    print('truncated __all__:', truncated.get('__all__'))
except Exception as e:
    print('Exception during smoke test:')
    traceback.print_exc()
