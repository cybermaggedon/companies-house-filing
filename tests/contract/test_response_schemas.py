import pytest
import json
from pathlib import Path
from lxml import etree

from ch_filing.state import State
from ch_filing.company_data import CompanyData
from ch_filing.form_submission import Accounts
from ch_filing.submission_status import SubmissionStatus
from ch_filing.envelope import Envelope


class TestResponseSchemas:
    """Contract tests to validate request XML against Companies House schemas"""
    
    @pytest.fixture
    def schema_dir(self):
        """Get the schema directory path"""
        return Path(__file__).parent.parent.parent / "schema"
    
    @pytest.fixture
    def test_state(self, tmp_path):
        """Create a test state with comprehensive configuration"""
        config_file = tmp_path / "contract_config.json"
        config_data = {
            "presenter-id": "CONTRACT_PRESENTER_123",
            "authentication": "CONTRACT_AUTH_456",
            "company-number": "12345678",
            "company-name": "CONTRACT TEST COMPANY LIMITED",
            "company-authentication-code": "CONTRACT1234",
            "company-type": "EW",
            "contact-name": "Contract Test Person",
            "contact-number": "07900 123456",
            "email": "contract@example.com",
            "made-up-date": "2023-12-31",
            "date-signed": "2024-01-15",
            "date": "2024-01-20",
            "package-reference": "CONTRACT001",
            "url": "https://xmlgw.companieshouse.gov.uk/v1-0/xmlgw/Gateway"
        }
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
            
        state_file = tmp_path / "contract_state.json"
        return State(str(config_file), str(state_file))
    
    @pytest.fixture
    def sample_accounts_data(self):
        """Sample iXBRL accounts data for testing"""
        return """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:ix="http://www.xbrl.org/2013/inlineXBRL">
<head>
    <title>Contract Test Company Limited - Annual Accounts</title>
    <meta charset="utf-8"/>
</head>
<body>
    <div>
        <h1>Contract Test Company Limited</h1>
        <h2>Annual Accounts for the year ended 31 December 2023</h2>
        
        <div class="balance-sheet">
            <h3>Balance Sheet as at 31 December 2023</h3>
            <table>
                <thead>
                    <tr>
                        <th>Item</th>
                        <th>Amount (£)</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>Total Assets</td>
                        <td><ix:nonFraction name="uk-bus:TotalAssets" 
                            contextRef="period" unitRef="GBP" decimals="0">100000</ix:nonFraction></td>
                    </tr>
                    <tr>
                        <td>Current Liabilities</td>
                        <td><ix:nonFraction name="uk-bus:CurrentLiabilities" 
                            contextRef="period" unitRef="GBP" decimals="0">20000</ix:nonFraction></td>
                    </tr>
                </tbody>
            </table>
        </div>
        
        <!-- XBRL contexts and units -->
        <ix:resources>
            <ix:context id="period">
                <ix:entity>
                    <ix:identifier scheme="http://www.companieshouse.gov.uk/">12345678</ix:identifier>
                </ix:entity>
                <ix:period>
                    <ix:startDate>2023-01-01</ix:startDate>
                    <ix:endDate>2023-12-31</ix:endDate>
                </ix:period>
            </ix:context>
            <ix:unit id="GBP">
                <ix:measure>iso4217:GBP</ix:measure>
            </ix:unit>
        </ix:resources>
    </div>
</body>
</html>"""
    
    def load_schema(self, schema_path):
        """Load and parse XSD schema file"""
        if not schema_path.exists():
            pytest.skip(f"Schema file not found: {schema_path}")
        
        try:
            schema_doc = etree.parse(str(schema_path))
            return etree.XMLSchema(schema_doc)
        except Exception as e:
            pytest.skip(f"Failed to load schema {schema_path}: {e}")
    
    def validate_xml_against_schema(self, xml_element, schema):
        """Validate XML element against schema"""
        xml_string = etree.tostring(xml_element, encoding='unicode')
        
        try:
            doc = etree.fromstring(xml_string.encode('utf-8'))
            is_valid = schema.validate(doc)
            
            if not is_valid:
                # Return validation errors for debugging
                return False, schema.error_log
            
            return True, None
        except Exception as e:
            return False, str(e)
    
    def test_company_data_request_schema_validation(self, test_state, schema_dir):
        """Test that CompanyDataRequest validates against CompanyData schema"""
        schema_path = schema_dir / "CompanyData-v3-4.xsd"
        schema = self.load_schema(schema_path)
        
        # Create CompanyDataRequest
        request = CompanyData.create_request(test_state)
        
        # Validate against schema
        is_valid, errors = self.validate_xml_against_schema(request, schema)
        
        if not is_valid:
            pytest.fail(f"CompanyDataRequest failed schema validation: {errors}")
    
    def test_form_submission_schema_validation(self, test_state, sample_accounts_data, schema_dir):
        """Test that FormSubmission validates against FormSubmission schema"""
        # Note: The actual schema file might have different name/location
        # This test structure shows how to validate form submissions
        schema_path = schema_dir / "FormSubmission-v2-11.xsd"
        
        if not schema_path.exists():
            pytest.skip(f"FormSubmission schema not found at {schema_path}")
        
        schema = self.load_schema(schema_path)
        
        # Create FormSubmission
        submission = Accounts.create_submission(test_state, "accounts.html", sample_accounts_data)
        
        # Validate against schema
        is_valid, errors = self.validate_xml_against_schema(submission, schema)
        
        if not is_valid:
            pytest.fail(f"FormSubmission failed schema validation: {errors}")
    
    def test_get_submission_status_schema_validation(self, test_state, schema_dir):
        """Test that GetSubmissionStatus validates against schema"""
        schema_path = schema_dir / "GetSubmissionStatus-v2-5.xsd"
        
        if not schema_path.exists():
            pytest.skip(f"GetSubmissionStatus schema not found at {schema_path}")
        
        schema = self.load_schema(schema_path)
        
        # Test with submission ID
        request_with_id = SubmissionStatus.create_request(test_state, "S00123")
        is_valid, errors = self.validate_xml_against_schema(request_with_id, schema)
        if not is_valid:
            pytest.fail(f"GetSubmissionStatus with ID failed schema validation: {errors}")
        
        # Test without submission ID
        request_without_id = SubmissionStatus.create_request(test_state)
        is_valid, errors = self.validate_xml_against_schema(request_without_id, schema)
        if not is_valid:
            pytest.fail(f"GetSubmissionStatus without ID failed schema validation: {errors}")
    
    def test_govtalk_envelope_structure_validation(self, test_state, schema_dir):
        """Test that GovTalk envelope structure follows expected format"""
        # This is more of a structural validation since GovTalk schema might not be available
        
        # Create a simple content for envelope
        content = CompanyData.create_request(test_state)
        envelope = Envelope.create(test_state, content, "CompanyDataRequest", "request")
        
        # Serialize and parse back to validate structure
        xml_string = etree.tostring(envelope, encoding='unicode')
        doc = etree.fromstring(xml_string.encode('utf-8'))
        
        # Validate basic GovTalk structure
        assert doc.tag.endswith("GovTalkMessage")
        
        # Check required elements exist
        envelope_version = doc.find(".//{http://www.govtalk.gov.uk/CM/envelope}EnvelopeVersion")
        header = doc.find(".//{http://www.govtalk.gov.uk/CM/envelope}Header")
        govtalk_details = doc.find(".//{http://www.govtalk.gov.uk/CM/envelope}GovTalkDetails")
        body = doc.find(".//{http://www.govtalk.gov.uk/CM/envelope}Body")
        
        assert envelope_version is not None
        assert header is not None
        assert govtalk_details is not None
        assert body is not None
        
        # Validate header structure
        message_details = header.find(".//{http://www.govtalk.gov.uk/CM/envelope}MessageDetails")
        assert message_details is not None
        
        # Check MessageDetails has required elements
        class_elem = message_details.find(".//{http://www.govtalk.gov.uk/CM/envelope}Class")
        qualifier = message_details.find(".//{http://www.govtalk.gov.uk/CM/envelope}Qualifier")
        transaction_id = message_details.find(".//{http://www.govtalk.gov.uk/CM/envelope}TransactionID")
        
        assert class_elem is not None
        assert qualifier is not None
        assert transaction_id is not None
        
        assert class_elem.text == "CompanyDataRequest"
        assert qualifier.text == "request"
    
    def test_xml_namespace_consistency(self, test_state, sample_accounts_data):
        """Test that all generated XML uses consistent namespaces"""
        
        # Test CompanyDataRequest namespace
        company_request = CompanyData.create_request(test_state)
        assert company_request.nsmap[None] == "http://xmlgw.companieshouse.gov.uk"
        
        # Test FormSubmission namespace
        form_submission = Accounts.create_submission(test_state, "accounts.html", sample_accounts_data)
        assert form_submission.nsmap[None] == "http://xmlgw.companieshouse.gov.uk/Header"
        
        # Test GetSubmissionStatus namespace
        status_request = SubmissionStatus.create_request(test_state, "S00123")
        assert status_request.nsmap[None] == "http://xmlgw.companieshouse.gov.uk"
        
        # Test GovTalk envelope namespace
        content = CompanyData.create_request(test_state)
        envelope = Envelope.create(test_state, content, "CompanyDataRequest", "request")
        assert envelope.nsmap[None] == "http://www.govtalk.gov.uk/CM/envelope"
    
    def test_schema_location_attributes(self, test_state, sample_accounts_data):
        """Test that schemaLocation attributes are correctly set"""
        
        # Test CompanyDataRequest schemaLocation
        company_request = CompanyData.create_request(test_state)
        xml_string = etree.tostring(company_request, encoding='unicode')
        assert 'CompanyData-v3-4.xsd' in xml_string
        assert 'schemaLocation' in xml_string
        
        # Test FormSubmission schemaLocation
        form_submission = Accounts.create_submission(test_state, "accounts.html", sample_accounts_data)
        xml_string = etree.tostring(form_submission, encoding='unicode')
        assert 'FormSubmission-v2-11.xsd' in xml_string
        assert 'schemaLocation' in xml_string
        
        # Test GetSubmissionStatus schemaLocation
        status_request = SubmissionStatus.create_request(test_state, "S00123")
        xml_string = etree.tostring(status_request, encoding='unicode')
        assert 'GetSubmissionStatus-v2-5.xsd' in xml_string
        assert 'schemaLocation' in xml_string
    
    def test_xml_well_formedness(self, test_state, sample_accounts_data):
        """Test that all generated XML is well-formed"""
        
        test_cases = [
            ("CompanyDataRequest", CompanyData.create_request(test_state)),
            ("FormSubmission", Accounts.create_submission(test_state, "accounts.html", sample_accounts_data)),
            ("GetSubmissionStatus", SubmissionStatus.create_request(test_state, "S00123")),
            ("GovTalkEnvelope", Envelope.create(test_state, CompanyData.create_request(test_state), "CompanyDataRequest", "request"))
        ]
        
        for name, xml_element in test_cases:
            # Test serialization
            xml_string = etree.tostring(xml_element, encoding='unicode')
            
            # Test parsing back
            try:
                parsed = etree.fromstring(xml_string.encode('utf-8'))
                assert parsed is not None
            except etree.XMLSyntaxError as e:
                pytest.fail(f"{name} XML is not well-formed: {e}")
    
    def test_required_fields_presence(self, test_state, sample_accounts_data):
        """Test that all required fields are present in generated XML"""
        
        # Test CompanyDataRequest required fields
        company_request = CompanyData.create_request(test_state)
        xml_string = etree.tostring(company_request, encoding='unicode')
        doc = etree.fromstring(xml_string.encode('utf-8'))
        
        # Check required CompanyData fields
        company_number = doc.find(".//{http://xmlgw.companieshouse.gov.uk}CompanyNumber")
        auth_code = doc.find(".//{http://xmlgw.companieshouse.gov.uk}CompanyAuthenticationCode")
        made_up_date = doc.find(".//{http://xmlgw.companieshouse.gov.uk}MadeUpDate")
        
        assert company_number is not None and company_number.text
        assert auth_code is not None and auth_code.text
        assert made_up_date is not None and made_up_date.text
        
        # Test FormSubmission required fields
        form_submission = Accounts.create_submission(test_state, "accounts.html", sample_accounts_data)
        xml_string = etree.tostring(form_submission, encoding='unicode')
        doc = etree.fromstring(xml_string.encode('utf-8'))
        
        # Check required FormSubmission fields
        form_header = doc.find(".//{http://xmlgw.companieshouse.gov.uk/Header}FormHeader")
        document = doc.find(".//{http://xmlgw.companieshouse.gov.uk/Header}Document")
        
        assert form_header is not None
        assert document is not None
        
        # Check FormHeader required fields
        company_number = form_header.find(".//{http://xmlgw.companieshouse.gov.uk/Header}CompanyNumber")
        submission_number = form_header.find(".//{http://xmlgw.companieshouse.gov.uk/Header}SubmissionNumber")
        form_identifier = form_header.find(".//{http://xmlgw.companieshouse.gov.uk/Header}FormIdentifier")
        
        assert company_number is not None and company_number.text
        assert submission_number is not None and submission_number.text
        assert form_identifier is not None and form_identifier.text == "Accounts"
    
    def test_data_types_and_formats(self, test_state):
        """Test that data types and formats conform to expected patterns"""
        
        # Test submission ID format
        status_request = SubmissionStatus.create_request(test_state, "S00123")
        xml_string = etree.tostring(status_request, encoding='unicode')
        doc = etree.fromstring(xml_string.encode('utf-8'))
        
        submission_number = doc.find(".//{http://xmlgw.companieshouse.gov.uk}SubmissionNumber")
        assert submission_number.text.startswith("S")
        assert len(submission_number.text) == 6  # S + 5 digits
        
        # Test company number format (8 digits)
        company_request = CompanyData.create_request(test_state)
        xml_string = etree.tostring(company_request, encoding='unicode')
        doc = etree.fromstring(xml_string.encode('utf-8'))
        
        company_number = doc.find(".//{http://xmlgw.companieshouse.gov.uk}CompanyNumber")
        assert company_number.text.isdigit()
        assert len(company_number.text) == 8
        
        # Test date format (YYYY-MM-DD)
        made_up_date = doc.find(".//{http://xmlgw.companieshouse.gov.uk}MadeUpDate")
        assert made_up_date.text == "2023-12-31"  # Expected format from test_state
        
        # Validate date format with regex
        import re
        date_pattern = r'^\d{4}-\d{2}-\d{2}$'
        assert re.match(date_pattern, made_up_date.text)
    
    def test_character_encoding_handling(self, tmp_path, sample_accounts_data):
        """Test that XML handles various character encodings correctly"""
        
        # Create state with unicode characters
        config_file = tmp_path / "unicode_config.json"
        config_data = {
            "presenter-id": "TËST_PRESENTER_123",
            "company-number": "12345678",
            "company-name": "TËST CÖMPÁÑY LÍMITÊD",
            "company-authentication-code": "ÃÜTH1234",
            "made-up-date": "2023-12-31"
        }
        
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False)
            
        state_file = tmp_path / "unicode_state.json"
        unicode_state = State(str(config_file), str(state_file))
        
        # Test that unicode characters are preserved in XML
        company_request = CompanyData.create_request(unicode_state)
        xml_string = etree.tostring(company_request, encoding='unicode')
        
        # Verify unicode characters are present
        assert "TËST CÖMPÁÑY LÍMITÊD" in xml_string or "ÃÜTH1234" in xml_string
        
        # Ensure XML is still parseable
        doc = etree.fromstring(xml_string.encode('utf-8'))
        assert doc is not None
    
    def test_schema_validation_error_reporting(self, test_state, schema_dir):
        """Test that schema validation provides useful error messages"""
        schema_path = schema_dir / "CompanyData-v3-4.xsd"
        
        if not schema_path.exists():
            pytest.skip(f"Schema file not found: {schema_path}")
        
        schema = self.load_schema(schema_path)
        
        # Create intentionally invalid XML by modifying valid request
        valid_request = CompanyData.create_request(test_state)
        xml_string = etree.tostring(valid_request, encoding='unicode')
        
        # Introduce an error (e.g., wrong namespace)
        invalid_xml = xml_string.replace(
            'xmlns="http://xmlgw.companieshouse.gov.uk"',
            'xmlns="http://invalid.namespace.com"'
        )
        
        try:
            doc = etree.fromstring(invalid_xml.encode('utf-8'))
            is_valid = schema.validate(doc)
            
            # Should not be valid
            assert not is_valid
            
            # Should have error messages
            assert len(schema.error_log) > 0
            
            # Error messages should be informative
            error_messages = [str(error) for error in schema.error_log]
            assert any("namespace" in msg.lower() for msg in error_messages)
            
        except Exception as e:
            # This is also acceptable - invalid XML should cause parsing errors
            assert "namespace" in str(e).lower() or "invalid" in str(e).lower()