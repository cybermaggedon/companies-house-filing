import pytest
import json
from lxml import etree, objectify

from ch_filing.submission_status import SubmissionStatus
from ch_filing.state import State


class TestSubmissionStatus:
    """Test the SubmissionStatus class for creating GetSubmissionStatus XML"""
    
    @pytest.fixture
    def test_state(self, tmp_path):
        """Create a test state with presenter ID for submission status requests"""
        config_file = tmp_path / "test_config.json"
        config_data = {
            "presenter-id": "TEST_PRESENTER_123",
            "authentication": "TEST_AUTH_456",
            "company-number": "12345678",
            "company-authentication-code": "AUTH1234"
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
            "presenter-id": "MIN_PRESENTER_789"
        }
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
            
        state_file = tmp_path / "minimal_state.json"
        return State(str(config_file), str(state_file))
    
    def test_create_request_with_submission_id_structure(self, test_state):
        """Test that create_request with submission ID generates correct XML structure"""
        submission_id = "S00123"
        request = SubmissionStatus.create_request(test_state, submission_id)
        
        # Check root element
        assert request.tag.endswith("GetSubmissionStatus")
        
        # Check required elements exist
        assert hasattr(request, 'SubmissionNumber')
        assert hasattr(request, 'PresenterID')
        
        # Verify content
        assert str(request.SubmissionNumber) == "S00123"
        assert str(request.PresenterID) == "TEST_PRESENTER_123"
    
    def test_create_request_without_submission_id_structure(self, test_state):
        """Test that create_request without submission ID generates correct XML structure"""
        request = SubmissionStatus.create_request(test_state)
        
        # Check root element
        assert request.tag.endswith("GetSubmissionStatus")
        
        # Check required elements exist
        assert hasattr(request, 'PresenterID')
        
        # Check SubmissionNumber is NOT present when no submission ID provided
        assert not hasattr(request, 'SubmissionNumber')
        
        # Verify content
        assert str(request.PresenterID) == "TEST_PRESENTER_123"
    
    def test_create_request_namespace(self, test_state):
        """Test that create_request uses correct XML namespace"""
        request = SubmissionStatus.create_request(test_state, "S00123")
        
        # Check namespace
        expected_ns = "http://xmlgw.companieshouse.gov.uk"
        assert request.nsmap[None] == expected_ns
        
        # Convert to string to check namespace in XML
        xml_string = etree.tostring(request, encoding='unicode')
        assert f'xmlns="{expected_ns}"' in xml_string
    
    def test_create_request_schema_location(self, test_state):
        """Test that create_request includes schema location"""
        request = SubmissionStatus.create_request(test_state, "S00123")
        
        # Convert to string to check schema location
        xml_string = etree.tostring(request, encoding='unicode')
        
        # Check schema location is set
        assert 'schemaLocation' in xml_string
        assert 'GetSubmissionStatus-v2-5.xsd' in xml_string
    
    def test_different_presenter_ids(self, tmp_path):
        """Test request creation with different presenter IDs"""
        test_cases = [
            "PRESENTER_001",
            "TEST_PRES_ABC",
            "DEV_PRESENTER_XYZ",
            "DEMO_PRES_123456",
        ]
        
        for presenter_id in test_cases:
            config_file = tmp_path / f"config_{presenter_id}.json"
            config_data = {
                "presenter-id": presenter_id
            }
            
            with open(config_file, 'w') as f:
                json.dump(config_data, f)
                
            state_file = tmp_path / f"state_{presenter_id}.json"
            state = State(str(config_file), str(state_file))
            
            request = SubmissionStatus.create_request(state, "S00123")
            assert str(request.PresenterID) == presenter_id
    
    def test_different_submission_ids(self, test_state):
        """Test request creation with different submission ID formats"""
        test_cases = [
            "S00001",
            "S00123",
            "S99999",
            "S12345",
        ]
        
        for submission_id in test_cases:
            request = SubmissionStatus.create_request(test_state, submission_id)
            assert str(request.SubmissionNumber) == submission_id
    
    def test_xml_serialization_with_submission_id(self, test_state):
        """Test that request with submission ID can be properly serialized to XML"""
        request = SubmissionStatus.create_request(test_state, "S00123")
        
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
    
    def test_xml_serialization_without_submission_id(self, test_state):
        """Test that request without submission ID can be properly serialized to XML"""
        request = SubmissionStatus.create_request(test_state)
        
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
    
    def test_xml_parsing_roundtrip_with_submission_id(self, test_state):
        """Test that generated XML with submission ID can be parsed back"""
        request = SubmissionStatus.create_request(test_state, "S00456")
        
        # Serialize to XML
        xml_string = etree.tostring(request, encoding='unicode')
        
        # Parse back from XML
        parsed = objectify.fromstring(xml_string.encode('utf-8'))
        
        # Verify content is preserved
        assert str(parsed.SubmissionNumber) == "S00456"
        assert str(parsed.PresenterID) == "TEST_PRESENTER_123"
    
    def test_xml_parsing_roundtrip_without_submission_id(self, test_state):
        """Test that generated XML without submission ID can be parsed back"""
        request = SubmissionStatus.create_request(test_state)
        
        # Serialize to XML
        xml_string = etree.tostring(request, encoding='unicode')
        
        # Parse back from XML
        parsed = objectify.fromstring(xml_string.encode('utf-8'))
        
        # Verify content is preserved
        assert str(parsed.PresenterID) == "TEST_PRESENTER_123"
        # Should not have SubmissionNumber
        assert not hasattr(parsed, 'SubmissionNumber')
    
    def test_xml_element_order_with_submission_id(self, test_state):
        """Test that XML elements appear in the expected order when submission ID is provided"""
        request = SubmissionStatus.create_request(test_state, "S00123")
        
        # Parse XML to get proper child order
        xml_string = etree.tostring(request, encoding='unicode')
        doc = etree.fromstring(xml_string.encode('utf-8'))
        
        # Get direct children of GetSubmissionStatus
        children = list(doc)
        child_tags = [child.tag.split('}')[-1] for child in children]  # Remove namespace
        
        # Check expected order based on XSD (SubmissionNumber should come before PresenterID)
        expected_order = ["SubmissionNumber", "PresenterID"]
        assert child_tags == expected_order
    
    def test_xml_element_order_without_submission_id(self, test_state):
        """Test that XML elements appear in the expected order when no submission ID is provided"""
        request = SubmissionStatus.create_request(test_state)
        
        # Parse XML to get proper child order
        xml_string = etree.tostring(request, encoding='unicode')
        doc = etree.fromstring(xml_string.encode('utf-8'))
        
        # Get direct children of GetSubmissionStatus
        children = list(doc)
        child_tags = [child.tag.split('}')[-1] for child in children]  # Remove namespace
        
        # Check expected order based on XSD (only PresenterID should be present)
        expected_order = ["PresenterID"]
        assert child_tags == expected_order
    
    def test_xml_validation_structure_with_submission_id(self, test_state):
        """Test that XML structure with submission ID matches expected schema requirements"""
        request = SubmissionStatus.create_request(test_state, "S00789")
        xml_string = etree.tostring(request, encoding='unicode')
        
        # Parse with lxml to validate structure
        doc = etree.fromstring(xml_string.encode('utf-8'))
        
        # Check root element name and namespace
        expected_ns = "http://xmlgw.companieshouse.gov.uk"
        assert doc.tag == f"{{{expected_ns}}}GetSubmissionStatus"
        
        # Check required child elements exist
        submission_number = doc.find(f".//{{{expected_ns}}}SubmissionNumber")
        presenter_id = doc.find(f".//{{{expected_ns}}}PresenterID")
        
        assert submission_number is not None
        assert presenter_id is not None
        assert submission_number.text == "S00789"
        assert presenter_id.text == "TEST_PRESENTER_123"
    
    def test_xml_validation_structure_without_submission_id(self, test_state):
        """Test that XML structure without submission ID matches expected schema requirements"""
        request = SubmissionStatus.create_request(test_state)
        xml_string = etree.tostring(request, encoding='unicode')
        
        # Parse with lxml to validate structure
        doc = etree.fromstring(xml_string.encode('utf-8'))
        
        # Check root element name and namespace
        expected_ns = "http://xmlgw.companieshouse.gov.uk"
        assert doc.tag == f"{{{expected_ns}}}GetSubmissionStatus"
        
        # Check required child elements exist
        presenter_id = doc.find(f".//{{{expected_ns}}}PresenterID")
        submission_number = doc.find(f".//{{{expected_ns}}}SubmissionNumber")
        
        assert presenter_id is not None
        assert submission_number is None  # Should not be present
        assert presenter_id.text == "TEST_PRESENTER_123"
    
    def test_static_method_call_patterns(self, test_state):
        """Test different ways of calling the static method"""
        # Call with positional arguments
        request1 = SubmissionStatus.create_request(test_state, "S00123")
        
        # Call with keyword arguments
        request2 = SubmissionStatus.create_request(st=test_state, sub_id="S00123")
        
        # Call without submission ID
        request3 = SubmissionStatus.create_request(test_state)
        
        # Call with None submission ID (should behave like no submission ID)
        request4 = SubmissionStatus.create_request(test_state, None)
        
        # Verify results
        assert str(request1.SubmissionNumber) == "S00123"
        assert str(request2.SubmissionNumber) == "S00123"
        assert not hasattr(request3, 'SubmissionNumber')
        assert not hasattr(request4, 'SubmissionNumber')
    
    def test_multiple_requests_independence(self, test_state, minimal_state):
        """Test that multiple request creations are independent"""
        request1 = SubmissionStatus.create_request(test_state, "S00111")
        request2 = SubmissionStatus.create_request(minimal_state, "S00222")
        
        # Requests should have different content
        assert str(request1.PresenterID) != str(request2.PresenterID)
        assert str(request1.SubmissionNumber) != str(request2.SubmissionNumber)
        
        # Modifying one shouldn't affect the other
        request1.PresenterID = "MODIFIED_PRESENTER"
        assert str(request2.PresenterID) == "MIN_PRESENTER_789"  # Unchanged
    
    def test_missing_presenter_id(self, tmp_path):
        """Test behavior when presenter ID is missing from config"""
        config_file = tmp_path / "no_presenter_config.json"
        config_data = {
            "company-number": "12345678"
            # Missing presenter-id
        }
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
            
        state_file = tmp_path / "no_presenter_state.json"
        state = State(str(config_file), str(state_file))
        
        # Should handle missing presenter-id gracefully (return None from state.get())
        request = SubmissionStatus.create_request(state, "S00123")
        
        assert str(request.SubmissionNumber) == "S00123"
        assert str(request.PresenterID) == "None"  # str(None) = "None"
    
    def test_empty_presenter_id(self, tmp_path):
        """Test behavior when presenter ID is empty"""
        config_file = tmp_path / "empty_presenter_config.json"
        config_data = {
            "presenter-id": ""
        }
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
            
        state_file = tmp_path / "empty_presenter_state.json"
        state = State(str(config_file), str(state_file))
        
        # Should handle empty presenter-id
        request = SubmissionStatus.create_request(state, "S00123")
        
        assert str(request.SubmissionNumber) == "S00123"
        assert str(request.PresenterID) == ""
    
    def test_unicode_in_submission_id(self, test_state):
        """Test handling of unicode characters in submission ID (edge case)"""
        # While unlikely in real usage, test robustness
        unicode_submission_id = "S00123ñ"
        request = SubmissionStatus.create_request(test_state, unicode_submission_id)
        
        # Should handle unicode correctly
        assert str(request.SubmissionNumber) == unicode_submission_id
        
        # Should serialize to XML without errors
        xml_string = etree.tostring(request, encoding='unicode')
        assert unicode_submission_id in xml_string
    
    def test_unicode_in_presenter_id(self, tmp_path):
        """Test handling of unicode characters in presenter ID"""
        config_file = tmp_path / "unicode_presenter_config.json"
        config_data = {
            "presenter-id": "PRËSENTÉR_123"
        }
        
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False)
            
        state_file = tmp_path / "unicode_presenter_state.json"
        state = State(str(config_file), str(state_file))
        
        request = SubmissionStatus.create_request(state, "S00123")
        
        # Should handle unicode correctly
        assert str(request.PresenterID) == "PRËSENTÉR_123"
        
        # Should serialize to XML without errors
        xml_string = etree.tostring(request, encoding='unicode')
        assert "PRËSENTÉR_123" in xml_string