# Series basis and data dictionary

Every market and adjustment series is registered in `data/series_catalog.csv`. The required basis fields prevent unlike prices from being blended silently.

| Field | Meaning |
|---|---|
| `series_id` | Stable identifier used in price observations. |
| `role` | `rack`, `spot_fallback`, `ethanol`, `terminal_basis`, `freight`, or `tax`. |
| `product_grade` | Exact grade/commodity; never merely “gasoline.” |
| `ethanol_spec` | E0, E10, or the quoted blend. |
| `tax_treatment` | Included/excluded and which taxes. |
| `geography` | Pricing point, terminal, or delivery region. |
| `observation_time` | Publication/assessment timing and timezone, or `daily; time not specified by publisher`. |
| `delivery_basis` | FOB, at-rack, delivered, or modeled route. |
| `source` / `source_url` | Publisher and stable provenance link. |
| `reliable` | Governance approval for use as a rack anchor. |

The two configured EIA fallbacks are daily wholesale spot prices in dollars per gallon, FOB at their named market, excluding retail and motor-fuel taxes. `EIA_GC_REG_CONV_E0` is U.S. Gulf Coast conventional regular gasoline (E0/not an ethanol blend specification). `EIA_NYH_RBOB_REG_E0` is New York Harbor regular RBOB (an unblended blendstock intended for oxygenate blending, not finished E10). EIA does not publish an intraday timestamp for these daily series, so the catalog says so instead of inventing one.

The EIA API series identifiers and source pages in the catalog should be checked when an extract is refreshed. Vendor rack inputs must state whether the quote is gross, prompt, branded/unbranded, and tax inclusive in `notes`.

## Input files

`prices.csv` requires `date,region,series_id,value_usd_per_gallon` plus optional `terminal_basis`, `freight`, `ethanol`, and `tax`. Blank is materially different from zero. `history_template.csv` requires fiscal `quarter`, reported margin in cents per gallon, and quarterly means of both EIA series in dollars per gallon.

