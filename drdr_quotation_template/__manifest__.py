# -*- coding: utf-8 -*-
{
    'name': "drdr_quotation_template",

    'summary': """
        Short (1 phrase/line) summary of the module's purpose, used as
        subtitle on modules listing or apps.openerp.com""",

    'description': """
        Long description of module's purpose
    """,

    'author': "Gourida Said",
    'website': "http://www.crea-tech.tech",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base','ps_quotation_template'],

    # always loaded
    'data': [
        'views/company.xml',
        'report/action_report.xml',
        'report/inherit_external_layout_sale.xml',
        'report/inherit_ps_sale_report_document.xml',
        'report/inherit_ps_sale_report_document_ar.xml'
    ],
    'assets': {
        'web.report_assets_pdf': [ 
            "/drdr_quotation_template/static/src/css/report.css"
        ],

    },
    'installable': True,
    'application': True,
    'license': "AGPL-3",
}
