#! /usr/bin/env python3

from jinja2 import Environment, FileSystemLoader
from argparse import ArgumentParser
from dataclasses import dataclass, field
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
@dataclass
class ComponentData:
    associated_refdes: str = ""
    part_description: str = None
    mfr_name: str = None
    mfr_part_number: str = None
    photo_url: str = None
    datasheet_url: str = None
    product_url: str = None
    qty_available: str = None
    lifecycle_status: str = None
    eol_status: str = None
    discontinued_status: str = None
    pricing: str = None
    package_case: str = None
    supplier_device_package: str = None
    operating_temp: str = None
    xy_size: str = None
    height: str = None
    thickness: str = None
    ratings: str = None
    grade: str = None
    qualification: str = None
    rohs_status: str = None
    moisture_sensitivity_level: str = None
    reach_status: str = None
    eccn: str = None
    htsus: str = None
    categories: list = field(default_factory=list)
    cogs_breakdown: list = field(default_factory=list)


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
        ) = part_data.xy_size = part_data.height = part_data.thickness = (
            part_data.ratings
        ) = part_data.qualifications = part_data.grade = None
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
                if "Dimension" in parameter["ParameterText"]:
                    part_data.xy_size = parameter["ValueText"]
                # Get the package height or thickness
                if "Height" in parameter["ParameterText"]:
                    part_data.height = parameter["ValueText"]
                if "Thickness (Max)" in parameter["ParameterText"]:
                    part_data.thickness = parameter["ValueText"]
                # Get the component ratings
                if "Ratings" in parameter["ParameterText"]:
                    part_data.ratings = parameter["ValueText"]
                # Get the component grade
                if "Grade" in parameter["ParameterText"]:
                    part_data.grade = parameter["ValueText"]
                # Get the component qualification
                if "Qualification" in parameter["ParameterText"]:
                    part_data.qualification = parameter["ValueText"]
        # Get environmental and classification data
        try:
            part_data.rohs_status = product_data["Classifications"]["RohsStatus"]
            part_data.moisture_sensitivity_level = product_data["Classifications"][
                "MoistureSensitivityLevel"
            ]
            part_data.reach_status = product_data["Classifications"]["ReachStatus"]
            part_data.eccn = product_data["Classifications"]["ExportControlClassNumber"]
            part_data.htsus = product_data["Classifications"]["HtsusCode"]
        except KeyError:
            pass
        # Get the category chain
        part_data.categories.append(product_data["Category"]["Name"])
        child_categories = product_data["Category"]["ChildCategories"]
        while True:
            if child_categories:
                part_data.categories.append(child_categories[0]["Name"])
                child_categories = child_categories[0]["ChildCategories"]
            else:
                break

    # Return the extracted part data
    return part_data


################################################################################
def get_prices_for_target_qtys(part_data, single_pcb_part_qty, pcb_quantities):
    # Initialize list of prices to populate and return
    pcb_qty_prices_by_part_type = []
    # Iterate through list of quantities and pricing data if pricing data exists
    if part_data.pricing:
        for pricing_type in part_data.pricing:
            # Get the standard pricing for this package type
            std_pricing = pricing_type["StandardPricing"]
            # Process the pricing type if data exists, else skip
            if std_pricing:
                # Initialize a pricing dictionary and populate package type
                pricing_for_price_type = {}
                pricing_for_price_type["package_type"] = pricing_type["PackageType"]
                pricing_for_price_type["cogs"] = []
                # Get price breakpoints for this pricing type
                breakpoints = [
                    int(stdpricing["BreakQuantity"]) for stdpricing in std_pricing
                ]
                # Iterate through the PCB quantities for COGS breakdown
                for pcb_qty in pcb_quantities:
                    # Get the total part count for this PCB quantity
                    part_qty = single_pcb_part_qty * pcb_qty
                    # Initialize a dict for populating COGS for this PCB quantity
                    pricing_for_pcb_qty = {
                        "pcb_qty": pcb_qty,
                        "total_part_qty": part_qty,
                    }
                    # Set the breakpoint index to start or end of list, or as None,
                    # depending on the quantity. Set pricing for edge case
                    breakpoint_idx = (
                        0
                        if part_qty <= min(breakpoints)
                        else -1
                        if part_qty >= max(breakpoints)
                        else None
                    )
                    if breakpoint_idx is not None:
                        pricing_for_pcb_qty["break_qty"] = std_pricing[breakpoint_idx][
                            "BreakQuantity"
                        ]
                        pricing_for_pcb_qty["price_per_unit"] = std_pricing[
                            breakpoint_idx
                        ]["UnitPrice"]
                        pricing_for_pcb_qty["total_price"] = (
                            std_pricing[breakpoint_idx]["UnitPrice"] * part_qty
                        )
                    else:
                        # Populate break quantity and prices the target quantity
                        for breakpoint in std_pricing:
                            # If breakpoint index already set, populate
                            if part_qty >= breakpoint["BreakQuantity"]:
                                pricing_for_pcb_qty["break_qty"] = breakpoint[
                                    "BreakQuantity"
                                ]
                                pricing_for_pcb_qty["price_per_unit"] = breakpoint[
                                    "UnitPrice"
                                ]
                                pricing_for_pcb_qty["total_price"] = (
                                    breakpoint["UnitPrice"] * part_qty
                                )
                    # Append the pricing for this PCB quantity to the list
                    pricing_for_price_type["cogs"].append(pricing_for_pcb_qty)
                # Add pricing dict to the list of pricing types
                pcb_qty_prices_by_part_type.append(pricing_for_price_type)
    # Return the populated pricing data
    return pcb_qty_prices_by_part_type


