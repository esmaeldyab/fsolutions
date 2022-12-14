# -*- coding: utf-8 -*-
#upgraded by Mohamed Saber
{
    'name': 'Standard Accounting Report',
    'version': '15.0.1.0.0',
    'category': 'Accounting',
    'author': 'Florent de Labarre,Mohamed Saber',
    'summary': 'Standard Accounting Report',
    'website': 'https://github.com/fmdl',
    'depends': ['account', 'report_xlsx'],
    'data': [
        'security/ir.model.access.csv',
        'data/report_paperformat.xml',
        'data/res_currency_data.xml',
        'report/report_account_standard_report.xml',
        'report/report_standard_report.xml',
        'views/account_view.xml',
        'views/account_standard.xml',
        'views/account_standard_report_template_view.xml',
        'views/res_currency_views.xml',
        'wizard/account_standard_report_view.xml',
    ],
    'demo': [],
    'license': 'AGPL-3',
    'support': 'https://github.com/fmdl',
    'installable': True,
    'auto_install': False,
    'images': ['images/main_screenshot.png'],
}
