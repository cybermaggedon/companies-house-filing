
import json

class State:
    def __init__(self, config_file, state_file):
        self.config = json.loads(open(config_file).read())
        self.config_file = config_file
        self.state_file = state_file
        self.state = self.load_state()
    def load_state(self):
        # FIXME: Check it exists!
        try:
            return json.loads(open(self.state_file).read())
        except:
            return {
                "transaction-id": 0,
                "submission-id": 0
            }
    def write(self):
        with open(self.state_file, "w") as f:
            f.write(json.dumps(self.state))
    def get_next_tx_id(self):
        self.state["transaction-id"] += 1
        self.write()
        return self.state["transaction-id"]
    def get_cur_tx_id(self):
        return self.state["transaction-id"]
    def get_next_submission_id(self):
        self.state["submission-id"] += 1
        self.write()
        return "S%05d" % self.state["submission-id"]
    def get_cur_submission_id(self):
        return self.state["submission-id"]
    def get(self, key):
        return self.config.get(key)