################################################################################
if __name__ == "__main__":
    # Initialize argument parser
    parser = ArgumentParser()
    parser.add_argument("bom_file", help="Path to the BOM file")
    parser.add_argument(
        "--refdes_column", help="Name of the reference designator column in the BOM"
    )
    parser.add_argument(
        "--part_number_column",
        help="Name of the manufacturer part number column in the BOM",
    )
    parser.add_argument(
        "--output_path", help="Path to the directory to output report to"
    )
    parser.add_argument(
        "--pcb_quantities",
        help=(
            "A comma-separated list of quantities of PCBs to compute the COGS "
            + "for. Defaults to '%(default)s'."
        ),
        default="1,10,100,500,1000",
    )
    parser.add_argument(
        "--report_type",
        choices=("html", "md"),
        help=(
            "Report type as html or md. html reports are uploaded as artifacts"
            + " to the Action run whereas md reports are added to the"
            + " repository's Wiki. Defaults to html."
        ),
        default="html",
        const="html",
        nargs="?",
    )
    args = parser.parse_args()

    refdes_column = args.refdes_column
    part_number_column = args.part_number_column
    if not refdes_column:
        raise ValueError(
            "Reference designator column name needs to be specified. Please set refdes_column."
        )
    if not part_number_column:
        raise ValueError(
            "Manufacturer part number column name needs to be specified. Please set part_number_column."
        )

    # Read the BOM file into list
    with open(args.bom_file, newline="") as bomfile:
        # Comma delimited file with " as quote character to be included
        bomreader = csv.reader(bomfile, delimiter=",", quotechar='"')
        # Save as a list
        bom_line_items = list(bomreader)
        # Save the index of the designator and manufacturer part number field
        refdes_col_idx = (bom_line_items[0]).index(refdes_column)
        mfg_pn_col_idx = (bom_line_items[0]).index(part_number_column)
        # Skip the header
        del bom_line_items[0]

    # Get the PCB quantities, if specified
    pcb_quantities = []
    if args.pcb_quantities:
        try:
            # Get the quantities as a list of integers
            pcb_quantities = [
                int(quantity) for quantity in args.pcb_quantities.split(",")
            ]
        except Exception:
            pass

    # Authenticate with DigiKey
    digikey_client_id = os.environ.get("DIGIKEY_CLIENT_ID")
    digikey_client_secret = os.environ.get("DIGIKEY_CLIENT_SECRET")
    (response_code, access_token) = get_access_token(
        DIGIKEY_API_AUTH_ENDPOINT, digikey_client_id, digikey_client_secret
    )

    # Cannot proceed with search API queries if authentication failed,
    # exit gracefully.
    if response_code != 200:
        print("Authentication failed. Response from server:")
        print(access_token)
        print("Exiting...")

    # Initialize list of BOM item part data
    bom_items_digikey_data = []

    # Fetch information for all parts in the BOM
    for line_item in bom_line_items:
        num_retries = 3
        while num_retries > 0:
            print("- Fetching info for " + line_item[0] + "... ", end="")
            # Search for parts in DigiKey by Manufacturer Part Number as keyword
            (response_code, keyword_search_json) = query_digikey_v4_API_keyword_search(
                DIGIKEY_API_V4_KEYWORD_SEARCH_ENDPOINT,
                digikey_client_id,
                access_token,
                "US",
                "en",
                "USD",
                "0",
                line_item[mfg_pn_col_idx],
            )
            # Process a successful response
            if response_code == 200:
                print("✅" + "\n", end="", flush=True)
                # Extract the part data from the keyword search response
                part_data = extract_data_from_digikey_search_response(
                    keyword_search_json
                )
                # Add the associated reference designators
                part_data.associated_refdes = line_item[refdes_col_idx]
                # Get the COGS pricing if PCB quantities specified
                if args.pcb_quantities:
                    # Get the number of components needed for this part
                    part_qty = len(part_data.associated_refdes.split(","))
                    # Initialize a COGS breakdown dict for the different quantities
                    cogs_breakdown = {}
                    # Iterate PCB quantities and get prices for component quantities
                    # at each PCB quantity. Add COGS breakdown to the component data set
                    part_data.cogs_breakdown = get_prices_for_target_qtys(
                        part_data, part_qty, pcb_quantities
                    )
                # Add the extracted data to the list of BOM items part data
                bom_items_digikey_data.append(part_data)
                # No need for retries
                break
            # Print out the details of an unsuccessful response
            else:
                print("⛔ (" + str(response_code) + ")\n", end="", flush=True)
            # Retry
            num_retries -= 1

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
    with open(
        "/component_report/index.html", mode="w", encoding="utf-8"
    ) as report_file:
        print("- Outputting report")
        report_file.write(template.render(context))
    # Zip the component report as a git workspace artifact
    with zipfile.ZipFile(
        args.output_path + "/component_report.zip", "w", zipfile.ZIP_DEFLATED
    ) as zipper:
        for root, dirs, files in os.walk("/component_report"):
            for file in files:
                zipper.write(os.path.join(root, file))
    # Convert all ComponentData objects in the BOM items DigiKey data
    # list to dictionaries in preparation for JSON output
    for idx in range(0, len(bom_items_digikey_data)):
        bom_items_digikey_data[idx] = bom_items_digikey_data[idx].__dict__
    # Output the BOM items DigiKey data as a json file
    with open(
        "digikey_data_from_bom.json", mode="w", encoding="utf-8"
    ) as json_output_file:
        json_output_file.write(json.dumps(bom_items_digikey_data, indent=2))
