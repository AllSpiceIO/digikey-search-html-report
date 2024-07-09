#! /usr/bin/env python3

from jinja2 import Environment, FileSystemLoader
from argparse import ArgumentParser
from contextlib import ExitStack
import requests
import zipfile
import shutil
import json
import csv
import os

DIGIKEY_API_URL_BASE = "https://api.digikey.com"
DIGIKEY_API_AUTH_ENDPOINT = DIGIKEY_API_URL_BASE + "/v1/oauth2/token"
DIGIKEY_API_V4_KEYWORD_SEARCH_ENDPOINT = (
    DIGIKEY_API_URL_BASE + "/products/v4/search/keyword"
)


################################################################################
class ComponentData:
    def __init__(self):
        self.associated_refdes = ""
        self.part_description = None
        self.mfr_name = None
        self.mfr_part_number = None
        self.photo_url = None
        self.datasheet_url = None
        self.product_url = None
        self.qty_available = None
        self.lifecycle_status = None
        self.eol_status = None
        self.discontinued_status = None
        self.pricing = None
        self.package_case = None
        self.supplier_device_package = None
        self.operating_temp = None
        self.xy_size = None
        self.height = None
        self.thickness = None


################################################################################
def get_access_token(url, client_id, client_secret):
    # Populate request header
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
    }
    # Post the request and get the response
    response = requests.post(
        url,
        data={"grant_type": "client_credentials"},
        headers=headers,
        auth=(client_id, client_secret),
    )
    # Populate the access token return value
    access_token = (
        response.json()["access_token"] if response.status_code == 200 else None
    )
    # Return response status code and access token
    return (response.status_code, access_token)


################################################################################
def query_digikey_v4_API_keyword_search(
    url,
    client_id,
    access_token,
    locale_site,
    locale_language,
    locale_currency,
    customer_id,
    keyword,
):
    # Populate request header
    headers = {
        "charset": "utf-8",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": "Bearer " + access_token,
        "X-DIGIKEY-Client-Id": client_id,
        "X-DIGIKEY-Locale-Site": locale_site,
        "X-DIGIKEY-Locale-Language": locale_language,
        "X-DIGIKEY-Locale-Currency": locale_currency,
        "X-DIGIKEY-Customer-Id": customer_id,
    }
    # Populate request data
    request_data = {
        "Keywords": keyword,
    }
    # Post the request and get the response
    response = requests.post(
        url,
        data=str(json.dumps(request_data)),
        headers=headers,
    )
    # Populate the search result return value
    keyword_search_json = (
        response.json() if response.status_code == 200 else response.text
    )
    # Return response status code and search result
    return (response.status_code, keyword_search_json)


################################################################################
def extract_data_from_digikey_search_response(keyword_search_json):
    # Initialize a component data object to store the extracted info
    part_data = ComponentData()
    # Extract product data from exact match
    product_data = (
        (keyword_search_json["ExactMatches"])[0]
        if keyword_search_json["ExactMatches"]
        else None
    )
    # If the product data matched with valid results, process the line item
    if product_data:
        # Get the product description
        part_data.part_description = product_data["Description"]["ProductDescription"]
        # Get the manufacturer name
        part_data.mfr_name = product_data["Manufacturer"]["Name"]
        # Get the manufacturer part number
        part_data.mfr_part_number = product_data["ManufacturerProductNumber"]
        # Save the photo from the photo URL
        part_data.photo_url = product_data["PhotoUrl"]
        # Get the datasheet URL
        part_data.datasheet_url = product_data["DatasheetUrl"]
        # Get the product URL
        part_data.product_url = product_data["ProductUrl"]
        # Get the in stock quantity
        part_data.qty_available = product_data["QuantityAvailable"]
        # Get the part lifecycle, EOL, and discontinued status
        part_data.lifecycle_status = product_data["ProductStatus"]["Status"]
        part_data.eol_status = product_data["EndOfLife"]
        part_data.discontinued_status = product_data["Discontinued"]
        # Get the pricing information
        part_data.pricing = product_data["ProductVariations"]
        # Remove Digi-Reel and rename as DR/CT if both Digi-Reel and Cut-Tape exist
        pricing_variations = [
            variation["PackageType"]["Name"] for variation in part_data.pricing
        ]
        cut_tape_idx = digi_reel_idx = [
            i
            for i in range(0, len(pricing_variations))
            if "Cut Tape" in pricing_variations[i]
        ]
        digi_reel_idx = [
            i
            for i in range(0, len(pricing_variations))
            if "Digi-Reel" in pricing_variations[i]
        ]
        if cut_tape_idx and digi_reel_idx:
            part_data.pricing[cut_tape_idx[0]]["PackageType"]["Name"] = (
                "Cut Tape (CT) & Digi-Reel®"
            )
            del part_data.pricing[digi_reel_idx[0]]
        # Initialize part parameter variables
        part_data.package_case = part_data.supplier_device_package = (
            part_data.operating_temp
        ) = part_data.xy_size = part_data.height = part_data.thickness = None
        # Get product parameter information
        for parameter in product_data["Parameters"]:
            if "ParameterText" in parameter.keys():
                # Get the package / case
                if parameter["ParameterText"] == "Package / Case":
                    part_data.package_case = parameter["ValueText"]
                # Get the supplier device package
                if parameter["ParameterText"] == "Supplier Device Package":
                    part_data.supplier_device_package = parameter["ValueText"]
                # Get the operating temperature range
                if parameter["ParameterText"] == "Operating Temperature":
                    part_data.operating_temp = parameter["ValueText"]
                # Get the package XY dimensions
                if "Size" in parameter["ParameterText"]:
                    part_data.xy_size = parameter["ValueText"]
                # Get the package height or thickness
                if "Height" in parameter["ParameterText"]:
                    part_data.height = parameter["ValueText"]
                if "Thickness" in parameter["ParameterText"]:
                    part_data.thickness = parameter["ValueText"]

    # Return the extracted part data
    return part_data


