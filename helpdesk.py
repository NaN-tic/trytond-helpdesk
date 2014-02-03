# This file is part of the helpdesk module for Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from datetime import datetime
from email import Utils
from email.header import Header
from email.mime.text import MIMEText
from email.utils import parseaddr
from trytond.model import Workflow, ModelView, ModelSQL, fields
from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction
import logging
CHECK_EMAIL = False
try:
    import emailvalid
    CHECK_EMAIL = True
except ImportError:
    logging.getLogger('Helpdesk').warning(
    'Unable to import emailvalid. Email validation disabled.')

__all__ = [
    'Helpdesk', 'HelpdeskTalk', 'HelpdeskLog',
    ]


class Helpdesk(Workflow, ModelSQL, ModelView):
    'Helpdesk'
    __name__ = 'helpdesk'
    name = fields.Char('Description', required=True,
        states={
            'readonly': Eval('state').in_(['cancel', 'done']),
            },
        depends=['state'])
    date = fields.DateTime('Date',
        states={
            'readonly': Eval('state').in_(['cancel', 'done']),
            },
        depends=['state'])
    message = fields.Text('Message',
        states={
            'readonly': Eval('state').in_(['cancel', 'done']),
            },
        depends=['state'])
    priority = fields.Selection([
            ('4', '4-Low'),
            ('3', '3-Normal'),
            ('2', '2-High'),
            ('1', '1-Important'),
            ], 'Priority',
        states={
            'readonly': Eval('state').in_(['cancel', 'done']),
            },
        depends=['state'])
    email_from = fields.Char('Email',
        states={
            'readonly': Eval('state').in_(['cancel', 'done']),
            },
        depends=['state'])
    email_cc = fields.Char('CC',
        states={
            'readonly': Eval('state').in_(['cancel', 'done']),
            },
        depends=['state'])
    create_date = fields.DateTime('Created', readonly=True)
    closed_date = fields.DateTime('Closed', readonly=True)
    state = fields.Selection([
            ('draft', 'Draft'),
            ('open', 'Open'),
            ('pending', 'Pending'),
            ('done', 'Done'),
            ], 'Status', readonly=True)
    party = fields.Many2One('party.party', 'Party',
        on_change=['party', 'email_from'],
        states={
            'readonly': Eval('state').in_(['cancel', 'done']),
            },
        depends=['state'])
    contact = fields.Many2One('party.address', 'Contact',
        domain=[
            ('party', '=', Eval('party')),
            ],
        states={
            'readonly': Eval('state').in_(['cancel', 'done']),
            },
        depends=['party', 'state'])
    employee = fields.Many2One('company.employee', 'Responsible',
        states={
            'readonly': Eval('state').in_(['cancel', 'done']),
            }, depends=['state'])
    talks = fields.One2Many('helpdesk.talk', 'helpdesk',
        'Communication', states={
            'readonly': Eval('state').in_(['cancel', 'done']),
            },
        depends=['state'])
    logs = fields.One2Many('helpdesk.log', 'helpdesk',
        'Logs Helpdesk', readonly=True)
    message_id = fields.Char('Message ID')
    last_talk = fields.Function(fields.DateTime('Last Talk'),
        'get_last_talk')
    num_attach = fields.Function(fields.Integer('Attachments'),
        'get_num_attachments')
    attachments = fields.One2Many('ir.attachment', 'resource', 'Attachments')
    unread = fields.Function(fields.Boolean('Unread'),
        'get_unread', setter='set_unread', searcher='search_unread')
    kind = fields.Selection([
            ('generic', 'Generic'),
            ], 'Kind', readonly=True)

    @classmethod
    def __setup__(cls):
        super(Helpdesk, cls).__setup__()
        cls._order.insert(0, ('priority', 'ASC'))
        cls._order.insert(1, ('date', 'DESC'))
        cls._order.insert(2, ('id', 'DESC'))
        cls._error_messages.update({
                'no_email_from': 'You must put a party email to use this '
                    'action!',
                'no_user': 'You must define a responsible user for this '
                    'helpdesk in order to use this action!',
                'no_message': 'Add a message before send an email or '
                    'note!',
                'no_user_email': 'No E-Mail ID Found for your Company '
                    'address!',
                'no_from_valid': 'Not valid from email!',
                'no_recepients_valid': 'Not valid recepients email!',
                'smtp_error': 'Wrong connection to SMTP server. Email have '
                    'not sent.',
                'no_employee': 'You must select a employee in yours user '
                    'preferences!',
                'send': 'Send',
                'opened': 'Opened',
                'pending': 'Pending',
                'drafted': 'Drafted',
                'closed': 'Closed',
                })
        cls._transition_state = 'state'
        cls._transitions |= set((
                ('draft', 'open'),
                ('draft', 'pending'),
                ('draft', 'done'),
                ('open', 'pending'),
                ('open', 'done'),
                ('pending', 'open'),
                ('pending', 'done'),
                ('done', 'draft'),
                ))
        cls._buttons.update({
                'done': {
                    'invisible': Eval('state') == 'done',
                    },
                'open': {
                    'invisible': ~Eval('state').in_(['draft', 'pending']),
                    },
                'pending': {
                    'invisible': ~Eval('state').in_(['draft', 'open']),
                    },
                'draft': {
                    'invisible': Eval('state') != 'done',
                    },
                'add_reply': {
                    'invisible': Eval('state') != 'open',
                    },
                'talk_note': {
                    'invisible': Eval('state') != 'open',
                    },
                'talk_email': {
                    'invisible': Eval('state') != 'open',
                    },
                })

    @classmethod
    def get_origin(cls):
        Model = Pool().get('ir.model')
        models = ('account.invoice', 'sale.sale', 'stock.shipment.out')
        models = Model.search([
                ('model', 'in', models),
                ])
        return [('', '')] + [(m.model, m.name) for m in models]

    def get_unread(self, name):
        for talk in self.talks:
            if talk.unread:
                return True
        return False

    @classmethod
    def set_unread(cls, helpdesks, name, value):
        HelpdeskTalk = Pool().get('helpdesk.talk')
        for helpdesk in helpdesks:
            HelpdeskTalk.write(helpdesk.talks, {'unread': value})

    @classmethod
    def search_unread(cls, name, clause):
        cursor = Transaction().cursor
        unread = 't' if clause[2] else 'f'
        cursor.execute('''
            SELECT
                h.id
            FROM
                    helpdesk as h
                LEFT JOIN
                    helpdesk_talk as ht
                ON
                    ht.helpdesk = h.id
            WHERE
                ht.unread = '%s'
            GROUP BY
                h.id
            ''' % unread)
        return [('id', 'in', [x[0] for x in cursor.fetchall()])]

    def get_last_talk(self, name):
        Talk = Pool().get('helpdesk.talk')
        talks = Talk.search([
                ('helpdesk', '=', self.id),
                ], order=[('date', 'DESC')], limit=1)
        if talks:
            return talks[0].date

    def get_num_attachments(self, name=None):
        Attachment = Pool().get('ir.attachment')
        attachments = Attachment.search([
                ('resource', '=', 'helpdesk,%s' % self.id),
                ])
        return len(attachments)

    def on_change_party(self):
        Address = Pool().get('party.address')
        Contact = Pool().get('party.contact_mechanism')
        res = {}
        if self.party:
            addresses = Address.search([('party', '=', self.party)])
            for address in addresses:
                res['contact'] = address.id
                if address.email and not self.email_from:
                    res['email_from'] = address.email
                break
            contacts = Contact.search([('party', '=', self.party)])
            if not res.get('email_from'):
                for contact in contacts:
                    if contact.type == 'email':
                        res['email_from'] = contact.email
                        break
        if not res.get('contact'):
            res['contact'] = None
            res['email_from'] = None
        return res

    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def default_priority():
        return '4'

    @staticmethod
    def default_date():
        return datetime.now()

    @staticmethod
    def default_employee():
        User = Pool().get('res.user')
        if Transaction().context.get('employee'):
            return Transaction().context['employee']
        else:
            user = User(Transaction().user)
            if user.employee:
                return user.employee.id

    @staticmethod
    def default_kind():
        return Transaction().context.get('kind', 'generic')

    @classmethod
    def delete(cls, helpdesks):
        Attachment = Pool().get('ir.attachment')
        attachments = [a for h in helpdesks for a in h.attachments]
        Attachment.delete(attachments)
        super(Helpdesk, cls).delete(helpdesks)

    @classmethod
    def copy(cls, helpdesks, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default['attachments'] = None
        return super(Helpdesk, cls).copy(helpdesks, default=default)

    @classmethod
    def _talk(cls, helpdesks):
        pool = Pool()
        Talk = pool.get('helpdesk.talk')
        User = pool.get('res.user')
        user = User(Transaction().user)
        reads = []
        for helpdesk in helpdesks:
            if not helpdesk.message:
                cls.raise_user_error('no_message')
            talk = Talk()
            talk.date = datetime.now()
            talk.email = user.email or None
            talk.helpdesk = helpdesk
            talk.message = helpdesk.message
            talk.unread = False
            talk.save()
            for talk in helpdesk.talks:
                if talk.unread:
                    reads.append(talk)
        if reads:
            Talk.write(reads, {'unread': False})

    @classmethod
    def _log(cls, helpdesks, keyword):
        pool = Pool()
        User = pool.get('res.user')
        Log = pool.get('helpdesk.log')
        for helpdesk in helpdesks:
            log = Log()
            log.name = keyword
            log.date = datetime.now()
            log.user = User(Transaction().user)
            log.helpdesk = helpdesk
            log.save()

    @classmethod
    @ModelView.button
    def add_reply(cls, helpdesks):
        for helpdesk in helpdesks:
            if helpdesk.talks:
                message = helpdesk.talks[0].message
                cls.write([helpdesk], {
                    'message': '> ' + message.replace('\n', '\n> '),
                    })

    @classmethod
    @ModelView.button
    def talk_note(cls, helpdesks):
        cls._talk(helpdesks)
        cls.write(helpdesks, {'message': None})

    @classmethod
    @ModelView.button
    def talk_email(cls, helpdesks):
        SMTP = Pool().get('smtp.server')
        for helpdesk in helpdesks:
            if not helpdesk.email_from:
                cls.raise_user_error('no_email_from')
            if not helpdesk.message:
                cls.raise_user_error('no_message')
        server = SMTP.get_smtp_server_from_model('helpdesk')
        cls.send_email(helpdesks, server)  # Send email
        cls._talk(helpdesks)
        cls.write(helpdesks, {'message': None})

    @classmethod
    def send_email(cls, helpdesks, server):
        pool = Pool()
        SMTP = pool.get('smtp.server')
        User = pool.get('res.user')
        user = User(Transaction().user)
        from_ = user.email or server.smtp_email
        if server.smtp_use_email:
            from_ = server.smtp_email
        for helpdesk in helpdesks:
            if not helpdesk.email_from:
                cls.raise_user_error('no_email_from')
            if not helpdesk.message:
                cls.raise_user_error('no_message')
            recipients = []
            emails = helpdesk.email_from.replace(' ', '').replace(',', ';')
            emails = emails.split(';')
            recipients = recipients + emails
            cc_addresses = []
            if helpdesk.email_cc:
                emails = helpdesk.email_cc.replace(' ', '').replace(',', ';')
                emails = emails.split(';')
                cc_addresses = cc_addresses + emails
            if CHECK_EMAIL:
                for recipient in recipients:
                    if not emailvalid.check_email(recipient):
                        cls.raise_user_error('no_from_valid')
                if cc_addresses:
                    for cc_address in cc_addresses:
                        if not emailvalid.check_email(cc_address):
                            cls.raise_user_error('no_recepients_valid')
            msg = MIMEText(helpdesk.message, _charset='utf-8')
            msg['Subject'] = Header(helpdesk.name, 'utf-8')
            msg['From'] = from_
            msg['To'] = ', '.join(recipients)
            if cc_addresses:
                msg['Cc'] = ', '.join(cc_addresses)
            msg['Reply-to'] = server.smtp_email
            # msg['Date']     = Utils.formatdate(localtime = 1)
            msg['Message-ID'] = Utils.make_msgid()
            if helpdesk.message_id:
                msg['In-Reply-To'] = helpdesk.message_id
            try:
                server = SMTP.get_smtp_server(server)
                server.sendmail(from_, recipients +
                    cc_addresses, msg.as_string())
                server.quit()
            except:
                cls.raise_user_error('smtp_error')
            if not helpdesk.message_id:
                cls.write([helpdesk], {'message_id': msg.get('Message-ID')})

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def done(cls, helpdesks):
        keyword = cls.raise_user_error('closed', raise_exception=False)
        cls._log(helpdesks, keyword)
        cls.write(helpdesks, {'closed_date': datetime.now()})

    @classmethod
    @ModelView.button
    @Workflow.transition('open')
    def open(cls, helpdesks):
        User = Pool().get('res.user')
        keyword = cls.raise_user_error('opened', raise_exception=False)
        for helpdesk in helpdesks:
            if not helpdesk.employee:
                employee = User(Transaction().user).employee
                if not employee:
                    cls.raise_user_error('no_user')
                cls.write([helpdesk], {'employee': employee})
        cls._log(helpdesks, keyword)

    @classmethod
    @ModelView.button
    @Workflow.transition('pending')
    def pending(cls, helpdesks):
        keyword = cls.raise_user_error('pending', raise_exception=False)
        cls._log(helpdesks, keyword)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, helpdesks):
        keyword = cls.raise_user_error('drafted', raise_exception=False)
        cls._log(helpdesks, keyword)

    @classmethod
    def getmail(cls, messages, attachments=None):
        '''Get messages and load in helpdesk talks'''
        pool = Pool()
        GetMail = pool.get('getmail.server')
        Helpdesk = pool.get('helpdesk')
        HelpdeskTalk = pool.get('helpdesk.talk')
        Attachment = pool.get('ir.attachment')
        for (_, message) in messages:
            msgeid = message.messageid
            msgfrom = (parseaddr(message.from_addr)[1] if message.from_addr
                else None)
            msgcc = message.cc if not message.cc == 'None' else None
            msgreferences = message.references
            msginrepplyto = getattr(message, 'inrepplyto', None)
            msgsubject = message.title or 'Not subject'
            msgdate = message.date
            msgbody = message.body
            logging.getLogger('Helpdesk').info('Process email: %s' %
                (msgeid))
            helpdesk = None
            if msgreferences or msginrepplyto:
                references = msgreferences or msginrepplyto
                if '\r\n' in references:
                    references = references.split('\r\n')
                else:
                    references = references.split(' ')
                for ref in references:
                    ref = ref.strip()
                    helpdesk = cls.search([('message_id', '=', ref)], limit=1)
                    if helpdesk:
                        helpdesk = helpdesk[0]
                        break
            # Create a new helpdesk
            if not helpdesk:
                party, address = GetMail.get_party_from_email(msgfrom)
                helpdesk = Helpdesk()
                helpdesk.name = msgsubject
                helpdesk.email_from = msgfrom
                helpdesk.email_cc = msgcc
                helpdesk.party = party if party else None
                helpdesk.address = address if address else None
                helpdesk.message_id = msgeid
                helpdesk.save()
            # Create a new helpdesk talk
            helpdesk_talk = HelpdeskTalk()
            helpdesk_talk.date = GetMail.get_date(msgdate)
            helpdesk_talk.email = msgfrom
            helpdesk_talk.helpdesk = helpdesk
            helpdesk_talk.message = msgbody
            helpdesk_talk.unread = True
            helpdesk_talk.save()
            # Create a attachments
            if attachments:
                for attachment in message.attachments:
                    attach = Attachment()
                    attach.name = attachment[0]
                    attach.type = 'data'
                    attach.data = attachment[1]
                    attach.resource = '%s' % (helpdesk)
                    attach.save()
        return True


