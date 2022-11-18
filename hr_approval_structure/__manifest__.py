{
    'name': 'HR Approval Structure',
    'version': '15.0.1.0.0',
    'category': 'Human Resources/Recruitment',
    'summary': 'Dynamic HR Approval Structure',
    'author': "Mohamed Saber",
    'license': 'AGPL-3',
    'depends': ['base','mail','hr',],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/mail_template.xml',
        'views/hr_authorization_approval_template.xml',
        'views/hr_authorization_approval.xml',
    ],
}
