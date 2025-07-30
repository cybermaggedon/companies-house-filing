
# `gnucash-ch-filing`

[![CI](https://github.com/cybermaggedon/gnucash-ch-filing/workflows/Continuous%20Integration/badge.svg)](https://github.com/cybermaggedon/gnucash-ch-filing/actions/workflows/ci.yaml)
[![Test PR](https://github.com/cybermaggedon/gnucash-ch-filing/workflows/Test%20pull%20request/badge.svg)](https://github.com/cybermaggedon/gnucash-ch-filing/actions/workflows/pull-request.yaml)
[![PyPI version](https://badge.fury.io/py/gnucash-ch-filing.svg)](https://badge.fury.io/py/gnucash-ch-filing)
[![Python versions](https://img.shields.io/pypi/pyversions/gnucash-ch-filing.svg)](https://pypi.org/project/gnucash-ch-filing/)
[![License](https://img.shields.io/github/license/cybermaggedon/gnucash-ch-filing.svg)](https://github.com/cybermaggedon/gnucash-ch-filing/blob/master/LICENSE)

## Introduction

Very partial implementation of the Companies House Software Filing interface.
There is enough support to file company accounts.

This utility is designed to take a UK company accounts file formatted using
[`gnucash-ixbrl`](https://github.com/cybermaggedon/gnucash-ixbrl) and
submits in accordance with the Software Filing API.

`gnucash-ch-filing` presently understands a small subset of the accounts
management process, and may be useful for a small business with simple
accounting affairs. It really is no use to a complex business.

## Status

This is a command-line utility, which has been tested with the
Software Filing API.

## Credentials

In order to use this, you need production credentials (presenter ID,
authentication value and the company authentication code) for the company
you are filing for.

Companies House documentation:
- [Software Filing](https://www.gov.uk/government/organisations/companies-house/about-our-services#software-filing)
- [Developer information](http://xmlgw.companieshouse.gov.uk/SchemaStatus)

## Installing

```
pip3 install git+https://github.com/cybermaggedon/gnucash-ch-filing
```

## Testing

I can't share my test credentials with you, you would need to email
Companies House to get some.

You need to edit the `config.json` file to contain the right details for
you.  Check the credentials work by fetching company information:

```
% ch-filing --get-company-data
```

Company accounts should be an iXBRL file which conforms to the CH
accepted taxonomies.  Once you are ready to file:

```
% ch-filing --submit-accounts --accounts accts.html
```

You get a submission ID in return.  To check the process of the submitted
accounts:
```
% ch-filing --get-submission-status -i S00027
S00027: PENDING
```

## Usage

```
usage: ch-filing [-h] [--config CONFIG] [--state STATE] [--accounts ACCOUNTS]
                 [--get-company-data] [--submit-accounts]
                 [--get-submission-status] [--submission-id SUBMISSION_ID]

Submittion to HMRC Corporation Tax API

optional arguments:
  -h, --help            show this help message and exit
  --config CONFIG, -c CONFIG
                        Configuration file (default: config.json)
  --state STATE, -s STATE
                        Transaction counter state (default: state.json)
  --accounts ACCOUNTS, -a ACCOUNTS
                        Company accounts iXBRL file
  --get-company-data, -C
                        Get company details, to check the authentication
  --submit-accounts, -S
                        Submit company accounts
  --get-submission-status, -G
                        Get status of previous filing
  --submission-id SUBMISSION_ID, -i SUBMISSION_ID
                        Submission ID of previous filing
```

# Licences, Compliance, etc.

## Warranty

This code comes with no warranty whatsoever.  See the [LICENCE](LICENSE) file
for details.  Further, I am not an accountant.  It is possible that this code
could be useful to you in meeting regulatory reporting requirements for your
business.  It is also possible that the software could report misleading
information which could land you in a lot of trouble if used for regulatory
purposes.  Really, you should check with a qualified accountant.

## Licence

Copyright (C) 2021, Cyberapocalypse Limited

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.

