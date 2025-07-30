# Test Fixtures

This directory contains sample XML responses and test data files used by the test suite.

## Files

### Response Fixtures
- `company_data_response.xml` - Sample response from Companies House for company data requests
- `form_submission_response.xml` - Sample response after successfully submitting accounts
- `submission_status_response.xml` - Sample response for submission status queries
- `error_responses.xml` - Collection of various error response examples

### Test Data
- `sample_accounts.html` - Complete iXBRL accounts file for testing form submissions

## Usage

These fixtures are used by:
- Integration tests to validate response parsing
- Contract tests to ensure response format compatibility
- Mock server to provide realistic responses during testing
- End-to-end tests for complete workflow validation

## Structure

All XML responses follow the GovTalk envelope format:
```xml
<GovTalkMessage xmlns="http://www.govtalk.gov.uk/CM/envelope">
    <EnvelopeVersion>2.0</EnvelopeVersion>
    <Header>...</Header>
    <GovTalkDetails>...</GovTalkDetails>
    <Body>...</Body>
</GovTalkMessage>
```

Company-specific content is contained within the `<Body>` element using appropriate namespaces.

## Error Responses

The `error_responses.xml` file contains examples of common error scenarios:
- Authentication failures (502)
- Validation errors (100)
- Accounts corruption (9999)
- Company not found (1001)
- Service unavailable (503)
- Schema validation errors (400)

These help ensure the client handles all error conditions gracefully.