
from lxml import objectify, etree
import requests

class Client:

    def __init__(self, state):
        self.state = state

    def get_next_tx_id(self):
        return self.state.get_next_tx_id()

    def call(self, st, env):

        header = {
            "Content-Type": "text/xml"
        }

        objectify.deannotate(env, cleanup_namespaces=True)
        enc = etree.tostring(env, pretty_print=True, xml_declaration=True)

        resp = requests.post(self.state.get("url"), data=enc, headers=header)

        if resp.status_code != 200:
            raise RuntimeError("Status " + str(resp.status_code))

        root = objectify.fromstring(resp.text.encode("utf-8"))

        self.review_errors(root)

        return root

    def review_errors(self, env):
        err = None
        try:
            for err in env.GovTalkDetails.GovTalkErrors.Error:
                err = err.Text
                break
        except:
            # No errors.
            pass
        if err: raise RuntimeError(err)
