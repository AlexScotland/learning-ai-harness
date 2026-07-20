class Observation():
    def __init__(self, agent_id: str, observation_data: dict):
        self.agent_id = agent_id
        self.observation_data = observation_data

    def update_observation(self, new_observation_data: dict):
        self.observation_data.update(new_observation_data)

    def get_observation(self) -> dict:
        return self.observation_data