
import hashlib
from lxml import objectify

env_ns = "http://www.govtalk.gov.uk/CM/envelope"
env_sl = "http://xmlgw.companieshouse.gov.uk/v2-1/schema/Egov_ch-v2-0.xsd"

xsi_ns = "http://www.w3.org/2001/XMLSchema-instance"

class Envelope:

    @staticmethod
    def create(st, content, cls, qualifier):

        maker = objectify.ElementMaker(
            annotate=False,
            namespace=env_ns,
            nsmap={
                None: env_ns
            }
        )

        pres_id = st.get("presenter-id")
        pres_hash = hashlib.md5(pres_id.encode("utf-8")).hexdigest()

        auth_val = st.get("authentication")
        auth_hash = hashlib.md5(auth_val.encode("utf-8")).hexdigest()

        env = maker.GovTalkMessage(
            maker.EnvelopeVersion("1.0"),
            maker.Header(
                maker.MessageDetails(
                    maker.Class(cls),
                    maker.Qualifier(qualifier),
                    maker.TransactionID(st.get_next_tx_id()),
                    maker.GatewayTest(st.get("test-flag"))
                ),
                maker.SenderDetails(
                    maker.IDAuthentication(
                        maker.SenderID(pres_hash),
                        maker.Authentication(
                            maker.Method("clear"),
                            maker.Value(auth_hash)
                        )
                    ),
                    maker.EmailAddress(st.get("email"))
                )
            ),
            maker.GovTalkDetails(
                maker.Keys()
            ),
            maker.Body(
                content
            )
        )

        env.set("{%s}schemaLocation" % xsi_ns, env_ns + " " + env_sl)

        return env
