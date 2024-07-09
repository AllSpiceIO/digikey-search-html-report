# DigiKey-Reports
An actions repository for DigiKey API integration and report generation given an input BOM

This action uses the DigiKey API.  See the [DigiKey API docs](https://developer.digikey.com/products) for more information.

## Usage

Add the following step to your actions:

```yaml
- name: Generate BOM report using DigiKey
  uses: https://hub.allspice.io/Actions/digikey-report@v1
  with:
    bom_file: bom.csv
    digikey_client_id: ${{ secrets.DIGIKEY_CLIENT_ID }}
    digikey_client_secret: ${{ secrets.DIGIKEY_CLIENT_SECRET }}
```
