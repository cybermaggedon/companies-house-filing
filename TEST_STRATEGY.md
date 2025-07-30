# Test Strategy for GnuCash Companies House Filing

## Overview

This document outlines the comprehensive testing strategy for the gnucash-ch-filing project. The strategy employs a multi-layered approach to ensure reliability, correctness, and maintainability of the filing system.

## Test Pyramid

```
        /\
       /E2E\
      /------\
     /Contract\
    /----------\
   /Integration \
  /--------------\
 /     Unit       \
/------------------\
```

## 1. Unit Tests

### Purpose
Test individual components in isolation to ensure they behave correctly at the smallest level.

### Scope
- **Envelope creation** (`ch_filing/envelope.py`)
  - Correct XML structure generation
  - MD5 hash calculation for authentication
  - Namespace handling
  
- **Request builders** (`ch_filing/company_data.py`, `ch_filing/form_submission.py`, `ch_filing/submission_status.py`)
  - XML request generation
  - Data validation
  - Base64 encoding for accounts data
  
- **State management** (`ch_filing/state.py`)
  - Transaction ID increment
  - Submission ID generation
  - Configuration loading
  
- **Response parsing**
  - Error detection and categorization
  - Data extraction from XML responses

### Test Structure
```
tests/unit/
├── test_envelope.py
├── test_company_data.py
├── test_form_submission.py
├── test_submission_status.py
├── test_state.py
└── test_client.py
```

### Example Test
```python
def test_envelope_authentication_hash():
    """Test that authentication values are correctly hashed"""
    config = {
        "presenter-id": "TEST123",
        "authentication": "SECRET",
        # ... other config
    }
    state = State(config)
    envelope = Envelope.create(state, content, "TestClass", "request")
    
    expected_presenter_hash = hashlib.md5(b"TEST123").hexdigest()
    assert envelope.Header.SenderDetails.IDAuthentication.SenderID == expected_presenter_hash
```

## 2. Integration Tests

### Purpose
Test the interaction between multiple components to ensure they work together correctly.

### Scope
- **Client-Server Communication**
  - Request/response cycle with test server
  - Error handling and retry logic
  - SSL/TLS handling
  
- **Full Request Workflows**
  - Company data retrieval
  - Accounts submission
  - Status checking
  
- **State Persistence**
  - Transaction counter updates
  - State file writing and reading

### Test Structure
```
tests/integration/
├── test_client_server.py
├── test_company_data_workflow.py
├── test_accounts_submission_workflow.py
├── test_submission_status_workflow.py
└── test_error_handling.py
```

### Example Test
```python
def test_accounts_submission_workflow():
    """Test complete accounts submission process"""
    with TestServer(port=9303) as server:
        config = create_test_config(server.get_url())
        state = State(config, "test_state.json")
        client = Client(state)
        
        # Submit accounts
        accounts_data = load_test_accounts()
        content = Accounts.create_submission(state, "test.xbrl", accounts_data)
        env = Envelope.create(state, content, "Accounts", "request")
        response = client.call(state, env)
        
        # Verify submission stored
        submission_id = content.FormHeader.SubmissionNumber.text
        assert server.data.get_submission(submission_id) is not None
```

## 3. Contract Tests

### Purpose
Ensure the API contract with Companies House is maintained and our implementation matches their specifications.

### Scope
- **Request Schema Validation**
  - XML structure matches XSD schemas
  - Required fields are present
  - Data types are correct
  
- **Response Handling**
  - Can parse all documented response formats
  - Handle all documented error codes
  - Namespace compatibility

### Test Structure
```
tests/contract/
├── test_request_schemas.py
├── test_response_schemas.py
├── test_error_responses.py
└── fixtures/
    ├── company_data_responses.xml
    ├── submission_responses.xml
    └── error_responses.xml
```

### Example Test
```python
def test_company_data_request_schema():
    """Validate CompanyDataRequest against XSD schema"""
    schema_doc = etree.parse("schema/CompanyData-v3-4.xsd")
    schema = etree.XMLSchema(schema_doc)
    
    request = CompanyData.create_request(test_state)
    request_xml = etree.tostring(request)
    
    doc = etree.fromstring(request_xml)
    assert schema.validate(doc), schema.error_log
```

## 4. End-to-End Tests

### Purpose
Test complete user workflows from command line to Companies House API (using test server).

### Scope
- **CLI Operations**
  - All command-line flags work correctly
  - Config file handling
  - Error messages to users
  
- **Full Filing Process**
  - Load iXBRL file
  - Submit to Companies House
  - Check submission status
  - Handle authentication failures

### Test Structure
```
tests/e2e/
├── test_cli_operations.py
├── test_filing_workflow.py
├── test_authentication.py
└── fixtures/
    ├── test_accounts.html
    ├── valid_config.json
    └── invalid_config.json
```

