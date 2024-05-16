
import sys
import argparse
from lxml import objectify

from ch_filing.client import *
from ch_filing.state import State
from ch_filing.company_data import CompanyData
from ch_filing.envelope import Envelope
from ch_filing.form_submission import Accounts
from ch_filing.submission_status import SubmissionStatus

def main():

    # Command-line argument parser
    parser = argparse.ArgumentParser(
        description="Submittion to Companies house API"
    )
    parser.add_argument('--config', '-c',
                        default='config.json',
                        help='Configuration file (default: config.json)')
    parser.add_argument('--state', '-s',
                        default='state.json',
                        help='Transaction counter state (default: state.json)')
    parser.add_argument('--accounts', '-a', 
                        help='Company accounts iXBRL file')
    parser.add_argument('--get-company-data', '-C',
                        action="store_true", default=False,
                        help='Get company details, to check the authentication')
    parser.add_argument('--submit-accounts', '-S',
                        action="store_true", default=False,
                        help='Submit company accounts')
    parser.add_argument('--get-submission-status', '-G',
                        action="store_true", default=False,
                        help='Get status of previous filing')
    parser.add_argument('--accounts-image',
                        action="store_true", default=False,
                        help='Get accounts image')
    parser.add_argument('--submission-id', '-i',
                        help='Submission ID of previous filing')

    # Parse arguments
    args = parser.parse_args(sys.argv[1:])

    try:

        st = State(args.config, args.state)

        cli = Client(st)

        if args.get_company_data:

            content = CompanyData.create_request(st)
            env = Envelope.create(st, content, "CompanyDataRequest", "request")
            renv = cli.call(st, env)
            cd = renv.Body.CompanyData

            print("Company:", cd.CompanyName)
            print("Number:", cd.CompanyNumber)
            print("Category:", cd.CompanyCategory)
            print("Jurisdiction:", cd.Jurisdiction)
            print("Trading on market:", "yes" if cd.TradingOnMarket else "no")
            print("Made up date:", cd.MadeUpDate)
            print("Next due date:", cd.NextDueDate)

            print("Registered Office:")
            print("  Premise:", cd.RegisteredOfficeAddress.Premise)
            print("  Street:", cd.RegisteredOfficeAddress.Street)
            try:
                print("  Thoroughfare:", cd.RegisteredOfficeAddress.Thoroughfare)
            except:
                pass
            print("  Post town:", cd.RegisteredOfficeAddress.PostTown)
            print("  Postcode:", cd.RegisteredOfficeAddress.Postcode)
            print("  Country:", cd.RegisteredOfficeAddress.Country)

            print("SIC codes:", ", ".join([
                v.text for v in cd.SICCodes.SICCode
            ]))

        elif args.submit_accounts:

            if args.accounts:
                data = open(args.accounts).read()
            else:
                raise RuntimeError("--accounts must be specified")

            content = Accounts.create_submission(st, args.accounts, data)
            sub_id = content.FormHeader.SubmissionNumber.text
            env = Envelope.create(st, content,
                                  content.FormHeader.FormIdentifier.text,
                                  "request")
            renv = cli.call(st, env)
            print("Submission completed.")
            print("Submission ID is:", sub_id)

        elif args.get_submission_status:

            if args.submission_id:
                content = SubmissionStatus.create_request(st, args.submission_id)
            else:
                content = SubmissionStatus.create_request(st)

            env = Envelope.create(st, content, "GetSubmissionStatus", "request")
            renv = cli.call(st, env)

            for status in renv.Body.SubmissionStatus.Status:
                print("%s: %s" % (status.SubmissionNumber, status.StatusCode))

        elif args.accounts_image:

            if args.accounts:
                data = open(args.accounts).read()
            else:
                raise RuntimeError("--accounts must be specified")

            content = Accounts.create_submission(st, args.accounts, data)

            env = Envelope.create(st, content, "AccountsImage", "request")
            renv = cli.call(st, env)

            data = renv.Body
            print(str(data))

        else:

            raise RuntimeError("Need to specify an operation to perform.")

    except AuthenticationFailure as e:
        print("Exception:", e)
        print("Check your configuration to ensure the company number, and "
              "authentication code")
        print("are correct.")
    except RequestFailure as e:
        print("Exception:", e)
        print("Request could not be completed.  Service problems suspected.")
        print("Try again later?")
    except SuspectedAccountsCorruption as e:
        print("Exception:", e)
        print("Suspected error in submitted account data.")
    except SuspectedValidationFailure as e:
        print("Exception:", e)
        print("Suspected error in submitted message.  Failed validation check?")
    except PrivacyFailure as e:
        print("Exception:", e)
        print("Failure in security transport!  Host certificate may be invalid.")
    except Exception as e:
        print("Exception:", e)


if __name__ == "__main__":
    main()

