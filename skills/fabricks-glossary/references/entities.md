# Fabricks DWH — Core Business Entities

## Articles (Products)

- **Article**: Product master data with supplier, pricing, classification, and status
- **Article Status codes**: `06`=Phase out, `08`=Liquidation, `09`=Inactive, `15`=Service, `20`=In preparation, `30`=Rental, `40`=Template
- **Row Type**: `0`=Standard article; other values for variants
- **Product Group**: Multi-level classification (L1, L2, L3)
- **Discount Group**: Pricing tier assignment per article
- **Own Brand**: Flag indicating manufacturer vs. reseller brand (`is_own_brand`)
- **OTA (One Time Article)**: Template/single-use articles excluded from regular sales analysis (`is_one_off`)
- **Composed Item**: Kit/bundle containing multiple components
- **BME Taxonomy**: Product classification aligned with parent company group standards

## Customers

- **Customer**: Buyer/client master data including location, payment terms, industry classification
- **Customer Relation**: Contact persons and their relationship to the customer
- **Customer Delivery Address**: Shipping addresses and delivery location information
- **Construction Site Customer**: Project-based customer with a specific job site location
- **Customer Churn**: Prediction of customer attrition risk
- **Customer Drop Sales**: Orders from inactive/dropped customers
- **Customer Minus Sales**: Credit/return orders reducing revenue

## Sales Agents & Organization

- **Sales Agent**: Sales reps with territories, teams, and hierarchy (Sales Manager > Team Leader > Sales Agent)
- **Forced Sales Agent**: Manual override of commission assignment for specific orders
- **Commission Sales Agent**: Agent responsible for commission (may differ from the order creator)
- **Current Sales Agent**: Agent currently assigned to the customer
- **Our Reference (Product Manager)**: Product manager assigned to an article for accountability
- **Cost Center**: Organizational unit for cost allocation and budget control
- **Backoffice Region**: Administrative region for reporting and control
- **Cluster**: Grouping of locations for organizational purposes
- **Distribution Channel**: Sales channel (e.g., direct sales vs. transit/wholesale)

## Inventory

- **ABC Stock Classification**: Article importance ranking by sales volume (A=high, B=medium, C=low)
- **Slim Stock**: Lightweight/optimized inventory snapshot (`core.fact_slim_stock`)
- **Stock Availability**: On-hand stock with fulfillment status codes
- **Stock Assortment**: Product availability across store locations
- **Stock Budget**: Planned inventory investment by period and article
