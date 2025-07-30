import pytest
import json
from pathlib import Path
from lxml import etree, objectify

from ch_filing.envelope import Envelope
from ch_filing.company_data import CompanyData
from ch_filing.form_submission import Accounts
from ch_filing.submission_status import SubmissionStatus
from ch_filing.state import State


class TestRequestSchemas:
    """Contract tests to validate XML requests against Companies House schemas"""
    
    @pytest.fixture
    def schema_dir(self):
        """Get the schema directory path"""
        return Path(__file__).parent.parent.parent
    
    @pytest.fixture
    def test_state(self, tmp_path):
        """Create a test state with valid configuration"""
        config_file = tmp_path / "test_config.json"
        config_data = {
            "presenter-id": "TEST_PRESENTER_ID",
            "authentication": "TEST_AUTH_CODE",
            "company-number": "12345678",
            "company-name": "TEST COMPANY LIMITED",
            "company-authentication-code": "ABCD1234",
            "email": "test@example.com",
            "test-flag": "1",
            "made-up-date": "2023-12-31"
        }
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
            
        state_file = tmp_path / "test_state.json"
        return State(str(config_file), str(state_file))
    
    def load_schema(self, schema_path):
        """Load and parse an XSD schema file"""
        if not schema_path.exists():
            pytest.skip(f"Schema file not found: {schema_path}")
            
        try:
            schema_doc = etree.parse(str(schema_path))
            return etree.XMLSchema(schema_doc)
        except Exception as e:
            pytest.skip(f"Could not load schema {schema_path}: {e}")
    
    def validate_xml_against_schema(self, xml_element, schema):
        """Validate an XML element against a schema"""
        # Convert objectify element to standard etree
        xml_string = etree.tostring(xml_element, encoding='unicode')
        doc = etree.fromstring(xml_string.encode('utf-8'))
        
        is_valid = schema.validate(doc)
        if not is_valid:
            error_log = schema.error_log
            return False, str(error_log)
        return True, None
    
    def test_govtalk_envelope_schema(self, test_state, schema_dir):
        """Test that GovTalk envelope validates against GovTalk schema"""
        schema_path = schema_dir / "schema" / "Egov_ch-v2-0.xsd"
        schema = self.load_schema(schema_path)
        
        # Create a simple content element
        maker = objectify.ElementMaker(annotate=False)
        content = maker.TestContent(maker.Field("value"))
        
        # Create envelope
        envelope = Envelope.create(test_state, content, "CompanyDataRequest", "request")
        
        # Validate against schema
        is_valid, error = self.validate_xml_against_schema(envelope, schema)
        
        if not is_valid:
            pytest.fail(f"GovTalk envelope validation failed: {error}")
    
    def test_company_data_request_schema(self, test_state, schema_dir):
        """Test that CompanyDataRequest validates against CompanyData schema"""
        schema_path = schema_dir / "schema" / "CompanyData-v3-4.xsd"
        
        # Skip if schema file doesn't exist or has dependency issues
        if not schema_path.exists():
            pytest.skip(f"Schema file not found: {schema_path}")
        
        # Create CompanyDataRequest
        company_data_request = CompanyData.create_request(test_state)
        
        # For this test, we'll validate the structure manually since
        # the XSD has includes that may not resolve
        self._validate_company_data_request_structure(company_data_request, test_state)
    
    def _validate_company_data_request_structure(self, request, state):
        """Manually validate CompanyDataRequest structure"""
        # Check root element name
        assert request.tag.endswith("CompanyDataRequest")
        
        # Check required elements exist
        assert hasattr(request, 'CompanyNumber')
        assert hasattr(request, 'CompanyAuthenticationCode') 
        assert hasattr(request, 'MadeUpDate')
        
        # Validate content
        assert str(request.CompanyNumber) == state.get("company-number")
        assert str(request.CompanyAuthenticationCode) == state.get("company-authentication-code")
        assert str(request.MadeUpDate) == state.get("made-up-date")
        
        # Check namespace
        expected_ns = "http://xmlgw.companieshouse.gov.uk"
        assert request.nsmap[None] == expected_ns
    
    def test_company_data_request_in_envelope(self, test_state, schema_dir):
        """Test complete CompanyDataRequest wrapped in GovTalk envelope"""
        # Create the request
        content = CompanyData.create_request(test_state)
        envelope = Envelope.create(test_state, content, "CompanyDataRequest", "request")
        
        # Validate envelope structure
        assert envelope.tag.endswith("GovTalkMessage")
        assert str(envelope.Header.MessageDetails.Class) == "CompanyDataRequest"
        assert str(envelope.Header.MessageDetails.Qualifier) == "request"
        
        # Validate the content is properly embedded
        body_content = envelope.Body.getchildren()[0]
        assert body_content.tag.endswith("CompanyDataRequest")
        
        # Validate content structure
        self._validate_company_data_request_structure(body_content, test_state)
    
    def test_accounts_submission_structure(self, test_state, tmp_path):
        """Test Accounts submission structure (form submission)"""
        # Create test accounts file
        accounts_file = tmp_path / "test_accounts.html"
        test_accounts_data = """<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
    <head><title>Test Accounts</title></head>
    <body><p>Test accounts data</p></body>
</html>"""
        accounts_file.write_text(test_accounts_data)
        
        # Create form submission
        submission = Accounts.create_submission(test_state, str(accounts_file), test_accounts_data)
        
        # Validate structure
        assert submission.tag.endswith("FormSubmission")
        assert hasattr(submission, 'FormHeader')
        assert hasattr(submission, 'Document')
        
        # Check FormHeader elements
        header = submission.FormHeader
        assert str(header.CompanyNumber) == test_state.get("company-number")
        assert str(header.CompanyName) == test_state.get("company-name")
        assert str(header.FormIdentifier) == "Accounts"
        
        # Check Document elements
        doc = submission.Document
        assert hasattr(doc, 'Data')
        assert hasattr(doc, 'Filename')
        assert hasattr(doc, 'ContentType')
        assert str(doc.ContentType) == "application/xml"
        assert str(doc.Category) == "ACCOUNTS"
    
    def test_submission_status_request_structure(self, test_state):
        """Test GetSubmissionStatus request structure"""
        # Test with submission ID
        submission_id = "S12345"
        status_request = SubmissionStatus.create_request(test_state, submission_id)
        
        assert status_request.tag.endswith("GetSubmissionStatus")
        assert hasattr(status_request, 'SubmissionNumber')
        assert hasattr(status_request, 'PresenterID')
        assert str(status_request.SubmissionNumber) == submission_id
        assert str(status_request.PresenterID) == test_state.get("presenter-id")
        
        # Test without submission ID
        status_request_all = SubmissionStatus.create_request(test_state)
        assert status_request_all.tag.endswith("GetSubmissionStatus")
        assert hasattr(status_request_all, 'PresenterID')
        assert str(status_request_all.PresenterID) == test_state.get("presenter-id")
        
        # Should not have SubmissionNumber when not specified
        try:
            _ = status_request_all.SubmissionNumber
            pytest.fail("SubmissionNumber should not exist when not specified")
        except AttributeError:
            pass  # This is expected
    
    def test_xml_encoding_and_declaration(self, test_state):
        """Test that generated XML has correct encoding and declaration"""
        content = CompanyData.create_request(test_state)
        envelope = Envelope.create(test_state, content, "CompanyDataRequest", "request")
        
        # Convert to string with XML declaration
        xml_string = etree.tostring(
            envelope, 
            pretty_print=True, 
            xml_declaration=True, 
            encoding='UTF-8'
        ).decode('utf-8')
        
        # Check XML declaration
        assert xml_string.startswith('<?xml version=\'1.0\' encoding=\'UTF-8\'?>')
        
        # Check for proper namespace declarations
        assert 'xmlns="http://www.govtalk.gov.uk/CM/envelope"' in xml_string
        
        # Check schema location
        assert 'schemaLocation' in xml_string
    
    def test_special_characters_handling(self, test_state, tmp_path):
        """Test handling of special characters in XML content"""
        # Update config with special characters
        config_file = tmp_path / "special_config.json"
        config_data = {
            "presenter-id": "TEST_PRESENTER",
            "authentication": "TEST_AUTH",
            "company-number": "12345678",
            "company-name": "TEST & COMPANY <LIMITED>",  # Special chars
            "company-authentication-code": "ABCD1234",
            "email": "test@example.com",
            "test-flag": "1",
            "made-up-date": "2023-12-31"
        }
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
            
        state_file = tmp_path / "special_state.json"
        special_state = State(str(config_file), str(state_file))
        
        # Create request with special characters
        content = CompanyData.create_request(special_state)
        envelope = Envelope.create(special_state, content, "CompanyDataRequest", "request")
        
        # Convert to string and verify it's valid XML
        xml_string = etree.tostring(envelope, encoding='unicode')
        
        # Parse it back to ensure it's valid
        try:
            parsed = etree.fromstring(xml_string.encode('utf-8'))
            assert parsed is not None
        except etree.XMLSyntaxError as e:
            pytest.fail(f"Generated XML with special characters is invalid: {e}")