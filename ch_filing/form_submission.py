
from lxml import objectify
import base64

fs_ns = "http://xmlgw.companieshouse.gov.uk/Header"
fs_sl = "http://xmlgw.companieshouse.gov.uk/v1-1/schema/forms/FormSubmission-v2-11.xsd"

xsi_ns = "http://www.w3.org/2001/XMLSchema-instance"

class Accounts:

    @staticmethod
    def create_submission(st, fname, data):

        maker = objectify.ElementMaker(
            annotate=False,
            namespace=fs_ns,
            nsmap={
                None: fs_ns
            }
        )

        data = base64.b64encode(data.encode("utf-8")).decode("utf-8")

        # Truncated base64 error
#        data = data[:10]

        fs = maker.FormSubmission(
            maker.FormHeader(
                maker.CompanyNumber(st.get("company-number")),
                maker.CompanyType(st.get("company-type")),
                maker.CompanyName(st.get("company-name")),
                maker.CompanyAuthenticationCode(
                    st.get("company-authentication-code")
                ),
                maker.PackageReference(st.get("package-reference")),
                maker.Language("EN"),
                maker.FormIdentifier("Accounts"),
                maker.SubmissionNumber(st.get_next_submission_id()),
                maker.ContactName(st.get("contact-name")),
                maker.ContactNumber(st.get("contact-number")),
            ),
            maker.DateSigned(st.get("date-signed")),
            maker.Form(),
            maker.Document(
                maker.Data(data),
                maker.Date(st.get("date")),
                maker.Filename(fname),
                maker.ContentType("application/xml"),
                maker.Category("ACCOUNTS"),
            )
        )

        fs.set("{%s}schemaLocation" % xsi_ns, fs_ns + " " + fs_sl)

        return fs
