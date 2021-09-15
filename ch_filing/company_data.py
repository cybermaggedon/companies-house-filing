
from lxml import objectify

cd_ns = "http://xmlgw.companieshouse.gov.uk"
cd_sl = "http://xmlgw.companieshouse.gov.uk/v2-1/schema/CompanyData-v3-3.xsd"

xsi_ns = "http://www.w3.org/2001/XMLSchema-instance"

class CompanyData:

    @staticmethod
    def create_request(st):

        maker = objectify.ElementMaker(
            annotate=False,
            namespace=cd_ns,
            nsmap={
                None: cd_ns
            }
        )

        cdr = maker.CompanyDataRequest(
            maker.CompanyNumber(st.get("company-number")),
            maker.CompanyAuthenticationCode(
                st.get("company-authentication-code")
            ),
            maker.MadeUpDate(
                st.get("made-up-date")
            )
        )
            
        cdr.set("{%s}schemaLocation" % xsi_ns, cd_ns + " " + cd_sl)

        return cdr
