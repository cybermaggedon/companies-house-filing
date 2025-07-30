#!/usr/bin/env python3
"""
Test data generator for GnuCash Companies House filing tests.

This module provides utilities to generate test data for various scenarios:
- Company configurations
- Account data files (iXBRL)
- Response XML files
- State files
- Mock server configurations
"""

import json
import random
import string
from pathlib import Path
from typing import Dict, List, Optional, Union
from datetime import datetime, timedelta
import hashlib
import base64


class TestDataGenerator:
    """Generate comprehensive test data for the filing system"""
    
    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or Path(__file__).parent
        
    def generate_company_number(self, prefix: str = "") -> str:
        """Generate a valid 8-digit company number"""
        if prefix:
            remaining_digits = 8 - len(prefix)
            suffix = ''.join(random.choices(string.digits, k=remaining_digits))
            return prefix + suffix
        return ''.join(random.choices(string.digits, k=8))
    
    def generate_auth_code(self, length: int = 8) -> str:
        """Generate a company authentication code"""
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
    
    def generate_presenter_id(self, suffix: str = "") -> str:
        """Generate a presenter ID"""
        base = "TEST_PRESENTER"
        if suffix:
            return f"{base}_{suffix}"
        return f"{base}_{random.randint(1000, 9999)}"
    
    def generate_config(self, 
                       config_type: str = "complete",
                       company_number: Optional[str] = None,
                       **overrides) -> Dict:
        """
        Generate a test configuration file
        
        Args:
            config_type: Type of config ('minimal', 'complete', 'micro', 'invalid')
            company_number: Specific company number to use
            **overrides: Override specific fields
        """
        company_num = company_number or self.generate_company_number()
        
        if config_type == "minimal":
            config = {
                "presenter-id": self.generate_presenter_id("MIN"),
                "authentication": self.generate_auth_code(16),
                "company-number": company_num,
                "made-up-date": "2023-12-31",
                "url": "http://localhost:8080/v1-0/xmlgw/Gateway"
            }
        elif config_type == "micro":
            config = {
                "presenter-id": self.generate_presenter_id("MICRO"),
                "authentication": self.generate_auth_code(16),
                "company-number": company_num,
                "company-name": f"MICRO ENTITY {random.randint(100, 999)} LIMITED",
                "company-authentication-code": self.generate_auth_code(6),
                "company-type": "EW",
                "contact-name": f"Test Contact {random.randint(1, 100)}",
                "contact-number": f"079{random.randint(10, 99)} {random.randint(100000, 999999)}",
                "email": f"test{random.randint(1, 1000)}@example.com",
                "made-up-date": "2023-12-31",
                "date-signed": "2024-01-15",
                "date": "2024-01-20",
                "package-reference": f"MICRO{random.randint(100, 999)}",
                "url": "http://localhost:8080/v1-0/xmlgw/Gateway"
            }
        elif config_type == "invalid":
            config = {
                "presenter-id": "",  # Invalid: empty
                "authentication": "TOO_SHORT",  # Invalid: too short
                "company-number": "INVALID",  # Invalid: not numeric
                "made-up-date": "invalid-date",  # Invalid: bad format
                "url": "not-a-url"  # Invalid: malformed URL
            }
        else:  # complete
            config = {
                "presenter-id": self.generate_presenter_id("COMPLETE"),
                "authentication": self.generate_auth_code(20),
                "company-number": company_num,
                "company-name": f"COMPLETE TEST COMPANY {random.randint(100, 999)} LIMITED",
                "company-authentication-code": self.generate_auth_code(8),
                "company-type": random.choice(["EW", "SC", "NI"]),
                "contact-name": f"Complete Test Contact {random.randint(1, 100)}",
                "contact-number": f"079{random.randint(10, 99)} {random.randint(100000, 999999)}",
                "email": f"complete{random.randint(1, 1000)}@example.com",
                "made-up-date": "2023-12-31",
                "date-signed": "2024-01-15", 
                "date": "2024-01-20",
                "package-reference": f"COMP{random.randint(100, 999)}",
                "url": "http://localhost:8080/v1-0/xmlgw/Gateway"
            }
        
        # Apply overrides
        config.update(overrides)
        return config
    
    def generate_financial_data(self, company_type: str = "small") -> Dict:
        """Generate realistic financial figures for different company types"""
        
        if company_type == "micro":
            return {
                "turnover": random.randint(50000, 632000),  # Micro entity limits
                "total_assets": random.randint(10000, 316000),
                "employees": random.randint(1, 10),
                "cost_of_sales": lambda t: int(t * random.uniform(0.4, 0.7)),
                "admin_expenses": lambda t: int(t * random.uniform(0.15, 0.35)),
                "profit_margin": random.uniform(0.05, 0.25)
            }
        elif company_type == "small":
            return {
                "turnover": random.randint(100000, 10200000),  # Small company limits
                "total_assets": random.randint(50000, 5100000),
                "employees": random.randint(5, 50),
                "cost_of_sales": lambda t: int(t * random.uniform(0.45, 0.75)),
                "admin_expenses": lambda t: int(t * random.uniform(0.15, 0.35)),
                "profit_margin": random.uniform(0.03, 0.20)
            }
        else:  # large
            return {
                "turnover": random.randint(5000000, 50000000),
                "total_assets": random.randint(2000000, 25000000),
                "employees": random.randint(25, 250),
                "cost_of_sales": lambda t: int(t * random.uniform(0.50, 0.80)),
                "admin_expenses": lambda t: int(t * random.uniform(0.10, 0.30)),
                "profit_margin": random.uniform(0.02, 0.15)
            }
    
    def generate_accounts_html(self, 
                              company_number: str,
                              company_name: str,
                              company_type: str = "small") -> str:
        """Generate a complete iXBRL accounts file"""
        
        financial_data = self.generate_financial_data(company_type)
        turnover = financial_data["turnover"]
        
        # Calculate derived figures
        cost_of_sales = financial_data["cost_of_sales"](turnover)
        gross_profit = turnover - cost_of_sales
        admin_expenses = financial_data["admin_expenses"](turnover)
        operating_profit = gross_profit - admin_expenses
        
        # Previous year figures (90-110% of current year)
        prev_multiplier = random.uniform(0.9, 1.1)
        prev_turnover = int(turnover * prev_multiplier)
        prev_cost_of_sales = int(cost_of_sales * prev_multiplier)
        prev_gross_profit = prev_turnover - prev_cost_of_sales
        prev_admin_expenses = int(admin_expenses * prev_multiplier)
        prev_operating_profit = prev_gross_profit - prev_admin_expenses
        
        # Balance sheet figures
        current_assets = int(turnover * random.uniform(0.15, 0.35))
        fixed_assets = int(turnover * random.uniform(0.10, 0.30))
        current_liabilities = int(current_assets * random.uniform(0.30, 0.70))
        net_assets = current_assets + fixed_assets - current_liabilities
        
        # Share capital and reserves
        share_capital = random.choice([100, 1000, 10000])
        profit_loss_reserve = net_assets - share_capital
        
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"
      xmlns:uk-bus="http://xbrl.frc.org.uk/cd/2021-01-01/business"
      xmlns:uk-core="http://xbrl.frc.org.uk/fr/2021-01-01/core">