class HelpdeskTalk(ModelSQL, ModelView):
    'Helpdesk Talk'
    __name__ = 'helpdesk.talk'
    _rec_name = 'display_text'
    date = fields.DateTime('Date', readonly=True)
    email = fields.Char('email')
    helpdesk = fields.Many2One('helpdesk', 'Helpdesk', required=True,
        ondelete='CASCADE')
    message = fields.Text('Message')
    display_text = fields.Function(fields.Text('Display Text'),
        'get_display_text')
    unread = fields.Boolean('Unread')

    @classmethod
    def __setup__(cls):
        super(HelpdeskTalk, cls).__setup__()
        cls._order.insert(0, ('id', 'DESC'))

    def truncate_data(self):
        message = self.message and self.message.split('\n') or []
        return ('\n\t'.join(message[:6]) + '...' if len(message) > 6
            else '\n\t'.join(message))

    def get_display_text(self, name=None):
        display = ('(' + str(self.date) + '):\n' + self.truncate_data())
        return self.email + ' ' + display if self.email else display


class HelpdeskLog(ModelSQL, ModelView):
    'Helpdesk Log'
    __name__ = 'helpdesk.log'
    name = fields.Char('Action')
    date = fields.DateTime('Date')
    user = fields.Many2One('res.user', 'User', readonly=True)
    helpdesk = fields.Many2One('helpdesk', 'Helpdesk', required=True,
            ondelete='CASCADE')

    @classmethod
    def __setup__(cls):
        super(HelpdeskLog, cls).__setup__()
        cls._order.insert(0, ('id', 'DESC'))

    @staticmethod
    def default_date():
        return datetime.now()
