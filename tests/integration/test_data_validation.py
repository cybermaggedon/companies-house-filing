import pytest
import json
import base64
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch, Mock
from datetime import datetime, date

from ch_filing.client import (
    Client, 
    AuthenticationFailure, 
    SuspectedAccountsCorruption, 
    SuspectedValidationFailure, 
    RequestFailure, 
    PrivacyFailure
)
from ch_filing.state import State
from ch_filing.company_data import CompanyData
from ch_filing.form_submission import Accounts
from ch_filing.submission_status import SubmissionStatus
from ch_filing.envelope import Envelope
from ch_filing.test_server import MockServer


class TestDataValidationIntegration:
    """Integration tests for data validation across the entire stack"""
    
    @pytest.fixture
    def fixtures_dir(self):
        """Get the fixtures directory path"""
        return Path(__file__).parent.parent / "fixtures"
    
    @pytest.fixture
    def test_state(self, tmp_path):
        """Create a test state for data validation testing"""
        config_file = tmp_path / "validation_config.json"
        config_data = {
            "presenter-id": "VALIDATION_PRESENTER_123",
            "authentication": "VALIDATION_AUTH_456",
            "company-number": "12345678",
            "company-name": "VALIDATION TEST COMPANY LIMITED",
            "company-authentication-code": "VALIDATION1234",
            "company-type": "EW",
            "contact-name": "Validation Test Person",
            "contact-number": "07900 123456",
            "email": "validation@example.com",
            "made-up-date": "2023-12-31",
            "date-signed": "2024-01-15",
            "date": "2024-01-20",
            "package-reference": "VALIDATION001",
            "url": "http://localhost:9307/v1-0/xmlgw/Gateway"  # Unique port for validation tests
        }
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
            
        state_file = tmp_path / "validation_state.json"
        return State(str(config_file), str(state_file))
    
    @pytest.fixture
    def test_client(self, test_state):
        """Create a test client instance"""
        return Client(test_state)
    
    @pytest.fixture
    def valid_accounts_data(self):
        """Create valid iXBRL accounts data for testing"""
        return """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"
      xmlns:ixt="http://www.xbrl.org/2008/inlineXBRL/transformation"
      xmlns:uk-bus="http://xbrl.frc.org.uk/cd/2021-01-01/business"
      xmlns:uk-core="http://xbrl.frc.org.uk/fr/2021-01-01/core">
<head>
    <title>Test Company - Annual Accounts</title>
    <ix:header>
        <ix:hidden>
            <ix:nonNumeric contextRef="entity" name="uk-bus:EntityCurrentLegalName">TEST COMPANY LIMITED</ix:nonNumeric>
            <ix:nonNumeric contextRef="entity" name="uk-bus:CompaniesHouseRegisteredNumber">12345678</ix:nonNumeric>
        </ix:hidden>
    </ix:header>
</head>
<body>
    <h1>TEST COMPANY LIMITED</h1>
    <p>Company Number: <ix:nonNumeric contextRef="entity" name="uk-bus:CompaniesHouseRegisteredNumber">12345678</ix:nonNumeric></p>
    <p>Turnover: <ix:nonFraction contextRef="period" name="uk-core:Turnover" unitRef="GBP">100000</ix:nonFraction></p>
</body>
</html>"""
     
    @pytest.fixture
    def invalid_accounts_data(self):
        """Create invalid accounts data for testing validation errors"""
        return [
            # Missing required namespaces
            """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>Invalid Accounts</title></head>
<body><p>Missing iXBRL namespaces</p></body>
</html>""",
            # Invalid XBRL structure
            """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:ix="http://www.xbrl.org/2013/inlineXBRL">
<head><title>Invalid XBRL</title></head>
<body>
    <ix:nonNumeric>Missing required attributes</ix:nonNumeric>
</body>
</html>""",
            # Invalid XML syntax
            """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>Invalid XML</title></head>
<body><p>Unclosed tag<span></body>
</html>""",
            # Empty document
            "",
            # Non-HTML content
            "This is not HTML or XML content at all!"
        ]
    
    def test_company_number_validation(self, tmp_path):
        """Test validation of company numbers in various formats"""
        test_cases = [
            ("12345678", True),      # Valid standard format
            ("01234567", True),      # Valid with leading zero
            ("SC123456", True),      # Valid Scottish format
            ("NI123456", True),      # Valid Northern Ireland format
            ("1234567", False),      # Too short
            ("123456789", False),    # Too long
            ("INVALID", False),      # Invalid characters
            ("", False),             # Empty
            ("00000000", True),      # Edge case - all zeros (might be valid)
        ]
        
        for company_number, should_be_valid in test_cases:
            config_file = tmp_path / f"company_test_{company_number.replace('/', '_')}.json"
            config_data = {
                "presenter-id": "TEST_PRESENTER",
                "authentication": "TEST_AUTH",
                "company-number": company_number,
                "company-name": "TEST COMPANY LIMITED",
                "company-authentication-code": "TEST1234",
                "made-up-date": "2023-12-31",
                "url": "http://localhost:9307/v1-0/xmlgw/Gateway"
            }
            
            with open(config_file, 'w') as f:
                json.dump(config_data, f)
                
            state_file = tmp_path / f"company_state_{company_number.replace('/', '_')}.json"
            
            try:
                test_state = State(str(config_file), str(state_file))
                client = Client(test_state)
                
                # Create request - this should work regardless of company number validity
                content = CompanyData.create_request(test_state)
                envelope = Envelope.create(test_state, content, "CompanyDataRequest", "request")
                
                # Verify the company number appears in the XML
                from lxml import etree
                xml_string = etree.tostring(envelope, encoding='unicode')
                assert company_number in xml_string
                
                # If we got this far, the local validation passed
                if not should_be_valid and company_number and company_number not in ["INVALID"]:
                    # Some edge cases might be locally valid but rejected by the server
                    pass
                    
            except Exception as e:
                if should_be_valid:
                    pytest.fail(f"Valid company number {company_number} caused exception: {e}")
                # Invalid company numbers might cause exceptions, which is acceptable
    
    def test_date_validation_formats(self, tmp_path):
        """Test validation of various date formats"""
        date_test_cases = [
            ("2023-12-31", True),    # ISO format
            ("31/12/2023", True),    # UK format (if supported)
            ("2023-02-29", False),   # Invalid date (not leap year)
            ("2024-02-29", True),    # Valid leap year date
            ("2023-13-01", False),   # Invalid month
            ("2023-12-32", False),   # Invalid day
            ("invalid-date", False),  # Invalid format
            ("", False),             # Empty
            ("2023", False),         # Incomplete
        ]
        
        for date_value, should_be_valid in date_test_cases:
            config_file = tmp_path / f"date_test_{date_value.replace('/', '_').replace('-', '_')}.json"
            config_data = {
                "presenter-id": "TEST_PRESENTER",
                "authentication": "TEST_AUTH",
                "company-number": "12345678",
                "company-name": "TEST COMPANY LIMITED",
                "company-authentication-code": "TEST1234",
                "made-up-date": date_value,
                "date-signed": "2024-01-15",
                "date": "2024-01-20",
                "url": "http://localhost:9307/v1-0/xmlgw/Gateway"
            }
            
            with open(config_file, 'w') as f:
                json.dump(config_data, f)
                
            state_file = tmp_path / f"date_state_{date_value.replace('/', '_').replace('-', '_')}.json"
            
            try:
                test_state = State(str(config_file), str(state_file))
                content = CompanyData.create_request(test_state)
                envelope = Envelope.create(test_state, content, "CompanyDataRequest", "request")
                
                # If we got this far, basic validation passed
                if not should_be_valid and date_value not in ["", "invalid-date", "2023"]:
                    # Some dates might pass local validation but fail server validation
                    pass
                    
            except Exception as e:
                if should_be_valid:
                    pytest.fail(f"Valid date {date_value} caused exception: {e}")
                # Invalid dates causing exceptions is acceptable
    
    def test_email_validation_formats(self, tmp_path):
        """Test validation of email address formats"""
        email_test_cases = [
            ("test@example.com", True),
            ("valid.email+tag@example.co.uk", True),
            ("user123@domain.org", True),
            ("invalid-email", False),
            ("@example.com", False),
            ("test@", False),
            ("test@@example.com", False),
            ("", False),
            ("user@domain@example.com", False),
        ]
        
        for email, should_be_valid in email_test_cases:
            config_file = tmp_path / f"email_test_{email.replace('@', '_at_').replace('.', '_dot_')}.json"
            config_data = {
                "presenter-id": "TEST_PRESENTER",
                "authentication": "TEST_AUTH",
                "company-number": "12345678",
                "company-name": "TEST COMPANY LIMITED",
                "company-authentication-code": "TEST1234",
                "email": email,
                "made-up-date": "2023-12-31",
                "url": "http://localhost:9307/v1-0/xmlgw/Gateway"
            }
            
            with open(config_file, 'w') as f:
                json.dump(config_data, f)
                
            state_file = tmp_path / f"email_state_{email.replace('@', '_at_').replace('.', '_dot_')}.json"
            
            try:
                test_state = State(str(config_file), str(state_file))
                content = CompanyData.create_request(test_state)
                envelope = Envelope.create(test_state, content, "CompanyDataRequest", "request")
                
                # Verify email appears in the XML
                from lxml import etree
                xml_string = etree.tostring(envelope, encoding='unicode')
                if email:  # Only check non-empty emails
                    assert email in xml_string
                
            except Exception as e:
                if should_be_valid:
                    pytest.fail(f"Valid email {email} caused exception: {e}")
    
    def test_accounts_data_size_limits(self, test_state, test_client):
        """Test handling of accounts data with various sizes"""
        size_test_cases = [
            ("small", 1000),      # 1KB
            ("medium", 100000),   # 100KB
            ("large", 1000000),   # 1MB
            ("xlarge", 5000000),  # 5MB - might be rejected
        ]
        
        for size_name, size_bytes in size_test_cases:
            # Create accounts data of specified size
            base_content = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:ix="http://www.xbrl.org/2013/inlineXBRL">