################################################################################
if __name__ == "__main__":
    # Initialize argument parser
    parser = ArgumentParser()
    parser.add_argument("bom_file", help="Path to the BOM file")
    parser.add_argument(
        "--output_path", help="Path to the directory to output report to"
    )
    args = parser.parse_args()

    # Read the BOM file into list
    with open(args.bom_file, newline="") as bomfile:
        # Comma delimited file with " as quote character to be included
        bomreader = csv.reader(bomfile, delimiter=",", quotechar='"')
        # Save as a list
        bom_line_items = list(bomreader)
        # Save the index of the designator field
        refdes_col_idx = (bom_line_items[0]).index("Designator")
        # Skip the header
        del bom_line_items[0]

    # Authenticate with DigiKey
    digikey_client_id = os.environ.get("DIGIKEY_CLIENT_ID")
    digikey_client_secret = os.environ.get("DIGIKEY_CLIENT_SECRET")
    (response_code, access_token) = get_access_token(
        DIGIKEY_API_AUTH_ENDPOINT, digikey_client_id, digikey_client_secret
    )

    # Initialize list of BOM item part data
    bom_items_digikey_data = []

    # Fetch information for all parts in the BOM
    for line_item in bom_line_items:
        print("- Fetching info for " + line_item[0])
        # Search for parts in DigiKey by Manufacturer Part Number as keyword
        (response_code, keyword_search_json) = query_digikey_v4_API_keyword_search(
            DIGIKEY_API_V4_KEYWORD_SEARCH_ENDPOINT,
            digikey_client_id,
            access_token,
            "US",
            "en",
            "USD",
            "0",
            line_item[0],
        )
        # Process a successful response
        if response_code == 200:
            # Extract the part data from the keyword search response
            part_data = extract_data_from_digikey_search_response(keyword_search_json)
            # Add the associated reference designators
            part_data.associated_refdes = line_item[refdes_col_idx]
            # Add the extracted data to the list of BOM items part data
            bom_items_digikey_data.append(part_data)
        # Print out the details of an unsuccessful response
        else:
            print(response_code, keyword_search_json)

    # Load Jinja with output HTML template
    template_env = Environment(loader=FileSystemLoader("/report_template/"))
    template = template_env.get_template("index.html")
    # Populuate the context data
    context = {"bom": bom_items_digikey_data}
    # Create report output folder if it doesn't exist
    try:
        os.makedirs("/component_report")
    except FileExistsError:
        pass
    # Unzip the JS/CSS assets
    shutil.unpack_archive("/report_template/assets.zip", "/component_report")
    # Write HTML output file
    with ExitStack() as stack:
        report_file = stack.enter_context(
            open("/component_report/index.html", mode="w", encoding="utf-8")
        )
        print("- Outputting report")
        report_file.write(template.render(context))
    # Zip the component report as a git workspace artifact
    with zipfile.ZipFile(
        args.output_path + "/component_report.zip", "w", zipfile.ZIP_DEFLATED
    ) as zipper:
        for root, dirs, files in os.walk("/component_report"):
            for file in files:
                zipper.write(os.path.join(root, file))
