# Test Fixtures and Sample Data

This directory contains comprehensive test fixtures, sample data, and utilities for the GnuCash Companies House filing system test suite.

## Directory Structure

```
fixtures/
├── README.md                          # This file
├── accounts/                          # Sample iXBRL accounts files
│   ├── micro_entity_accounts.html     # Micro entity accounts
│   ├── small_company_accounts.html    # Small company accounts  
│   └── sample_accounts.html           # Original sample file
├── configurations/                    # Test configuration files
│   ├── minimal_config.json           # Minimal required fields
│   ├── complete_config.json          # All optional fields included
│   ├── micro_entity_config.json      # Micro entity specific config
│   └── invalid_config.json           # Invalid config for error testing
├── responses/                         # Sample XML response files
│   ├── company_data_response.xml      # Company data query response
│   ├── form_submission_response.xml   # Form submission response
│   ├── submission_status_response.xml # Status query response
│   ├── error_responses.xml            # Various error responses
│   └── comprehensive_error_responses.xml # Extended error scenarios
├── data/                             # Test data utilities
│   └── test_data_generator.py        # Programmatic test data generation
└── scripts/                         # Test suite generation scripts  
    └── generate_test_suite.py       # Generate comprehensive test suites
```

## File Types

### Configuration Files (`configurations/`)

JSON configuration files with different completeness levels:

- **minimal_config.json**: Contains only required fields for basic functionality
- **complete_config.json**: Includes all optional fields for comprehensive testing
- **micro_entity_config.json**: Optimized for micro entity filings
- **invalid_config.json**: Contains invalid data for error handling tests

### Accounts Files (`accounts/`)

iXBRL (inline XBRL) HTML files representing different types of company accounts:

- **micro_entity_accounts.html**: Complete micro entity accounts with P&L and balance sheet
- **small_company_accounts.html**: Small company accounts with full notes and disclosures
- **sample_accounts.html**: Original basic sample for compatibility

### Response Files (`responses/`)

XML files representing various API responses from Companies House:

- **company_data_response.xml**: Successful company information query
- **form_submission_response.xml**: Successful accounts submission
- **submission_status_response.xml**: Status check response
- **error_responses.xml**: Common error scenarios
- **comprehensive_error_responses.xml**: Extended error cases with multiple error types

## Utilities

### Test Data Generator (`data/test_data_generator.py`)

A comprehensive Python utility for generating test data programmatically:

```python
from test_data_generator import TestDataGenerator

generator = TestDataGenerator()

# Generate configurations
config = generator.generate_config('complete')
micro_config = generator.generate_config('micro')

# Generate accounts HTML
accounts_html = generator.generate_accounts_html(
    company_number="12345678",
    company_name="TEST COMPANY LIMITED",
    company_type="small"
)

# Generate response XML
response = generator.generate_response_xml(
    'company_data_success',
    company_number="12345678"
)

# Generate bulk data for performance testing
bulk_data = generator.generate_bulk_test_data(count=100)
```

### Test Suite Generator (`scripts/generate_test_suite.py`)

Automated test suite generation for various scenarios:

```bash
# Generate full test suite
python scripts/generate_test_suite.py

# Generate limited test suite  
python scripts/generate_test_suite.py --count 10

# Generate to specific directory
python scripts/generate_test_suite.py --output-dir /path/to/output
```

## Test Scenarios Covered

### Standard Company Types
- Micro entities (turnover < £632k, assets < £316k)
- Small companies (turnover < £10.2m, assets < £5.1m)
- Medium companies (larger scale testing)

### Edge Cases
- Company numbers with leading zeros
- Very long company names
- Special characters in contact details
- Different company types (EW, SC, NI)
- Various year-end dates
- Short accounting periods

### Error Scenarios
- Invalid company numbers
- Empty required fields
- Malformed URLs
- Invalid date formats
- Oversized field data

