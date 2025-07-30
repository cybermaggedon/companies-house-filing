import pytest
import json
import base64
from lxml import etree, objectify

from ch_filing.form_submission import Accounts
from ch_filing.state import State


class TestFormSubmission:
    """Test the Accounts class for creating FormSubmission XML"""
    
    @pytest.fixture
    def test_state(self, tmp_path):
        """Create a test state with all required fields for form submission"""
        config_file = tmp_path / "test_config.json"
        config_data = {
            "company-number": "12345678",
            "company-type": "EW",
            "company-name": "TEST COMPANY LIMITED",
            "company-authentication-code": "AUTH1234",
            "package-reference": "PKG001",
            "contact-name": "Test Contact Person",
            "contact-number": "07900 123456",
            "date-signed": "2024-01-15",
            "date": "2024-01-20"
        }
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
            
        state_file = tmp_path / "test_state.json"
        return State(str(config_file), str(state_file))
    
    @pytest.fixture
    def minimal_state(self, tmp_path):
        """Create state with minimal required fields"""
        config_file = tmp_path / "minimal_config.json"
        config_data = {
            "company-number": "87654321",
            "company-type": "SC",
            "company-name": "MINIMAL TEST LIMITED",
            "company-authentication-code": "MIN123",
            "package-reference": "MIN001",
            "contact-name": "Min Contact",
            "contact-number": "01234 567890",
            "date-signed": "2023-06-30",
            "date": "2023-07-05"
        }
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
            
        state_file = tmp_path / "minimal_state.json"
        return State(str(config_file), str(state_file))
    
    @pytest.fixture
    def sample_accounts_data(self):
        """Sample iXBRL accounts data for testing"""
        return """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:ix="http://www.xbrl.org/2013/inlineXBRL">
<head>
    <title>Test Company Limited - Annual Accounts</title>
    <meta charset="utf-8"/>
</head>
<body>
    <div>
        <h1>Test Company Limited</h1>
        <h2>Annual Accounts for the year ended 31 December 2023</h2>
        
        <div class="balance-sheet">
            <h3>Balance Sheet as at 31 December 2023</h3>
            <table>
                <tr>
                    <td>Total Assets</td>
                    <td><ix:nonFraction name="uk-bus:TotalAssets" 
                        contextRef="period" unitRef="GBP" decimals="0">100000</ix:nonFraction></td>
                </tr>
            </table>
        </div>
    </div>
</body>
</html>"""
    
    def test_create_submission_structure(self, test_state, sample_accounts_data):
        """Test that create_submission generates correct XML structure"""
        submission = Accounts.create_submission(test_state, "accounts.html", sample_accounts_data)
        
        # Check root element
        assert submission.tag.endswith("FormSubmission")
        
        # Check required elements exist
        assert hasattr(submission, 'FormHeader')
        assert hasattr(submission, 'DateSigned')
        assert hasattr(submission, 'Form')
        assert hasattr(submission, 'Document')
        
        # Check FormHeader structure
        header = submission.FormHeader
        assert hasattr(header, 'CompanyNumber')
        assert hasattr(header, 'CompanyType')
        assert hasattr(header, 'CompanyName')
        assert hasattr(header, 'CompanyAuthenticationCode')
        assert hasattr(header, 'PackageReference')
        assert hasattr(header, 'Language')
        assert hasattr(header, 'FormIdentifier')
        assert hasattr(header, 'SubmissionNumber')
        assert hasattr(header, 'ContactName')
        assert hasattr(header, 'ContactNumber')
        
        # Check Document structure
        document = submission.Document
        assert hasattr(document, 'Data')
        assert hasattr(document, 'Date')
        assert hasattr(document, 'Filename')
        assert hasattr(document, 'ContentType')
        assert hasattr(document, 'Category')
    
    def test_create_submission_content(self, test_state, sample_accounts_data):
        """Test that create_submission includes correct data from state"""
        submission = Accounts.create_submission(test_state, "test_accounts.html", sample_accounts_data)
        
        # Verify FormHeader content matches state configuration
        header = submission.FormHeader
        assert str(header.CompanyNumber) == "12345678"
        assert str(header.CompanyType) == "EW"
        assert str(header.CompanyName) == "TEST COMPANY LIMITED"
        assert str(header.CompanyAuthenticationCode) == "AUTH1234"
        assert str(header.PackageReference) == "PKG001"
        assert str(header.Language) == "EN"
        assert str(header.FormIdentifier) == "Accounts"
        assert str(header.ContactName) == "Test Contact Person"
        assert str(header.ContactNumber) == "07900 123456"
        
        # Check submission number is generated (format: S00001, S00002, etc.)
        submission_id = str(header.SubmissionNumber)
        assert submission_id.startswith("S")
        submission_num = int(submission_id[1:])  # Remove 'S' prefix
        assert submission_num > 0
        
        # Verify other fields
        assert str(submission.DateSigned) == "2024-01-15"
        assert str(submission.Document.Date) == "2024-01-20"
        assert str(submission.Document.Filename) == "test_accounts.html"
        assert str(submission.Document.ContentType) == "application/xml"
        assert str(submission.Document.Category) == "ACCOUNTS"
    
    def test_create_submission_namespace(self, test_state, sample_accounts_data):
        """Test that create_submission uses correct XML namespace"""
        submission = Accounts.create_submission(test_state, "accounts.html", sample_accounts_data)
        
        # Check namespace
        expected_ns = "http://xmlgw.companieshouse.gov.uk/Header"
        assert submission.nsmap[None] == expected_ns
        
        # Convert to string to check namespace in XML
        xml_string = etree.tostring(submission, encoding='unicode')
        assert f'xmlns="{expected_ns}"' in xml_string
    
    def test_create_submission_schema_location(self, test_state, sample_accounts_data):
        """Test that create_submission includes schema location"""
        submission = Accounts.create_submission(test_state, "accounts.html", sample_accounts_data)
        
        # Convert to string to check schema location
        xml_string = etree.tostring(submission, encoding='unicode')
        
        # Check schema location is set
        assert 'schemaLocation' in xml_string
        assert 'FormSubmission-v2-11.xsd' in xml_string
    
    def test_base64_encoding_of_accounts_data(self, test_state, sample_accounts_data):
        """Test that accounts data is properly base64 encoded"""
        submission = Accounts.create_submission(test_state, "accounts.html", sample_accounts_data)
        
        # Get the encoded data
        encoded_data = str(submission.Document.Data)
        
        # Verify it's valid base64
        try:
            decoded_data = base64.b64decode(encoded_data).decode('utf-8')
            assert decoded_data == sample_accounts_data
        except Exception as e:
            pytest.fail(f"Base64 decoding failed: {e}")
    
    def test_different_filenames(self, test_state, sample_accounts_data):
        """Test submission creation with different filenames"""
        test_cases = [
            "accounts.html",
            "annual_accounts_2023.html",
            "company_accounts.xhtml",
            "test-accounts.html",
            "micro_accounts.xml"
        ]
        
        for filename in test_cases:
            submission = Accounts.create_submission(test_state, filename, sample_accounts_data)
            assert str(submission.Document.Filename) == filename
    
    def test_different_company_types(self, tmp_path, sample_accounts_data):
        """Test submission creation with different company types"""
        test_cases = [
            ("EW", "Private Limited Company (England/Wales)"),
            ("SC", "Private Limited Company (Scotland)"),
            ("NI", "Private Limited Company (Northern Ireland)"),
            ("PLC", "Public Limited Company"),
        ]
        
        for company_type, description in test_cases:
            config_file = tmp_path / f"config_{company_type}.json"
            config_data = {
                "company-number": "12345678",
                "company-type": company_type,
                "company-name": f"TEST {company_type} COMPANY LIMITED",
                "company-authentication-code": "TEST123",
                "package-reference": "TEST001",
                "contact-name": "Test Contact",
                "contact-number": "01234 567890",
                "date-signed": "2024-01-15",
                "date": "2024-01-20"
            }
            
            with open(config_file, 'w') as f:
                json.dump(config_data, f)
                
            state_file = tmp_path / f"state_{company_type}.json"
            state = State(str(config_file), str(state_file))
            
            submission = Accounts.create_submission(state, "accounts.html", sample_accounts_data)
            assert str(submission.FormHeader.CompanyType) == company_type
    
    def test_different_contact_information(self, tmp_path, sample_accounts_data):
        """Test submission creation with different contact information"""
        test_cases = [
            ("John Smith", "07700 900123"),
            ("Sarah Johnson", "0161 234 5678"),
            ("David Brown", "+44 20 7946 0958"),
            ("Emma Wilson", "1234567890"),
        ]
        
        for contact_name, contact_number in test_cases:
            config_file = tmp_path / f"config_{contact_name.replace(' ', '_')}.json"
            config_data = {
                "company-number": "12345678",
                "company-type": "EW",
                "company-name": "TEST COMPANY LIMITED",
                "company-authentication-code": "TEST123",
                "package-reference": "TEST001",
                "contact-name": contact_name,
                "contact-number": contact_number,
                "date-signed": "2024-01-15",
                "date": "2024-01-20"
            }
            
            with open(config_file, 'w') as f:
                json.dump(config_data, f)
                
            state_file = tmp_path / f"state_{contact_name.replace(' ', '_')}.json"
            state = State(str(config_file), str(state_file))
            
            submission = Accounts.create_submission(state, "accounts.html", sample_accounts_data)
            assert str(submission.FormHeader.ContactName) == contact_name
            assert str(submission.FormHeader.ContactNumber) == contact_number
    
    def test_different_dates(self, tmp_path, sample_accounts_data):
        """Test submission creation with different date formats"""
        test_cases = [
            ("2023-12-31", "2024-01-31"),    # Year end and filing
            ("2022-03-31", "2022-09-30"),    # Q1 end
            ("2021-06-30", "2021-12-31"),    # Q2 end
            ("2020-09-30", "2021-03-31"),    # Q3 end
        ]
        
        for date_signed, filing_date in test_cases:
            config_file = tmp_path / f"config_{date_signed.replace('-', '_')}.json"
            config_data = {
                "company-number": "12345678",
                "company-type": "EW",
                "company-name": "TEST COMPANY LIMITED",
                "company-authentication-code": "TEST123",
                "package-reference": "TEST001",
                "contact-name": "Test Contact",
                "contact-number": "01234 567890",
                "date-signed": date_signed,
                "date": filing_date
            }
            
            with open(config_file, 'w') as f:
                json.dump(config_data, f)
                
            state_file = tmp_path / f"state_{date_signed.replace('-', '_')}.json"
            state = State(str(config_file), str(state_file))
            
            submission = Accounts.create_submission(state, "accounts.html", sample_accounts_data)
            assert str(submission.DateSigned) == date_signed
            assert str(submission.Document.Date) == filing_date
    
    def test_xml_serialization(self, test_state, sample_accounts_data):
        """Test that submission can be properly serialized to XML"""
        submission = Accounts.create_submission(test_state, "accounts.html", sample_accounts_data)
        
        # Test serialization doesn't raise exceptions
        xml_bytes = etree.tostring(submission)
        assert isinstance(xml_bytes, bytes)
        assert len(xml_bytes) > 0
        
        # Test with encoding
        xml_string = etree.tostring(submission, encoding='unicode')
        assert isinstance(xml_string, str)
        assert len(xml_string) > 0
        
        # Test pretty print
        xml_pretty = etree.tostring(submission, pretty_print=True, encoding='unicode')
        assert '\\n' in xml_pretty or '\n' in xml_pretty  # Has line breaks
    
    def test_xml_parsing_roundtrip(self, test_state, sample_accounts_data):
        """Test that generated XML can be parsed back"""
        submission = Accounts.create_submission(test_state, "accounts.html", sample_accounts_data)
        
        # Serialize to XML
        xml_string = etree.tostring(submission, encoding='unicode')
        
        # Parse back from XML
        parsed = objectify.fromstring(xml_string.encode('utf-8'))
        
        # Verify content is preserved
        assert str(parsed.FormHeader.CompanyNumber) == "12345678"
        assert str(parsed.FormHeader.CompanyType) == "EW"
        assert str(parsed.FormHeader.CompanyName) == "TEST COMPANY LIMITED"
        assert str(parsed.DateSigned) == "2024-01-15"
        assert str(parsed.Document.Category) == "ACCOUNTS"
    
    def test_xml_element_order(self, test_state, sample_accounts_data):
        """Test that XML elements appear in the expected order"""
        submission = Accounts.create_submission(test_state, "accounts.html", sample_accounts_data)
        
        # Parse XML to get proper child order
        xml_string = etree.tostring(submission, encoding='unicode')
        doc = etree.fromstring(xml_string.encode('utf-8'))
        
        # Get direct children of FormSubmission
        children = list(doc)
        child_tags = [child.tag.split('}')[-1] for child in children]  # Remove namespace
        
        # Check expected order based on XSD
        expected_order = ["FormHeader", "DateSigned", "Form", "Document"]
        assert child_tags == expected_order
    
    def test_xml_validation_structure(self, test_state, sample_accounts_data):
        """Test that XML structure matches expected schema requirements"""
        submission = Accounts.create_submission(test_state, "accounts.html", sample_accounts_data)
        xml_string = etree.tostring(submission, encoding='unicode')
        
        # Parse with lxml to validate structure
        doc = etree.fromstring(xml_string.encode('utf-8'))
        
        # Check root element name and namespace
        expected_ns = "http://xmlgw.companieshouse.gov.uk/Header"
        assert doc.tag == f"{{{expected_ns}}}FormSubmission"
        
        # Check required child elements exist
        form_header = doc.find(f".//{{{expected_ns}}}FormHeader")
        date_signed = doc.find(f".//{{{expected_ns}}}DateSigned")
        form_element = doc.find(f".//{{{expected_ns}}}Form")
        document = doc.find(f".//{{{expected_ns}}}Document")
        
        assert form_header is not None
        assert date_signed is not None
        assert form_element is not None
        assert document is not None
    
    def test_submission_number_increment(self, test_state, sample_accounts_data):
        """Test that submission numbers increment correctly"""
        submission1 = Accounts.create_submission(test_state, "accounts1.html", sample_accounts_data)
        submission2 = Accounts.create_submission(test_state, "accounts2.html", sample_accounts_data)
        submission3 = Accounts.create_submission(test_state, "accounts3.html", sample_accounts_data)
        
        # Extract numeric part from submission IDs (format: S00001, S00002, etc.)
        sub_id1 = str(submission1.FormHeader.SubmissionNumber)
        sub_id2 = str(submission2.FormHeader.SubmissionNumber)
        sub_id3 = str(submission3.FormHeader.SubmissionNumber)
        
        sub_num1 = int(sub_id1[1:])  # Remove 'S' prefix
        sub_num2 = int(sub_id2[1:])  # Remove 'S' prefix
        sub_num3 = int(sub_id3[1:])  # Remove 'S' prefix
        
        # Should increment by 1 each time
        assert sub_num2 == sub_num1 + 1
        assert sub_num3 == sub_num2 + 1
    
    def test_multiple_submissions_independence(self, test_state, minimal_state, sample_accounts_data):
        """Test that multiple submission creations are independent"""
        submission1 = Accounts.create_submission(test_state, "accounts1.html", sample_accounts_data)
        submission2 = Accounts.create_submission(minimal_state, "accounts2.html", sample_accounts_data)
        
        # Submissions should have different content
        assert str(submission1.FormHeader.CompanyNumber) != str(submission2.FormHeader.CompanyNumber)
        assert str(submission1.FormHeader.CompanyType) != str(submission2.FormHeader.CompanyType)
        assert str(submission1.FormHeader.CompanyName) != str(submission2.FormHeader.CompanyName)
        
        # Modifying one shouldn't affect the other
        submission1.FormHeader.CompanyNumber = "99999999"
        assert str(submission2.FormHeader.CompanyNumber) == "87654321"  # Unchanged
    
    def test_empty_accounts_data(self, test_state):
        """Test handling of empty accounts data"""
        empty_data = ""
        submission = Accounts.create_submission(test_state, "empty.html", empty_data)
        
        # Should still create submission with empty base64 data
        encoded_data = str(submission.Document.Data)
        decoded_data = base64.b64decode(encoded_data).decode('utf-8')
        assert decoded_data == ""
    
    def test_unicode_in_accounts_data(self, test_state):
        """Test handling of unicode characters in accounts data"""
        unicode_data = """<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>Test Compañy Ltd - Åccounts</title></head>
<body>
    <p>Company: Tëst Compañy Ltd</p>
    <p>Amount: £1,000,000</p>
    <p>Currency: €500,000</p>
</body>
</html>"""
        
        submission = Accounts.create_submission(test_state, "unicode.html", unicode_data)
        
        # Should handle unicode correctly
        encoded_data = str(submission.Document.Data)
        decoded_data = base64.b64decode(encoded_data).decode('utf-8')
        assert decoded_data == unicode_data
        assert "Compañy" in decoded_data
        assert "£" in decoded_data
        assert "€" in decoded_data
    
    def test_missing_config_keys(self, tmp_path, sample_accounts_data):
        """Test behavior when config keys are missing"""
        config_file = tmp_path / "incomplete_config.json"
        config_data = {
            "company-number": "12345678",
            "company-type": "EW"
            # Missing other required fields
        }
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
            
        state_file = tmp_path / "incomplete_state.json"
        state = State(str(config_file), str(state_file))
        
        # Should handle missing keys gracefully (return None from state.get())
        submission = Accounts.create_submission(state, "accounts.html", sample_accounts_data)
        
        assert str(submission.FormHeader.CompanyNumber) == "12345678"
        assert str(submission.FormHeader.CompanyType) == "EW"
        assert str(submission.FormHeader.CompanyName) == "None"  # str(None) = "None"
        assert str(submission.FormHeader.CompanyAuthenticationCode) == "None"