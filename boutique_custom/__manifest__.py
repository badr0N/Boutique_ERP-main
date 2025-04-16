{
    "name": "Boutique Customize Module",
    "version": "1.0",
    "category": "Customization",
    "description": """
        Custom module for Boutique.
        This module provides additional features and customization for Boutique management.
    """,
    "author": "Budiman Zahri",
    "website": "www.bmz.com",
    "depends": [ 
        "mail",
        "product",
        "purchase",
        "sale",
        "stock",
        "sale_stock"
    ],
    "data": [
        # Security
        'security/security.xml',
        'security/ir.model.access.csv',

        # Wizards
        "wizard/stock_move_detail_package_wizard.xml",

        # Views
        "views/res_partner_views.xml",
        "views/product_views.xml",
        "views/purchase_views.xml",
        "views/sale_views.xml",
        "views/stock_picking_views.xml",

        # Reports
        "report/packing_list_report.xml",

    ],
    "installable": True,
    "application": True,
    "auto_install": False,
    "license": "OPL-1",
}