<head>
    <title>{company_name} - Annual Accounts</title>
    <ix:header>
        <ix:hidden>
            <ix:nonNumeric contextRef="entity" name="uk-bus:EntityCurrentLegalName">{company_name}</ix:nonNumeric>
            <ix:nonNumeric contextRef="entity" name="uk-bus:CompaniesHouseRegisteredNumber">{company_number}</ix:nonNumeric>
            <ix:nonNumeric contextRef="entity" name="uk-bus:EntityDormantCompanyIndicator">false</ix:nonNumeric>
            <ix:nonNumeric contextRef="period" name="uk-bus:BalanceSheetDate">2023-12-31</ix:nonNumeric>
        </ix:hidden>
    </ix:header>
</head>
<body>
    <div style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
        <h1>{company_name}</h1>
        <p><strong>Company Registration Number:</strong> <ix:nonNumeric contextRef="entity" name="uk-bus:CompaniesHouseRegisteredNumber">{company_number}</ix:nonNumeric></p>
        
        <h2>Annual Accounts for the year ended 31 December 2023</h2>
        
        <h3>Profit and Loss Account</h3>
        <table style="width: 100%; border-collapse: collapse; border: 1px solid #000;">
            <tr>
                <td style="border: 1px solid #000; padding: 8px;">Turnover</td>
                <td style="border: 1px solid #000; padding: 8px; text-align: right;">
                    <ix:nonFraction contextRef="period" name="uk-core:Turnover" unitRef="GBP" decimals="0">{turnover}</ix:nonFraction>
                </td>
                <td style="border: 1px solid #000; padding: 8px; text-align: right;">
                    <ix:nonFraction contextRef="period-previous" name="uk-core:Turnover" unitRef="GBP" decimals="0">{prev_turnover}</ix:nonFraction>
                </td>
            </tr>
            <tr>
                <td style="border: 1px solid #000; padding: 8px;">Cost of sales</td>
                <td style="border: 1px solid #000; padding: 8px; text-align: right;">
                    <ix:nonFraction contextRef="period" name="uk-core:CostOfSales" unitRef="GBP" decimals="0" sign="-">-{cost_of_sales}</ix:nonFraction>
                </td>
                <td style="border: 1px solid #000; padding: 8px; text-align: right;">
                    <ix:nonFraction contextRef="period-previous" name="uk-core:CostOfSales" unitRef="GBP" decimals="0" sign="-">-{prev_cost_of_sales}</ix:nonFraction>
                </td>
            </tr>
            <tr>
                <td style="border: 1px solid #000; padding: 8px;">Gross profit</td>
                <td style="border: 1px solid #000; padding: 8px; text-align: right;">
                    <ix:nonFraction contextRef="period" name="uk-core:GrossProfit" unitRef="GBP" decimals="0">{gross_profit}</ix:nonFraction>
                </td>
                <td style="border: 1px solid #000; padding: 8px; text-align: right;">
                    <ix:nonFraction contextRef="period-previous" name="uk-core:GrossProfit" unitRef="GBP" decimals="0">{prev_gross_profit}</ix:nonFraction>
                </td>
            </tr>
            <tr>
                <td style="border: 1px solid #000; padding: 8px;">Operating profit</td>
                <td style="border: 1px solid #000; padding: 8px; text-align: right;">
                    <ix:nonFraction contextRef="period" name="uk-core:OperatingProfitLoss" unitRef="GBP" decimals="0">{operating_profit}</ix:nonFraction>
                </td>
                <td style="border: 1px solid #000; padding: 8px; text-align: right;">
                    <ix:nonFraction contextRef="period-previous" name="uk-core:OperatingProfitLoss" unitRef="GBP" decimals="0">{prev_operating_profit}</ix:nonFraction>
                </td>
            </tr>
        </table>
        
        <h3>Balance Sheet as at 31 December 2023</h3>
        <table style="width: 100%; border-collapse: collapse; border: 1px solid #000;">
            <tr>
                <td style="border: 1px solid #000; padding: 8px;">Fixed assets</td>
                <td style="border: 1px solid #000; padding: 8px; text-align: right;">
                    <ix:nonFraction contextRef="period" name="uk-core:FixedAssets" unitRef="GBP" decimals="0">{fixed_assets}</ix:nonFraction>
                </td>
            </tr>
            <tr>
                <td style="border: 1px solid #000; padding: 8px;">Current assets</td>
                <td style="border: 1px solid #000; padding: 8px; text-align: right;">
                    <ix:nonFraction contextRef="period" name="uk-core:TotalCurrentAssets" unitRef="GBP" decimals="0">{current_assets}</ix:nonFraction>
                </td>
            </tr>
            <tr>
                <td style="border: 1px solid #000; padding: 8px;">Current liabilities</td>
                <td style="border: 1px solid #000; padding: 8px; text-align: right;">
                    <ix:nonFraction contextRef="period" name="uk-core:CreditorsAmountFallingDueWithinOneYear" unitRef="GBP" decimals="0" sign="-">-{current_liabilities}</ix:nonFraction>
                </td>
            </tr>
            <tr>
                <td style="border: 1px solid #000; padding: 8px; font-weight: bold;">Net assets</td>
                <td style="border: 1px solid #000; padding: 8px; text-align: right; font-weight: bold;">
                    <ix:nonFraction contextRef="period" name="uk-core:TotalNetAssets" unitRef="GBP" decimals="0">{net_assets}</ix:nonFraction>
                </td>
            </tr>
        </table>
        
        <h3>Capital and Reserves</h3>
        <table style="width: 100%; border-collapse: collapse; border: 1px solid #000;">
            <tr>
                <td style="border: 1px solid #000; padding: 8px;">Share capital</td>
                <td style="border: 1px solid #000; padding: 8px; text-align: right;">
                    <ix:nonFraction contextRef="period" name="uk-core:CalledUpShareCapital" unitRef="GBP" decimals="0">{share_capital}</ix:nonFraction>
                </td>
            </tr>
            <tr>
                <td style="border: 1px solid #000; padding: 8px;">Profit and loss account</td>
                <td style="border: 1px solid #000; padding: 8px; text-align: right;">
                    <ix:nonFraction contextRef="period" name="uk-core:ProfitLossAccountReserve" unitRef="GBP" decimals="0">{profit_loss_reserve}</ix:nonFraction>
                </td>
            </tr>
            <tr>
                <td style="border: 1px solid #000; padding: 8px; font-weight: bold;">Total shareholders' funds</td>
                <td style="border: 1px solid #000; padding: 8px; text-align: right; font-weight: bold;">
                    <ix:nonFraction contextRef="period" name="uk-core:TotalShareholdersFunds" unitRef="GBP" decimals="0">{net_assets}</ix:nonFraction>
                </td>
            </tr>
        </table>
    </div>
    
    <!-- XBRL contexts -->
    <ix:hidden>
        <xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance">
            <xbrli:context id="entity">
                <xbrli:entity>
                    <xbrli:identifier scheme="http://www.companieshouse.gov.uk/">{company_number}</xbrli:identifier>
                </xbrli:entity>
                <xbrli:period>
                    <xbrli:instant>2023-12-31</xbrli:instant>
                </xbrli:period>
            </xbrli:context>
            <xbrli:context id="period">
                <xbrli:entity>
                    <xbrli:identifier scheme="http://www.companieshouse.gov.uk/">{company_number}</xbrli:identifier>
                </xbrli:entity>
                <xbrli:period>
                    <xbrli:startDate>2023-01-01</xbrli:startDate>
                    <xbrli:endDate>2023-12-31</xbrli:endDate>
                </xbrli:period>
            </xbrli:context>
            <xbrli:context id="period-previous">
                <xbrli:entity>
                    <xbrli:identifier scheme="http://www.companieshouse.gov.uk/">{company_number}</xbrli:identifier>
                </xbrli:entity>
                <xbrli:period>
                    <xbrli:startDate>2022-01-01</xbrli:startDate>
                    <xbrli:endDate>2022-12-31</xbrli:endDate>
                </xbrli:period>
            </xbrli:context>
            <xbrli:unit id="GBP">
                <xbrli:measure>iso4217:GBP</xbrli:measure>
            </xbrli:unit>
        </xbrli:xbrl>
    </ix:hidden>