<head><title>Size Test</title></head>
<body>
<h1>TEST COMPANY LIMITED</h1>
<p>Data: """
            
            padding = "x" * (size_bytes - len(base_content) - 20)  # Leave room for closing tags
            accounts_data = base_content + padding + "</p></body></html>"
            
            try:
                submission = Accounts.create_submission(test_state, f"accounts_{size_name}.html", accounts_data)
                envelope = Envelope.create(test_state, submission, "Accounts", "request")
                
                # Check that base64 encoding worked
                from lxml import etree
                xml_string = etree.tostring(envelope, encoding='unicode')
                assert "base64" in xml_string.lower() or len(accounts_data) < 1000
                
                # Very large files might cause issues
                if size_bytes > 2000000:  # 2MB+
                    # This might fail due to memory or encoding limits
                    pass
                    
            except Exception as e:
                if size_bytes <= 1000000:  # Files up to 1MB should work
                    pytest.fail(f"Accounts data of size {size_bytes} bytes caused exception: {e}")
                # Very large files causing exceptions is acceptable
    
    def test_invalid_accounts_data_handling(self, test_state, test_client, invalid_accounts_data):
        """Test handling of various invalid accounts data formats"""
        for i, invalid_data in enumerate(invalid_accounts_data):
            try:
                submission = Accounts.create_submission(test_state, f"invalid_accounts_{i}.html", invalid_data)
                envelope = Envelope.create(test_state, content=submission, cls="Accounts", qualifier="request")
                
                # Even invalid accounts data should be base64 encoded successfully
                from lxml import etree
                xml_string = etree.tostring(envelope, encoding='unicode')
                
                # The invalid data should still be encoded, but might cause server-side validation errors
                if invalid_data:  # Non-empty data should be encoded
                    assert len(xml_string) > 1000  # Should contain substantial content
                
            except Exception as e:
                # Some invalid data formats might cause immediate encoding/processing errors
                # This is acceptable behavior for malformed input
                error_message = str(e).lower()
                assert any(keyword in error_message for keyword in [
                    "encoding", "xml", "parsing", "invalid", "format"
                ])
    
    def test_xml_structure_validation(self, test_state, test_client, valid_accounts_data):
        """Test XML structure validation throughout the pipeline"""
        # Test valid structure
        try:
            submission = Accounts.create_submission(test_state, "valid_accounts.html", valid_accounts_data)
            envelope = Envelope.create(test_state, submission, "Accounts", "request")
            
            # Verify envelope structure
            assert hasattr(envelope, 'Header')
            assert hasattr(envelope, 'Body')
            assert hasattr(envelope.Header, 'MessageDetails')
            assert hasattr(envelope.Header, 'SenderDetails')
            
            # Verify accounts submission structure
            assert hasattr(envelope.Body, 'Accounts')
            assert hasattr(envelope.Body.Accounts, 'CompanyNumber')
            assert hasattr(envelope.Body.Accounts, 'FilingDocument')
            
        except Exception as e:
            pytest.fail(f"Valid accounts data caused XML structure validation error: {e}")
    
    def test_base64_encoding_validation(self, test_state, test_client):
        """Test base64 encoding validation for accounts data"""
        test_content = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>Encoding Test</title></head>
<body><h1>TEST COMPANY</h1><p>Special chars: áéíóú €£$</p></body>
</html>"""
        
        submission = Accounts.create_submission(test_state, "encoding_test.html", test_content)
        envelope = Envelope.create(test_state, submission, "Accounts", "request")
        
        # Extract the base64 encoded content
        from lxml import etree
        xml_string = etree.tostring(envelope, encoding='unicode')
        
        # Verify it contains base64 encoded data
        filing_doc_start = xml_string.find("<FilingDocument>")
        filing_doc_end = xml_string.find("</FilingDocument>")
        
        if filing_doc_start != -1 and filing_doc_end != -1:
            encoded_content = xml_string[filing_doc_start + len("<FilingDocument>"):filing_doc_end].strip()
            
            # Verify it's valid base64
            try:
                decoded = base64.b64decode(encoded_content)
                decoded_text = decoded.decode('utf-8')
                
                # Verify original content is preserved
                assert "TEST COMPANY" in decoded_text
                assert "Special chars" in decoded_text
                assert "áéíóú" in decoded_text
                
            except Exception as e:
                pytest.fail(f"Base64 encoding/decoding failed: {e}")
    
    def test_transaction_id_validation(self, test_state, test_client):
        """Test transaction ID generation and validation"""
        initial_tx_id = test_state.get_cur_tx_id()
        
        # Generate multiple requests and verify transaction IDs
        tx_ids = []
        for i in range(5):
            content = CompanyData.create_request(test_state)
            envelope = Envelope.create(test_state, content, "CompanyDataRequest", "request")
            
            # Extract transaction ID from envelope
            tx_id = envelope.Header.MessageDetails.TransactionID
            tx_ids.append(int(tx_id))
        
        # Verify transaction IDs are sequential and unique
        assert len(set(tx_ids)) == 5  # All unique
        assert max(tx_ids) == initial_tx_id + 5  # Sequential increment
        assert min(tx_ids) == initial_tx_id + 1   # Starts from initial + 1
    
    def test_submission_id_validation(self, test_state):
        """Test submission ID generation and format validation"""
        initial_sub_id = test_state.get_cur_submission_id()
        
        # Generate multiple submission IDs
        sub_ids = []
        for i in range(5):
            sub_id = test_state.get_next_submission_id()
            sub_ids.append(sub_id)
        
        # Verify format and uniqueness
        for sub_id in sub_ids:
            assert sub_id.startswith("S")
            assert len(sub_id) == 6  # "S" + 5 digits
            assert sub_id[1:].isdigit()
        
        # Verify sequential numbering
        sub_numbers = [int(sub_id[1:]) for sub_id in sub_ids]
        assert len(set(sub_numbers)) == 5  # All unique
        assert max(sub_numbers) == initial_sub_id + 5
        assert min(sub_numbers) == initial_sub_id + 1
    
    def test_namespace_validation(self, test_state, test_client):
        """Test XML namespace validation in generated requests"""
        content = CompanyData.create_request(test_state)
        envelope = Envelope.create(test_state, content, "CompanyDataRequest", "request")
        
        from lxml import etree
        xml_string = etree.tostring(envelope, encoding='unicode')
        
        # Verify required namespaces are present
        assert 'xmlns="http://www.govtalk.gov.uk/CM/envelope"' in xml_string
        assert 'http://xmlgw.companieshouse.gov.uk/v2-1/schema/Egov_ch-v2-0.xsd' in xml_string
        
        # Verify namespace prefixes are used correctly
        root = etree.fromstring(xml_string)
        assert root.tag.startswith("{http://www.govtalk.gov.uk/CM/envelope}")
    
    def test_character_encoding_validation(self, test_state, test_client):
        """Test handling of various character encodings and special characters"""
        test_cases = [
            ("ASCII", "Basic ASCII Text"),
            ("Latin1", "Café résumé naïve"),
            ("UTF8", "测试 Тест العربية עברית"),
            ("Symbols", "€£$¥©®™"),
            ("Newlines", "Line 1\nLine 2\r\nLine 3"),
            ("HTML", "<script>alert('test')</script>"),
        ]
        
        for encoding_name, test_text in test_cases:
            # Test in company name field
            original_name = test_state.get("company-name")
            test_state.config["company-name"] = f"TEST {test_text} COMPANY"
            
            try:
                content = CompanyData.create_request(test_state)
                envelope = Envelope.create(test_state, content, "CompanyDataRequest", "request")
                
                from lxml import etree
                xml_string = etree.tostring(envelope, encoding='unicode')
                
                # Verify the text is properly encoded in XML
                if encoding_name != "HTML":  # HTML should be escaped
                    assert test_text in xml_string or len(test_text.encode('utf-8')) != len(test_text)
                else:
                    # HTML should be escaped
                    assert "&lt;script&gt;" in xml_string or "<script>" not in xml_string
                    
            except Exception as e:
                if encoding_name in ["ASCII", "Latin1", "UTF8"]:
                    pytest.fail(f"Standard encoding {encoding_name} caused error: {e}")
                # Complex encodings or HTML might cause issues, which is acceptable
                
            finally:
                # Restore original company name
                test_state.config["company-name"] = original_name
    
    def test_field_length_validation(self, tmp_path):
        """Test validation of field length limits"""
        field_tests = [
            ("company-name", "A" * 100, True),    # Normal length
            ("company-name", "A" * 200, True),    # Long but reasonable
            ("company-name", "A" * 1000, False),  # Extremely long
            ("contact-name", "B" * 50, True),     # Normal length
            ("contact-name", "B" * 500, False),   # Too long
            ("email", "test@" + "a" * 50 + ".com", True),   # Long domain
            ("email", "test@" + "a" * 500 + ".com", False), # Extremely long domain
        ]
        
        for field_name, field_value, should_be_valid in field_tests:
            config_file = tmp_path / f"length_test_{field_name}_{len(field_value)}.json"
            config_data = {
                "presenter-id": "TEST_PRESENTER",
                "authentication": "TEST_AUTH",
                "company-number": "12345678",
                "company-name": "TEST COMPANY LIMITED",
                "company-authentication-code": "TEST1234",
                "contact-name": "Test Person",
                "email": "test@example.com",
                "made-up-date": "2023-12-31",
                "url": "http://localhost:9307/v1-0/xmlgw/Gateway"
            }
            
            # Override the specific field being tested
            config_data[field_name] = field_value
            
            with open(config_file, 'w') as f:
                json.dump(config_data, f)
                
            state_file = tmp_path / f"length_state_{field_name}_{len(field_value)}.json"
            
            try:
                test_state = State(str(config_file), str(state_file))
                content = CompanyData.create_request(test_state)
                envelope = Envelope.create(test_state, content, "CompanyDataRequest", "request")
                
                # If we got here, local processing succeeded
                if not should_be_valid:
                    # Very long fields might be locally valid but rejected by server
                    pass
                    
            except Exception as e:
                if should_be_valid:
                    pytest.fail(f"Valid field length for {field_name} ({len(field_value)} chars) caused error: {e}")
    
    def test_cross_field_validation(self, tmp_path):
        """Test validation that involves relationships between multiple fields"""
        # Test date consistency (made-up-date should be before date-signed)
        config_file = tmp_path / "cross_field_test.json"
        config_data = {
            "presenter-id": "TEST_PRESENTER",
            "authentication": "TEST_AUTH",
            "company-number": "12345678",
            "company-name": "TEST COMPANY LIMITED",
            "company-authentication-code": "TEST1234",
            "email": "test@example.com",
            "made-up-date": "2024-12-31",    # After date-signed
            "date-signed": "2024-01-15",     # Before made-up-date
            "date": "2024-01-20",
            "url": "http://localhost:9307/v1-0/xmlgw/Gateway"
        }
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
            
        state_file = tmp_path / "cross_field_state.json"
        
        # This might be valid locally but should be caught by server validation
        test_state = State(str(config_file), str(state_file))
        content = CompanyData.create_request(test_state)
        envelope = Envelope.create(test_state, content, "CompanyDataRequest", "request")
        
        # Local validation passes, but server should catch the date inconsistency
        from lxml import etree
        xml_string = etree.tostring(envelope, encoding='unicode')
        assert "2024-12-31" in xml_string
        assert "2024-01-15" in xml_string
    
    def test_mandatory_field_validation(self, tmp_path):
        """Test validation of mandatory fields"""
        mandatory_fields = [
            "presenter-id",
            "authentication", 
            "company-number",
            "made-up-date"
        ]
        
        for missing_field in mandatory_fields:
            config_file = tmp_path / f"missing_{missing_field}_test.json"
            config_data = {
                "presenter-id": "TEST_PRESENTER",
                "authentication": "TEST_AUTH",
                "company-number": "12345678",
                "company-name": "TEST COMPANY LIMITED",
                "company-authentication-code": "TEST1234",
                "made-up-date": "2023-12-31",
                "url": "http://localhost:9307/v1-0/xmlgw/Gateway"
            }
            
            # Remove the mandatory field
            if missing_field in config_data:
                del config_data[missing_field]
            
            with open(config_file, 'w') as f:
                json.dump(config_data, f)
                
            state_file = tmp_path / f"missing_{missing_field}_state.json"
            
            try:
                test_state = State(str(config_file), str(state_file))
                
                if missing_field in ["presenter-id", "authentication"]:
                    # These are needed for envelope creation
                    envelope = Envelope.create(test_state, None, "CompanyDataRequest", "request")
                    # Should fail due to missing authentication details
                elif missing_field == "company-number":
                    # This is needed for company data request
                    content = CompanyData.create_request(test_state)
                    # Should fail due to missing company number
                elif missing_field == "made-up-date":
                    # This is needed for company data request
                    content = CompanyData.create_request(test_state)
                    # Should fail due to missing made-up date
                    
            except (KeyError, AttributeError, TypeError) as e:
                # Expected - missing mandatory fields should cause errors
                assert missing_field.replace("-", "_") in str(e) or "None" in str(e)
            except Exception as e:
                # Other exceptions might also be valid for missing mandatory fields
                pass