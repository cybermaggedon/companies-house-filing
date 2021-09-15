
from lxml import objectify

gss_ns="http://xmlgw.companieshouse.gov.uk"
gss_sl="http://xmlgw.companieshouse.gov.uk/v2-1/schema/forms/GetSubmissionStatus-v2-5.xsd"

xsi_ns = "http://www.w3.org/2001/XMLSchema-instance"

class SubmissionStatus:

    def create_request(st, sub_id=None):

        maker = objectify.ElementMaker(
            annotate=False,
            namespace=gss_ns,
            nsmap={
                None: gss_ns
            }
        )

        if sub_id:
            c = maker.GetSubmissionStatus(
                maker.SubmissionNumber(sub_id),
                maker.PresenterID(st.get("presenter-id")),
            )
        else:
            c = maker.GetSubmissionStatus(
                maker.PresenterID(st.get("presenter-id")),
            )

        c.set("{%s}schemaLocation" % xsi_ns, gss_ns + " " + gss_sl)

        return c