</body>
</html>"""
    
    def generate_response_xml(self, response_type: str, **kwargs) -> str:
        """Generate response XML for different scenarios"""
        
        transaction_id = kwargs.get('transaction_id', f'T{random.randint(100000, 999999):06d}')
        correlation_id = kwargs.get('correlation_id', f'C{random.randint(100000, 999999):06d}')
        
        if response_type == "company_data_success":
            return self._generate_company_data_response(transaction_id, correlation_id, **kwargs)
        elif response_type == "submission_success":
            return self._generate_submission_response(transaction_id, correlation_id, **kwargs)
        elif response_type == "status_response":
            return self._generate_status_response(transaction_id, correlation_id, **kwargs)
        elif response_type == "error":
            return self._generate_error_response(transaction_id, correlation_id, **kwargs)
        else:
            raise ValueError(f"Unknown response type: {response_type}")
    
    def _generate_company_data_response(self, tx_id: str, corr_id: str, **kwargs) -> str:
        """Generate a successful company data response"""
        company_number = kwargs.get('company_number', self.generate_company_number())
        company_name = kwargs.get('company_name', f'GENERATED COMPANY {random.randint(100, 999)} LIMITED')
        
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<GovTalkMessage xmlns="http://www.govtalk.gov.uk/CM/envelope">
  <EnvelopeVersion>2.0</EnvelopeVersion>
  <Header>
    <MessageDetails>
      <Class>HMRC-CH-DEV</Class>
      <Qualifier>response</Qualifier>
      <Function>submit</Function>
      <TransactionID>{tx_id}</TransactionID>
      <CorrelationID>{corr_id}</CorrelationID>
      <Transformation>XML</Transformation>
      <GatewayTest>1</GatewayTest>
    </MessageDetails>
  </Header>
  <GovTalkDetails>
    <GovTalkErrors/>
  </GovTalkDetails>
  <Body>
    <CompanyDataResponse xmlns="http://www.companieshouse.gov.uk/schemas/rpp">
      <CompanyNumber>{company_number}</CompanyNumber>
      <CompanyName>{company_name}</CompanyName>
      <CompanyCategory>Private Limited Company</CompanyCategory>
      <CompanyStatus>Active</CompanyStatus>
      <IncorporationDate>2020-01-15</IncorporationDate>
      <NextDueDate>2024-12-31</NextDueDate>
      <LastMadeUpDate>2022-12-31</LastMadeUpDate>
      <AccountsType>FULL</AccountsType>
    </CompanyDataResponse>
  </Body>
</GovTalkMessage>"""
    
    def _generate_submission_response(self, tx_id: str, corr_id: str, **kwargs) -> str:
        """Generate a successful submission response"""
        submission_id = kwargs.get('submission_id', f'S{random.randint(10000, 99999):05d}')
        
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<GovTalkMessage xmlns="http://www.govtalk.gov.uk/CM/envelope">
  <EnvelopeVersion>2.0</EnvelopeVersion>
  <Header>
    <MessageDetails>
      <Class>HMRC-CH-DEV</Class>
      <Qualifier>response</Qualifier>
      <Function>submit</Function>
      <TransactionID>{tx_id}</TransactionID>
      <CorrelationID>{corr_id}</CorrelationID>
      <Transformation>XML</Transformation>
      <GatewayTest>1</GatewayTest>
    </MessageDetails>
  </Header>
  <GovTalkDetails>
    <GovTalkErrors/>
  </GovTalkDetails>
  <Body>
    <SubmissionResponse xmlns="http://www.companieshouse.gov.uk/schemas/rpp">
      <SubmissionNumber>{submission_id}</SubmissionNumber>
      <AcceptedDate>{datetime.now().strftime('%Y-%m-%d')}</AcceptedDate>
      <Status>Accepted</Status>
    </SubmissionResponse>
  </Body>
