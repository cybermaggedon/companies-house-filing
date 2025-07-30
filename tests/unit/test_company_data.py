import pytest
import json
from lxml import etree, objectify

from ch_filing.company_data import CompanyData
from ch_filing.state import State


class TestCompanyData:
    """Test the CompanyData class for creating CompanyDataRequest XML"""
    
    @pytest.fixture
    def test_state(self, tmp_path):
        """Create a test state with company data configuration"""
        config_file = tmp_path / "test_config.json"
        config_data = {
            "company-number": "12345678",
            "company-authentication-code": "AUTH1234",
            "made-up-date": "2023-12-31"
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
            "company-authentication-code": "MINIMAL123",
            "made-up-date": "2022-03-31"
        }
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
            
        state_file = tmp_path / "minimal_state.json"
        return State(str(config_file), str(state_file))
    
    def test_create_request_structure(self, test_state):
        """Test that create_request generates correct XML structure"""
        request = CompanyData.create_request(test_state)
        
        # Check root element
        assert request.tag.endswith("CompanyDataRequest")
        
        # Check required elements exist
        assert hasattr(request, 'CompanyNumber')
        assert hasattr(request, 'CompanyAuthenticationCode')
        assert hasattr(request, 'MadeUpDate')
    
    def test_create_request_content(self, test_state):
        """Test that create_request includes correct data from state"""
        request = CompanyData.create_request(test_state)
        
        # Verify content matches state configuration
        assert str(request.CompanyNumber) == "12345678"
        assert str(request.CompanyAuthenticationCode) == "AUTH1234"
        assert str(request.MadeUpDate) == "2023-12-31"
    
    def test_create_request_namespace(self, test_state):
        """Test that create_request uses correct XML namespace"""
        request = CompanyData.create_request(test_state)
        
        # Check namespace
        expected_ns = "http://xmlgw.companieshouse.gov.uk"
        assert request.nsmap[None] == expected_ns
        
        # Convert to string to check namespace in XML
        xml_string = etree.tostring(request, encoding='unicode')
        assert f'xmlns="{expected_ns}"' in xml_string
    
    def test_create_request_schema_location(self, test_state):
        """Test that create_request includes schema location"""
        request = CompanyData.create_request(test_state)
        
        # Convert to string to check schema location
        xml_string = etree.tostring(request, encoding='unicode')
        
        # Check schema location is set
        assert 'schemaLocation' in xml_string
        assert 'CompanyData-v3-4.xsd' in xml_string
    
    def test_create_request_different_company_numbers(self, tmp_path):
        """Test request creation with different company number formats"""
        test_cases = [
            "12345678",     # 8 digits
            "01234567",     # With leading zero
            "87654321",     # Different number
            "00000001",     # Minimum value with zeros
        ]
        
        for company_number in test_cases:
            config_file = tmp_path / f"config_{company_number}.json"
            config_data = {
                "company-number": company_number,
                "company-authentication-code": "TEST123",
                "made-up-date": "2023-12-31"
            }
            
            with open(config_file, 'w') as f:
                json.dump(config_data, f)
                
            state_file = tmp_path / f"state_{company_number}.json"
            state = State(str(config_file), str(state_file))
            
            request = CompanyData.create_request(state)
            assert str(request.CompanyNumber) == company_number
    
    def test_create_request_different_auth_codes(self, tmp_path):
        """Test request creation with different authentication codes"""
        test_cases = [
            "AUTH1234",
            "ABCD5678",
            "TEST9999",
            "XYZ12345",
        ]
        
        for auth_code in test_cases:
            config_file = tmp_path / f"config_{auth_code}.json"
            config_data = {
                "company-number": "12345678",
                "company-authentication-code": auth_code,
                "made-up-date": "2023-12-31"
            }
            
            with open(config_file, 'w') as f:
                json.dump(config_data, f)
                
            state_file = tmp_path / f"state_{auth_code}.json"
            state = State(str(config_file), str(state_file))
            
            request = CompanyData.create_request(state)
            assert str(request.CompanyAuthenticationCode) == auth_code
    
    def test_create_request_different_dates(self, tmp_path):
        """Test request creation with different made-up dates"""
        test_cases = [
            "2023-12-31",   # End of year
            "2023-03-31",   # End of Q1
            "2022-06-30",   # End of Q2
            "2021-09-30",   # End of Q3
            "2020-01-31",   # End of January
        ]
        
        for made_up_date in test_cases:
            config_file = tmp_path / f"config_{made_up_date.replace('-', '_')}.json"
            config_data = {
                "company-number": "12345678",
                "company-authentication-code": "TEST123",
                "made-up-date": made_up_date
            }
            
            with open(config_file, 'w') as f:
                json.dump(config_data, f)
                
            state_file = tmp_path / f"state_{made_up_date.replace('-', '_')}.json"
            state = State(str(config_file), str(state_file))
            
            request = CompanyData.create_request(state)
            assert str(request.MadeUpDate) == made_up_date
    
    def test_xml_serialization(self, test_state):
        """Test that request can be properly serialized to XML"""
        request = CompanyData.create_request(test_state)
        
        # Test serialization doesn't raise exceptions
        xml_bytes = etree.tostring(request)
        assert isinstance(xml_bytes, bytes)
        assert len(xml_bytes) > 0
        
        # Test with encoding
        xml_string = etree.tostring(request, encoding='unicode')
        assert isinstance(xml_string, str)
        assert len(xml_string) > 0
        
        # Test pretty print
        xml_pretty = etree.tostring(request, pretty_print=True, encoding='unicode')
        assert '\\n' in xml_pretty or '\n' in xml_pretty  # Has line breaks
    
    def test_xml_parsing_roundtrip(self, test_state):
        """Test that generated XML can be parsed back"""
        request = CompanyData.create_request(test_state)
        
        # Serialize to XML
        xml_string = etree.tostring(request, encoding='unicode')
        
        # Parse back from XML
        parsed = objectify.fromstring(xml_string.encode('utf-8'))
        
        # Verify content is preserved
        assert str(parsed.CompanyNumber) == "12345678"
        assert str(parsed.CompanyAuthenticationCode) == "AUTH1234"
        assert str(parsed.MadeUpDate) == "2023-12-31"
    
    def test_xml_element_order(self, test_state):
        """Test that XML elements appear in the expected order"""
        request = CompanyData.create_request(test_state)
        
        # Get child elements in order
        children = list(request)
        child_tags = [child.tag.split('}')[-1] for child in children]  # Remove namespace
        
        # Check expected order based on XSD
        expected_order = ["CompanyNumber", "CompanyAuthenticationCode", "MadeUpDate"]
        assert child_tags == expected_order
    
    def test_xml_validation_structure(self, test_state):
        """Test that XML structure matches expected schema requirements"""
        request = CompanyData.create_request(test_state)
        xml_string = etree.tostring(request, encoding='unicode')
        
        # Parse with lxml to validate structure
        doc = etree.fromstring(xml_string.encode('utf-8'))
        
        # Check root element name and namespace
        assert doc.tag == "{http://xmlgw.companieshouse.gov.uk}CompanyDataRequest"
        
        # Check required child elements exist
        company_number = doc.find(".//{http://xmlgw.companieshouse.gov.uk}CompanyNumber")
        auth_code = doc.find(".//{http://xmlgw.companieshouse.gov.uk}CompanyAuthenticationCode")
        made_up_date = doc.find(".//{http://xmlgw.companieshouse.gov.uk}MadeUpDate")
        
        assert company_number is not None
        assert auth_code is not None
        assert made_up_date is not None
    
    def test_empty_values_handling(self, tmp_path):
        """Test handling of empty or None values"""
        config_file = tmp_path / "empty_config.json"
        config_data = {
            "company-number": "",
            "company-authentication-code": "",
            "made-up-date": ""
        }
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
            
        state_file = tmp_path / "empty_state.json"
        state = State(str(config_file), str(state_file))
        
        # Should still create request even with empty values
        request = CompanyData.create_request(state)
        
        assert str(request.CompanyNumber) == ""
        assert str(request.CompanyAuthenticationCode) == ""
        assert str(request.MadeUpDate) == ""
    
    def test_missing_config_keys(self, tmp_path):
        """Test behavior when config keys are missing"""
        config_file = tmp_path / "incomplete_config.json"
        config_data = {
            "company-number": "12345678"
            # Missing company-authentication-code and made-up-date
        }
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
            
        state_file = tmp_path / "incomplete_state.json"
        state = State(str(config_file), str(state_file))
        
        # Should handle missing keys gracefully (return None from state.get())
        request = CompanyData.create_request(state)
        
        assert str(request.CompanyNumber) == "12345678"
        assert str(request.CompanyAuthenticationCode) == "None"  # str(None) = "None"
        assert str(request.MadeUpDate) == "None"
    
    def test_unicode_and_special_characters(self, tmp_path):
        """Test handling of unicode and special characters"""
        config_file = tmp_path / "unicode_config.json"
        config_data = {
            "company-number": "12345678",
            "company-authentication-code": "TËST123",  # Unicode character
            "made-up-date": "2023-12-31"
        }
        
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False)
            
        state_file = tmp_path / "unicode_state.json"
        state = State(str(config_file), str(state_file))
        
        request = CompanyData.create_request(state)
        
        # Should handle unicode correctly
        assert str(request.CompanyAuthenticationCode) == "TËST123"
        
        # Should serialize to XML without errors
        xml_string = etree.tostring(request, encoding='unicode')
        assert "TËST123" in xml_string
    
    def test_multiple_requests_independence(self, test_state, minimal_state):
        """Test that multiple request creations are independent"""
        request1 = CompanyData.create_request(test_state)
        request2 = CompanyData.create_request(minimal_state)
        
        # Requests should have different content
        assert str(request1.CompanyNumber) != str(request2.CompanyNumber)
        assert str(request1.CompanyAuthenticationCode) != str(request2.CompanyAuthenticationCode)
        
        # Modifying one shouldn't affect the other
        request1.CompanyNumber = "99999999"
        assert str(request2.CompanyNumber) == "87654321"  # Unchanged