### Security Testing
- SQL injection attempts
- XSS injection attempts
- XML external entity injection
- Unicode normalization
- Null byte injection

### Performance Testing
- Large accounts files
- Concurrent submission scenarios
- Rapid sequential requests
- Bulk data processing

## Usage in Tests

### Loading Configuration Data

```python
import json
from pathlib import Path

def load_test_config(config_name: str):
    config_path = Path(__file__).parent / "fixtures" / "configurations" / f"{config_name}_config.json"
    with open(config_path) as f:
        return json.load(f)

# Usage
minimal_config = load_test_config("minimal")
complete_config = load_test_config("complete")
```

### Loading Accounts Data

```python
def load_test_accounts(accounts_name: str):
    accounts_path = Path(__file__).parent / "fixtures" / "accounts" / f"{accounts_name}_accounts.html"
    with open(accounts_path) as f:
        return f.read()

# Usage
micro_accounts = load_test_accounts("micro_entity")
small_accounts = load_test_accounts("small_company")
```

### Loading Response Data

```python
from lxml import etree

def load_test_response(response_name: str):
    response_path = Path(__file__).parent / "fixtures" / "responses" / f"{response_name}.xml"
    with open(response_path) as f:
        return etree.parse(f)

# Usage
success_response = load_test_response("company_data_response")
error_response = load_test_response("error_responses")
```

## Integration with Test Framework

The fixtures are designed to integrate seamlessly with pytest:

```python
import pytest
from pathlib import Path

@pytest.fixture
def test_fixtures_dir():
    return Path(__file__).parent / "fixtures"

@pytest.fixture
def minimal_config(test_fixtures_dir):
    config_path = test_fixtures_dir / "configurations" / "minimal_config.json"
    with open(config_path) as f:
        return json.load(f)

@pytest.fixture
def micro_accounts_html(test_fixtures_dir):
    accounts_path = test_fixtures_dir / "accounts" / "micro_entity_accounts.html"
    with open(accounts_path) as f:
        return f.read()

def test_with_fixtures(minimal_config, micro_accounts_html):
    # Use the loaded fixtures in your test
    assert minimal_config["presenter-id"] == "MINIMAL_PRESENTER"
    assert "MICRO ENTITY TEST LIMITED" in micro_accounts_html
```

## Maintenance

### Adding New Fixtures

1. **Manual Creation**: Create files directly in the appropriate subdirectory
2. **Programmatic Generation**: Use `TestDataGenerator` to create new data
3. **Bulk Generation**: Use `generate_test_suite.py` to create comprehensive suites

### Updating Existing Fixtures

1. Update source files directly
2. Regenerate using the data generator utilities
3. Ensure compatibility with existing tests

### Validation

All fixtures should be validated to ensure:
- JSON configuration files are valid JSON and contain required fields
- iXBRL accounts files are valid HTML with proper XBRL markup
- XML response files are well-formed and follow the GovTalk schema

## Schema Compliance

### Configuration Files
- Must contain required fields: `presenter-id`, `authentication`, `company-number`, `made-up-date`, `url`
- Optional fields follow the system's configuration schema
- Field validation follows Companies House requirements

### Accounts Files  
- Must be valid HTML5 with iXBRL namespace declarations
- Must include required XBRL contexts and units
- Must contain mandatory company information elements
- Should follow UK GAAP taxonomy requirements

### Response Files
- Must follow GovTalk envelope schema version 2.0
- Must include proper message routing headers
- Error responses must include appropriate error codes and descriptions
- Success responses must contain expected business data elements

## Performance Considerations

- Large test files are marked appropriately for selective execution
- Bulk data generation is optimized for memory efficiency
- Generated test suites include performance timing metadata
- Test data is structured to minimize I/O operations during test execution

## Security

- Test configurations use safe, non-production credentials
- No real company data is included in fixtures
- Security test payloads are safe for testing environments
- All generated data is clearly marked as test data