### Example Test
```python
def test_complete_filing_process():
    """Test filing accounts from command line"""
    with TestServer(port=9303) as server:
        config_file = create_config(server.get_url())
        
        # Submit accounts
        result = subprocess.run([
            "ch-filing",
            "--config", config_file,
            "--accounts", "test_accounts.html",
            "--submit-accounts"
        ], capture_output=True, text=True)
        
        assert result.returncode == 0
        assert "Submission completed" in result.stdout
        
        # Check status
        submission_id = extract_submission_id(result.stdout)
        status_result = subprocess.run([
            "ch-filing",
            "--config", config_file,
            "--submission-id", submission_id,
            "--get-submission-status"
        ], capture_output=True, text=True)
        
        assert f"{submission_id}: accepted" in status_result.stdout
```

## Test Data Management

### Test Fixtures
- **Company Data**: Predefined company records in test server
- **iXBRL Files**: Sample accounts in various formats
- **Configuration**: Test authentication credentials

### Data Builders
```python
class TestDataBuilder:
    @staticmethod
    def create_test_accounts(company_number="12345678"):
        """Create test iXBRL accounts data"""
        return f"""<?xml version="1.0" encoding="UTF-8"?>
        <html xmlns="http://www.w3.org/1999/xhtml">
            <head><title>Test Accounts for {company_number}</title></head>
            <body><!-- Account data --></body>
        </html>"""
```

## Testing Tools and Dependencies

### Add to pyproject.toml:
```toml
[project.optional-dependencies]
test = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
    "pytest-mock>=3.0",
    "pytest-timeout>=2.0",
    "responses>=0.23.0",  # For mocking HTTP
    "freezegun>=1.2",     # For time-based tests
]

[tool.pytest.ini_options]
minversion = "7.0"
testpaths = ["tests"]
python_files = "test_*.py"
python_classes = "Test*"
python_functions = "test_*"
addopts = [
    "--strict-markers",
    "--cov=ch_filing",
    "--cov-report=term-missing",
    "--cov-report=html",
    "--cov-fail-under=80",
]

[tool.coverage.run]
source = ["ch_filing"]
omit = ["*/test_*", "*/tests/*"]
```

## CI/CD Integration

### GitHub Actions Workflow
```yaml
name: Test Suite

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.8", "3.9", "3.10", "3.11"]
    
    steps:
    - uses: actions/checkout@v3
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        pip install -e ".[test]"
    
    - name: Run unit tests
      run: pytest tests/unit -v
    
    - name: Run integration tests
      run: pytest tests/integration -v
    
    - name: Run contract tests
      run: pytest tests/contract -v
    
    - name: Run E2E tests
      run: pytest tests/e2e -v
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

## Test Execution Strategy

### Local Development
```bash
# Run all tests
pytest

# Run specific test category
pytest tests/unit
pytest tests/integration

# Run with coverage
pytest --cov=ch_filing --cov-report=html

# Run specific test
pytest tests/unit/test_envelope.py::test_authentication_hash
```

### Pre-commit Hooks
```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: unit-tests
        name: Unit Tests
        entry: pytest tests/unit
        language: system
        pass_filenames: false
        always_run: true
```

## Test Server Usage

### For Integration/E2E Tests
```python
@pytest.fixture
def test_server():
    """Provide test server for integration tests"""
    with TestServer(port=0) as server:  # port=0 for random port
        yield server

def test_with_server(test_server):
    config = create_test_config(test_server.get_url())
    # ... run test
```

### For Manual Testing
```bash
# Start test server
ch-test-server --port 9303

# In another terminal, test against it
ch-filing --config test_config.json --get-company-data
```

## Performance Testing

### Load Testing
```python
def test_concurrent_submissions():
    """Test server can handle concurrent submissions"""
    with TestServer() as server:
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for i in range(100):
                future = executor.submit(submit_accounts, server.get_url(), i)
                futures.append(future)
            
            results = [f.result() for f in futures]
            assert all(r.success for r in results)
```

## Security Testing

### Authentication Tests
- Invalid credentials
- Malformed authentication headers
- Replay attack prevention

### Input Validation
- XML injection attempts
- Oversized payloads
- Invalid XML structures

## Test Maintenance

### Regular Tasks
1. Update test data when Companies House changes schemas
2. Review and update contract tests quarterly
3. Add tests for new features before implementation
4. Remove obsolete tests
5. Monitor test execution time and optimize slow tests

### Test Documentation
- Each test should have a clear docstring
- Complex test setups should be documented
- Maintain a test inventory spreadsheet

## Success Metrics

- **Unit Test Coverage**: >90%
- **Integration Test Coverage**: >80%
- **Contract Test Pass Rate**: 100%
- **E2E Test Pass Rate**: >95%
- **Test Execution Time**: <5 minutes for full suite
- **Flaky Test Rate**: <1%