</GovTalkMessage>"""
    
    def _generate_status_response(self, tx_id: str, corr_id: str, **kwargs) -> str:
        """Generate a submission status response"""
        submission_id = kwargs.get('submission_id', f'S{random.randint(10000, 99999):05d}')
        status = kwargs.get('status', 'Processed')
        
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<GovTalkMessage xmlns="http://www.govtalk.gov.uk/CM/envelope">
  <EnvelopeVersion>2.0</EnvelopeVersion>
  <Header>
    <MessageDetails>
      <Class>HMRC-CH-DEV</Class>
      <Qualifier>response</Qualifier>
      <Function>submit</Function>
      <TransactionID>{tx_id}</TransactionID>
      <CorrelationID>{corr_id}</CorrelationID>
      <Transformation>XML</Transformation>
      <GatewayTest>1</GatewayTest>
    </MessageDetails>
  </Header>
  <GovTalkDetails>
    <GovTalkErrors/>
  </GovTalkDetails>
  <Body>
    <SubmissionStatusResponse xmlns="http://www.companieshouse.gov.uk/schemas/rpp">
      <SubmissionNumber>{submission_id}</SubmissionNumber>
      <Status>{status}</Status>
      <ProcessedDate>{datetime.now().strftime('%Y-%m-%d')}</ProcessedDate>
    </SubmissionStatusResponse>
  </Body>
</GovTalkMessage>"""
    
    def _generate_error_response(self, tx_id: str, corr_id: str, **kwargs) -> str:
        """Generate an error response"""
        error_code = kwargs.get('error_code', '502')
        error_text = kwargs.get('error_text', 'Authentication failure')
        
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<GovTalkMessage xmlns="http://www.govtalk.gov.uk/CM/envelope">
  <EnvelopeVersion>2.0</EnvelopeVersion>
  <Header>
    <MessageDetails>
      <Class>HMRC-CH-DEV</Class>
      <Qualifier>error</Qualifier>
      <Function>submit</Function>
      <TransactionID>{tx_id}</TransactionID>
      <CorrelationID>{corr_id}</CorrelationID>
      <Transformation>XML</Transformation>
      <GatewayTest>1</GatewayTest>
    </MessageDetails>
  </Header>
  <GovTalkDetails>
    <GovTalkErrors>
      <Error>
        <RaisedBy>GovTalk</RaisedBy>
        <Number>{error_code}</Number>
        <Type>fatal</Type>
        <Text>{error_text}</Text>
        <Location>Body</Location>
      </Error>
    </GovTalkErrors>
  </GovTalkDetails>
  <Body>
    <ErrorResponse xmlns="http://www.govtalk.gov.uk/schemas/govtalk/govtalkheader">
      <ErrorDescription>{error_text}</ErrorDescription>
    </ErrorResponse>
  </Body>
