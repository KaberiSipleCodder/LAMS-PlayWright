"""
Sample "New Wind Project" data - matches the exact values shown in the
Add New Land Proposal screenshots.

Any field set to None is intentionally skipped (either it's auto-calculated
by the page, like Decimal Latitude/Longitude and the Total land quantum).
Required form fields (Document Variant, Document File) must NOT be None -
the page rejects the submit otherwise.
"""

import os

_HERE = os.path.dirname(os.path.abspath(__file__))

WIND_PROJECT_DATA = {
    # ---- Land Bank Details ----
    "proposal_name": "New Wind Project",
    "company": "Heritage Builders pvt.ltd",
    "project_type": "Wind",
    "land_type": "Commercial",
    "state": "Bihar",
    "district": "Aurangabad",
    "taluka": "Aurangabad",
    "village": "Aranda",

    # ---- Land Co-ordinates ----
    "latitude_degree": "22",
    "latitude_minutes": "34",
    "latitude_seconds": "10",
    "latitude_direction": "North",
    "longitude_degree": "88",
    "longitude_minutes": "12",
    "longitude_seconds": "15",
    "longitude_direction": "East",
    "substation": "Durgapur Substation",
    "ctu_stu": "CTU",

    # ---- Sub-Station Co-ordinates ----
    "sub_station_latitude_degree": "22",
    "sub_station_latitude_minutes": "34",
    "sub_station_latitude_seconds": "10",
    "sub_station_latitude_direction": "North",
    "sub_station_longitude_degree": "88",
    "sub_station_longitude_minutes": "22",
    "sub_station_longitude_seconds": "15",
    "sub_station_longitude_direction": "East",

    # ---- Additional Details ----
    "tl_distance_km": "45",
    "ss_evacuation_capacity_mw": "100",
    "voltage_level_kv": "132",
    "ss_readiness": "Ready",
    "land_quantum_offered_lease": "50",
    "land_quantum_offered_purchase": "30",
    "connectivity_status": "Connected",
    "quantum_of_connectivity": "50",
    "remarks": "Land and substation connectivity available.",

    # ---- Document Section ----
    "document_type": "Application Document",
    # Required (red asterisk). Options are "Original" / "Certified True Copy".
    # Leaving this None makes the page reject the submit with
    # "Please select document variant".
    "document_variant": "Original",
    "physical_file_location": "location",
    "document_title": "label",
    # Required too - the form errors with "Please upload document" if empty.
    # Built from this file's location so it stays absolute and portable.
    "document_file_path": os.path.join(_HERE, "test_data", "sample_document.pdf"),

    # ---- Step 2: Technical Team ----
    # Field names confirmed from the live DOM (all tlbet_*).
    # Numeric ranges implied by the labels: Ease of Acquisition 0-10,
    # Albedo / PLF 0-1 - keep test values inside them.
    # Shape Index server-validates as INTEGER ("Shape Index must be
    # integer") - a decimal like 0.85 rejects the whole Step 2 submit.
    "plant_size_mw": "50",
    "land_quantum_usable_acres": "75",
    "shape_index": "1",
    "fit_for_tracker": "Yes",
    "site_visit_status": "Completed",
    # <input type="date">: Playwright fills ISO yyyy-mm-dd (the UI shows
    # dd-mm-yyyy, but fill() requires the ISO form).
    "site_visit_date": "2026-09-20",
    "ease_of_acquisition": "7",
    "ghi": "1850",
    "albedo": "0.25",
    "dc_feasible": "40",
    "energy_yield": "12500",
    "plf_of_plant": "0.28",
    "environment_study_status": "Completed",
    "go_no_go_environment_team": "Yes",
    "go_no_go_engineering_team": "Yes",

    # ---- Step 3: Commercial/Financial Details ----
    # Field names confirmed from the live DOM (all tlbbt_*).
    # Plain integer values everywhere: Step 2's Shape Index showed this
    # app server-validates numeric types ("must be integer"), so decimals
    # are only used where the field conceptually requires them.
    "basic_cost_sale": "500000",
    "basic_cost_lease": "200000",
    "stamp_duty_reg_charges_sale": "50000",
    "stamp_duty_reg_charges_lease": "20000",
    "other_statutory_charges": "10000",
    "service_fee_sale": "25000",
    "service_fee_lease": "15000",
    "lease_tenure_years": "30",
    "lease_escalation_rate": "5",
    "lease_escalation_frequency_years": "2",
    "total_land_cost_for_bd": "760000",
    "service_fee": "40000",
    "commercial_negotiation": "Completed",
    "land_cost_for_bd": "760000",
    "land_being_considered_for": "Lease",
    "tariff_due_to_this_land": "4",
}
