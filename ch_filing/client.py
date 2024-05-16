
from lxml import objectify, etree
import requests

class AuthenticationFailure(RuntimeError):
    pass

# Error 9999 is not documented.
class SuspectedAccountsCorruption(RuntimeError):
    pass

# Error 100 is not documented.
class SuspectedValidationFailure(RuntimeError):
    pass

class RequestFailure(RuntimeError):
    pass

class PrivacyFailure(RuntimeError):
    pass

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

        try:
            resp = requests.post(self.state.get("url"), data=enc,
                                 headers=header)
        except requests.exceptions.SSLError as e:
            raise PrivacyFailure(str(e))
        except requests.exceptions.ConnectionError as e:
            raise RequestFailure(str(e))

        if resp.status_code != 200:
            raise RuntimeError("Status " + str(resp.status_code))

        root = objectify.fromstring(resp.text.encode("utf-8"))

        self.review_errors(root)

        return root

    def review_errors(self, env):
        err = None
        try:
            for err in env.GovTalkDetails.GovTalkErrors.Error:

                errno = int(err.Number)

                if errno == 502:
                    err = AuthenticationFailure(err.Text)
                if errno == 9999:
                    err = SuspectedAccountsCorruption(err.Text)
                if errno == 100:
                    err = SuspectedValidationFailure(err.Text)
                else:
                    err = RuntimeError(err.Text)
                break
        except:
            # No errors.
            pass
        if err: raise err