</GovTalkMessage>"""
    
    def generate_bulk_test_data(self, count: int = 10) -> Dict:
        """Generate bulk test data for stress testing"""
        
        data = {
            'configs': [],
            'accounts': [],
            'company_numbers': []
        }
        
        for i in range(count):
            company_number = self.generate_company_number(f"{i+1:02d}")
            company_name = f"BULK TEST COMPANY {i+1:03d} LIMITED"
            
            # Generate config
            config = self.generate_config(
                config_type="complete",
                company_number=company_number,
                **{"company-name": company_name}
            )
            data['configs'].append(config)
            
            # Generate accounts
            accounts_html = self.generate_accounts_html(
                company_number, 
                company_name,
                random.choice(["micro", "small"])
            )
            data['accounts'].append(accounts_html)
            data['company_numbers'].append(company_number)
        
        return data
    
    def save_test_data(self, data: Union[Dict, str], filename: str, subdir: str = ""):
        """Save test data to file"""
        output_path = self.output_dir
        if subdir:
            output_path = output_path / subdir
            output_path.mkdir(exist_ok=True)
        
        file_path = output_path / filename
        
        if isinstance(data, dict):
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
        else:
            with open(file_path, 'w') as f:
                f.write(data)
        
        return file_path


if __name__ == "__main__":
    # Example usage and test data generation
    generator = TestDataGenerator()
    
    # Generate various test configurations
    configs = {
        'minimal': generator.generate_config('minimal'),
        'complete': generator.generate_config('complete'),
        'micro': generator.generate_config('micro'),
        'invalid': generator.generate_config('invalid')
    }
    
    print("Generated test configurations:")
    for config_type, config in configs.items():
        print(f"\n{config_type.upper()}:")
        for key, value in config.items():
            print(f"  {key}: {value}")
    
    # Generate sample accounts
    company_num = generator.generate_company_number()
    company_name = "GENERATED TEST COMPANY LIMITED"
    accounts_html = generator.generate_accounts_html(company_num, company_name)
    
    print(f"\nGenerated accounts HTML for {company_name} ({company_num})")
    print(f"Length: {len(accounts_html)} characters")
    
    # Generate bulk data
    bulk_data = generator.generate_bulk_test_data(5)
    print(f"\nGenerated bulk test data:")
    print(f"  Configs: {len(bulk_data['configs'])}")
    print(f"  Accounts files: {len(bulk_data['accounts'])}")
    print(f"  Company numbers: {bulk_data['company_numbers']}")