# DigiKey-Search-HTML-Report
An actions repository for demonstrating DigiKey API integration and HTML report generation given an input BOM

This action uses the DigiKey API.  See the [DigiKey API docs](https://developer.digikey.com/products) for more information.

## Usage

Add the following step to your actions:

```yaml
- name: Generate HTML component report using DigiKey API
  uses: https://hub.allspice.io/Actions/digikey-search-html-report.git@v3
  with:
    bom_file: bom.csv
    digikey_client_id: ${{ secrets.DIGIKEY_CLIENT_ID }}
    digikey_client_secret: ${{ secrets.DIGIKEY_CLIENT_SECRET }}
```

This add-on requires the DigiKey client ID and client secret to be stored as Actions secrets. Refer to the [knowledge base article on Actions secrets](https://learn.allspice.io/docs/secrets#actions-secrets) to learn how to add the required secrets to your repository.

## Input BOM

The input BOM to this Action is assumed to be generated from the py-allspice BOM generation utility. The column names referenced and used in this Action script assume the naming convention as populated by the py-allspice BOM generation function. The user is to adjust the expected column positions and naming conventions when using their own BOM file input.

A typical workflow is to use the [BOM generation Actions add-on](https://hub.allspice.io/Actions/generate-bom) to generate the BOM first, and use the generated BOM as an input to this Action.
