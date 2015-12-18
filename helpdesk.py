# This file is part of the helpdesk module for Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from datetime import datetime
from email import Utils
from email import Encoders
from email.header import Header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.utils import parseaddr
from html2text import html2text
from sql.aggregate import Count
from trytond.model import Workflow, ModelView, ModelSQL, fields
from trytond.pool import Pool
from trytond.pyson import Eval, If, Equal, In
from trytond.transaction import Transaction
import mimetypes
import dateutil.tz
import re
import logging

logger = logging.getLogger(__name__)

CHECK_EMAIL = False
try:
    import emailvalid
    CHECK_EMAIL = True
except ImportError:
    logger.warning('Unable to import emailvalid. Email validation disabled.')

try:
    import pytz
except:
    pytz = None

__all__ = ['Helpdesk', 'HelpdeskTalk', 'HelpdeskLog', 'HelpdeskAttachment']

PREFIX_REPLY = ['re', 'fw', 'fwd', 'fw', 'was', 'ot', 'eom', 'ab', 'ar', 'fya',
    'fysa', 'fyfg', 'fyg', 'i', 'let', 'lsfw', 'nim', 'nls', 'nm', 'nmp',
    'nms', 'nntr', 'nrn', 'nrr', 'nsfw', 'nss', 'nt', 'nwr', 'nws', 'ooo',
    'pnfo', 'pnsfw', 'pyr', 'que', 'rb', 'rlb', 'rr', 'sfw', 'sim', 'ssia',
    'tbf', 'tsfw', 'y/n', 'sv', 'antw', 'vs', 're', 'aw', 'r', 'rif', 'sv',
    're', 'odp', 'ynt', 'doorst', 'vl', 'tr', 'wg', 'fs', 'vs', 'vb', 'rv',
    'enc', 'pd']


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
    last_talk = fields.DateTime('Last Talk', readonly=True)
    num_attach = fields.Function(fields.Integer('Attachments'),
        'get_num_attachments')
    attachments = fields.One2Many('ir.attachment', 'resource', 'Attachments',
        help='Attachments fields related in this helpdesk. Remember to remove '
            'email attachments not necessary, for example, signatures, logos, '
            'etc')
    add_attachments = fields.Many2Many('helpdesk-ir.attachment', 'helpdesk',
        'attachment', 'Add Attachments Email',
        domain=[('id', 'in', Eval('attachments'))],
        depends=['attachments'],
        help='Send email attachments, first you need to add files in '
            'attachments field and after select in this list. When send email,'
            ' attachemtns will be remove from this list.')
    unread = fields.Function(fields.Boolean('Unread'),
        'get_unread', setter='set_unread', searcher='search_unread')
    kind = fields.Selection([
            ('generic', 'Generic'),
            ], 'Kind')

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
                'no_server_smtp': 'Not found SMTP server. '
                    'Configure an SMTP server related with Helpdesk!',
                'no_recepients_valid': 'Not valid recepients email!',
                'smtp_error':
                    'Wrong connection to SMTP server. Not send email.',
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
                ('done', 'pending'),
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
            if not helpdesk.talks:
                continue
            HelpdeskTalk.write(list(helpdesk.talks), {'unread': value})

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

    @classmethod
    def get_num_attachments(cls, helpdesks, name):
        Attachment = Pool().get('ir.attachment')
        attachment = Attachment.__table__()
        cursor = Transaction().cursor
        res = {h.id: None for h in helpdesks}
        cursor.execute(*attachment.select(
            attachment.resource.as_('resource'),
            Count(attachment.id).as_(name),
            where=attachment.resource.in_(
                ['helpdesk,%s' % str(h.id) for h in helpdesks]),
            group_by=attachment.resource))
        res.update({
                int(r['resource'].split(',')[1]): r[name]
                for r in cursor.dictfetchall()})
        return res

    @fields.depends('party', 'email_from')
    def on_change_party(self):
        pool = Pool()
        Address = pool.get('party.address')
        Contact = pool.get('party.contact_mechanism')

        if self.party:
            addresses = Address.search([('party', '=', self.party)])
            for address in addresses:
                self.contact = address
                if address.email and not self.email_from:
                    self.email_from = address.email
                break
            if not self.email_from:
                for contact in Contact.search([('party', '=', self.party)]):
                    if contact.type == 'email':
                        self.email_from = contact.email
                        break
        else:
            self.contact = None

    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def default_priority():
        return '3'

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
    def view_attributes(cls):
        return [('/tree', 'colors',
                If(In(Eval('state', ''), ['cancel', 'done']), 'grey', \
                If(Equal(Eval('state', ''), 'open'), 'red', 'black')))]

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
        for helpdesk in helpdesks:
            if not helpdesk.email_from:
                cls.raise_user_error('no_email_from')
            if not helpdesk.message:
                cls.raise_user_error('no_message')
        cls.send_email(helpdesks)  # Send email
        cls._talk(helpdesks)
        cls.write(helpdesks, {'message': None})

    @classmethod
    def send_email(cls, helpdesks):
        pool = Pool()
        SMTP = pool.get('smtp.server')
        User = pool.get('res.user')
        HelpdeskConfiguration = pool.get('helpdesk.configuration')

        helpdesk_configuration = HelpdeskConfiguration(1)
        user = User(Transaction().user)
        from_ = user.email
        signature = ('\n\n--\n%s' % user.signature
            if user.signature else user.name)

        for helpdesk in helpdesks:
            server = getattr(helpdesk_configuration, 'smtp_%s' % helpdesk.kind,
                None)
            if not server:
                server = SMTP.get_smtp_server_from_model('helpdesk')
            if not server:
                cls.raise_user_error('no_server_smtp')

            from_ = server.smtp_email
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

            if helpdesk.add_attachments:
                msg = MIMEMultipart()
                msg.attach(MIMEText(helpdesk.message + signature,
                    _charset='utf-8'))
            else:
                msg = MIMEText(helpdesk.message + signature, _charset='utf-8')

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

            #  Add email attachments from add attachments field
            for attachment in helpdesk.add_attachments:
                filename = attachment.name
                content_type, _ = mimetypes.guess_type(filename)
                maintype, subtype = (
                    content_type or 'application/octet-stream'
                    ).split('/', 1)

                attach = MIMEBase(maintype, subtype)
                attach.set_payload(attachment.data)
                Encoders.encode_base64(attach)
                attach.add_header(
                    'Content-Disposition', 'attachment', filename=filename)
                attach.add_header(
                    'Content-Transfer-Encoding', 'base64')
                msg.attach(attach)

            try:
                smtp_server = server.get_smtp_server()
                smtp_server.sendmail(from_, recipients +
                    cc_addresses, msg.as_string())
                smtp_server.quit()
            except:
                cls.raise_user_error('smtp_error')

            #  write helpdesk values
            vals = {}
            if not helpdesk.message_id:
                vals['message_id'] = msg.get('Message-ID')
            if helpdesk.add_attachments:
                vals['add_attachments'] = [('remove',
                    [x.id for x in helpdesk.add_attachments])]
            if vals:
                cls.write([helpdesk], vals)

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
    def getmail(cls, server, messages):
        'Get messages and load in helpdesk talks'
        pool = Pool()
        GetMail = pool.get('getmail.server')
        Helpdesk = pool.get('helpdesk')
        HelpdeskTalk = pool.get('helpdesk.talk')
        Attachment = pool.get('ir.attachment')

        new_talks = []
        helpdesks_to_write = set()
        for message in list(reversed(messages)): # order older to new message
            to_ = message.to
            if not to_:
                to_ = message.delivered_to
            msgeid = message.message_id
            msgfrom = (parseaddr(re.sub('[,;]', '', message.from_addr))[1]
                if message.from_addr else None)
            msgcc = None
            if message.cc:
                ccs = re.findall(r'[\w\.-]+@[\w\.-]+', message.cc)
                if ccs:
                    msgcc = ",".join(ccs)
            references = message.references
            if references:
                if ',' in references:  # Hotmail Reply References
                    references = references.split(',')
                elif '\r\n' in references:  # Gmail Replay References
                    references = references.split('\r\n')
                elif ' ' in references:  # Yahoo References
                    references = references.split(' ')
                else:
                    references = [references]
            if not references:
                references = [msgeid]
            if getattr(message, 'in_reply_to'):
                references.append(message.in_reply_to)
            msgsubject = message.title or 'Not subject'
            msgdate = message.date
            msgbody = html2text(message.body.replace('\n', '<br>'))
            logger.info('Process email: %s' % (msgeid))

            # Search helpdesk by msg reference, msg in reply to or
            # "description + email from"
            helpdesk = None
            talks_by_ref = HelpdeskTalk.search([
                    ('message_id', 'in', references)
                    ])
            if talks_by_ref:
                helpdesk = talks_by_ref[0].helpdesk

            # check if a new talk is related with recent helpdesk
            if not helpdesk:
                for new_talk in new_talks:
                    if new_talk.message_id in references:
                        helpdesk = new_talk.helpdesk
                        break

            # Helpdesk
            if helpdesk:
                helpdesks_to_write.add(helpdesk)
            else:
                party, address = GetMail.get_party_from_email(msgfrom)
                helpdesk = Helpdesk()
                helpdesk.name = msgsubject
                helpdesk.email_from = msgfrom
                helpdesk.email_cc = msgcc
                helpdesk.party = party if party else None
                helpdesk.address = address if address else None
                helpdesk.message_id = msgeid
                helpdesk.kind = server.kind if server.kind else 'generic'
                helpdesk.save()

            # Helpdesk talk
            helpdesk_talk = HelpdeskTalk()
            helpdesk_talk.date = GetMail.get_date(msgdate)
            helpdesk_talk.email = msgfrom
            helpdesk_talk.helpdesk = helpdesk
            helpdesk_talk.message = msgbody
            helpdesk_talk.unread = True
            helpdesk_talk.message_id = msgeid
            helpdesk_talk.save()
            new_talks.append(helpdesk_talk)

            # Attachments
            if server.attachment:
                # - Attachment name is unique. Skip reapeat filename
                # - If there are another same filename, write
                attachment_names = set()
                for attachment in message.attachments:
                    try:
                        fname = GetMail.get_filename(attachment[0])
                    except:
                        continue

                    if fname in attachment_names:
                        continue
                    attachment_names.add(fname)

                    attatchs = Attachment.search([
                            ('name', 'ilike', fname),
                            ('resource', '=', '%s' % (helpdesk)),
                            ])
                    if attatchs:
                        attach, = attatchs
                    else:
                        attach = Attachment()
                        attach.name = fname
                        attach.resource = '%s' % (helpdesk)
                        attach.type = 'data'
                    attach.data = attachment[1]
                    try:
                        attach.save()
                    except TypeError, e:
                        logging.getLogger('Helpdesk').warning(
                            'Email Attachment: %s. %s' % (msgeid, e))
                        continue
                    except:
                        continue

        if helpdesks_to_write:
            cls.write(list(helpdesks_to_write), {'state': 'pending'})


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
    message_id = fields.Char('Message ID')

    @classmethod
    def __setup__(cls):
        super(HelpdeskTalk, cls).__setup__()
        cls._order = [
            ('id', 'DESC'),
            ]

    @staticmethod
    def default_date():
        return datetime.now()

    def truncate_data(self):
        message = self.message and self.message.split('\n') or []
        return ('\n\t'.join(message[:6]) + '...' if len(message) > 6
            else '\n\t'.join(message))

    def get_display_text(self, name=None):
        Company = Pool().get('company.company')

        display = ''
        if self.email:
            display += self.email + ' '
        date = self.date
        if date:
            if pytz and Transaction().context.get('company'):
                company = Company(Transaction().context['company'])
                if company.timezone:
                    czone = pytz.timezone(company.timezone)
                    lzone = dateutil.tz.tzlocal()
                    date = date.replace(tzinfo=lzone).astimezone(czone)
            display += '(' + str(date) + ')'
        display += ':\n' + self.truncate_data()
        return display

    @classmethod
    def create(cls, vlist):
        Helpdesk = Pool().get('helpdesk')

        now = datetime.now()

        talks = super(HelpdeskTalk, cls).create(vlist)
        helpdesks = [t.helpdesk for t in talks]

        if helpdesks:
            Helpdesk.write(helpdesks, {
                'last_talk': now,
                })
        return talks

    @classmethod
    def write(cls, *args):
        Helpdesk = Pool().get('helpdesk')

        helpdesks = []
        now = datetime.now()

        super(HelpdeskTalk, cls).write(*args)

        actions = iter(args)
        for talks, values in zip(actions, actions):
            helpdesks = [t.helpdesk for t in talks]

        if helpdesks:
            Helpdesk.write(helpdesks, {
                'last_talk': now,
                })


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
        cls._order = [
            ('id', 'DESC'),
            ]

    @staticmethod
    def default_date():
        return datetime.now()


class HelpdeskAttachment(ModelSQL):
    'Helpdesk - Attachment'
    __name__ = 'helpdesk-ir.attachment'
    _table = 'helpdesk_attachment_rel'
    helpdesk = fields.Many2One('helpdesk', 'Helpdesk', ondelete='CASCADE',
        select=True, required=True)
    attachment = fields.Many2One('ir.attachment', 'Attachment',
        ondelete='RESTRICT', select=True, required=True)
