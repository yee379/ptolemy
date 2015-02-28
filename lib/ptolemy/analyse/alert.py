import smtplib
from email.mime.text import MIMEText

import logging


class Alert( object ):
    def send( self, to, msg, **kwargs ):
        raise NotImplementedError, 'send'
    
    
class Email( Alert ):

    smtp = None

    def __init__( self, *args, **kwargs ):
        self.smtp = smtplib.SMTP(kwargs['server'])
        for i in ( 'from_name', 'from_email', 'site_name' ):
            if i in kwargs:
                setattr( self, i, kwargs[i] )
            else:
                setattr( self, i, 'undefined' )

    def __destroy__( self ):
        if not self.smtp == None:
            self.smtp.quit()
        self.smtp = None
        
    def send( self, to, msg, subject=None, relation=None, from_name=None, from_email=None ):
        if from_name == None:
            from_name = self.from_name
        if from_email == None:
            from_email = self.from_email

        logging.debug("EMAIL TO: " + str(to))
        if len( to ) > 0:
            email = None
            try:
                msg = MIMEText( msg )
                msg['Subject'] = subject
                msg['From'] = from_name
                msg['BCC'] = ', '.join(to)
                if not relation == None:
                    msg['In-Reply-To'] = '<' + relation + '@' + self.site_name + '>'
                # send!
                self.smtp.sendmail( from_email, to, msg.as_string() )
            except smtplib.SMTPException, e:
                logging.error("could not send out email: " + str(e))

class EmailTemplate( Email ):
    def __init__( self, *args, **kwargs ):
        super(EmailTemplate,self).__init__(*args,**kwargs)
        self.template = kwargs['template']

    def send( self, to, msg, subject=None, relation=None, from_name=None, from_email=None ):
        merge = self.template % msg
        super( EmailTemplate, self ).send( to, merge, subject=subject, relation=relation, from_name=from_name, from_email=from_email )


class AIM( Alert ):
    
    def send( self, to, msg ):
        pass
        
class Syslog( Alert ):
    
    def __init__( self, *args, **kwargs ):
        for i in ( 'facility', 'level' ):
            setattr( self, i, kwargs[i] )
        
    def send( self, to, msg, level=logging.INFO ):
        pass