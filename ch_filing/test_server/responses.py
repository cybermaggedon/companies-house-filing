from lxml import etree, objectify
from typing import List, Dict

class ResponseBuilder:
    """Build XML responses for the test server"""
    
    ENV_NS = "http://www.govtalk.gov.uk/CM/envelope"
    
    @staticmethod
    def build_envelope(body_content):
        """Build a GovTalk envelope with the given body content"""
        maker = objectify.ElementMaker(
            annotate=False,
            namespace=ResponseBuilder.ENV_NS,
            nsmap={None: ResponseBuilder.ENV_NS}
        )
        
        env = maker.GovTalkMessage(
            maker.EnvelopeVersion("1.0"),
            maker.Header(
                maker.MessageDetails(
                    maker.Class("response"),
                    maker.Qualifier("response"),
                    maker.TransactionID("1")
                ),
                maker.SenderDetails()
            ),
            maker.GovTalkDetails(
                maker.Keys()
            ),
            maker.Body(body_content)
        )
        
        objectify.deannotate(env, cleanup_namespaces=True)
        return etree.tostring(env, pretty_print=True, xml_declaration=True, encoding='UTF-8').decode('utf-8')
        
    @staticmethod
    def build_error_response(error_code: int, error_text: str):
        """Build an error response"""
        maker = objectify.ElementMaker(annotate=False)
        
        body = maker.dummy()  # Empty body
        env = objectify.fromstring(ResponseBuilder.build_envelope(body).encode('utf-8'))
        
        # Add error details
        errors = maker.GovTalkErrors(
            maker.Error(
                maker.Number(str(error_code)),
                maker.Text(error_text)
            )
        )
        env.GovTalkDetails.append(errors)
        
        objectify.deannotate(env, cleanup_namespaces=True)
        return etree.tostring(env, pretty_print=True, xml_declaration=True, encoding='UTF-8').decode('utf-8')
        
    @staticmethod
    def build_company_data_response(company_number: str, company_data: Dict):
        """Build a CompanyData response"""
        cd_ns = "http://xmlgw.companieshouse.gov.uk"
        maker = objectify.ElementMaker(
            annotate=False,
            namespace=cd_ns,
            nsmap={None: cd_ns}
        )
        
        # Build SIC codes
        sic_codes = maker.SICCodes()
        for code in company_data.get('sic_codes', []):
            sic_codes.append(maker.SICCode(code))
            
        # Build address
        addr = company_data.get('address', {})
        address = maker.RegisteredOfficeAddress(
            maker.Premise(addr.get('premise', '')),
            maker.Street(addr.get('street', '')),
            maker.Thoroughfare(addr.get('thoroughfare', '')),
            maker.PostTown(addr.get('post_town', '')),
            maker.Postcode(addr.get('postcode', '')),
            maker.Country(addr.get('country', ''))
        )
        
        # Build company data
        company_data_elem = maker.CompanyData(
            maker.CompanyName(company_data.get('name', '')),
            maker.CompanyNumber(company_number),
            maker.CompanyCategory(company_data.get('category', '')),
            maker.Jurisdiction(company_data.get('jurisdiction', '')),
            maker.TradingOnMarket(str(company_data.get('trading', False)).lower()),
            maker.MadeUpDate(company_data.get('made_up_date', '')),
            maker.NextDueDate(company_data.get('next_due_date', '')),
            address,
            sic_codes
        )
        
        return ResponseBuilder.build_envelope(company_data_elem)
        
    @staticmethod
    def build_submission_response(submission_id: str):
        """Build a successful submission response"""
        maker = objectify.ElementMaker(annotate=False)
        
        # Simple acknowledgment - the submission ID was already in the request
        body = maker.SubmissionAcknowledgment(
            maker.SubmissionNumber(submission_id),
            maker.Status("accepted")
        )
        
        return ResponseBuilder.build_envelope(body)
        
    @staticmethod
    def build_status_response(submissions: List[Dict]):
        """Build a GetSubmissionStatus response"""
        ss_ns = "http://xmlgw.companieshouse.gov.uk"
        maker = objectify.ElementMaker(
            annotate=False,
            namespace=ss_ns,
            nsmap={None: ss_ns}
        )
        
        status_elem = maker.SubmissionStatus()
        
        for submission in submissions:
            status = maker.Status(
                maker.SubmissionNumber(submission['id']),
                maker.StatusCode(submission.get('status', 'pending'))
            )
            status_elem.append(status)
            
        return ResponseBuilder.build_envelope(status_elem)
        
    @staticmethod
    def build_accounts_image_response():
        """Build an AccountsImage response"""
        maker = objectify.ElementMaker(annotate=False)
        
        # Return a simple acknowledgment for now
        body = maker.AccountsImageResponse(
            maker.Status("generated"),
            maker.Message("Accounts image generated successfully")
        )
        
        return ResponseBuilder.build_envelope(body)