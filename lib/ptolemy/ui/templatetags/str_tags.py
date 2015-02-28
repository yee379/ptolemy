from django import template
from re import search

register = template.Library()

@register.filter(name='split')
def split(value, arg):
    """ splits the string by supplied arg str and returns an arra y"""
    if value == None:
        return []
    return value.split(arg)

@register.filter(name='colourise')
def colourise(value):
    c = 'gray'
    if value == 'connected':
        c = 'green'
    elif value == 'notconnected':
        c = 'red'
    else:
        c = 'gray'
    return '<font color="' + c + '">' + value + '</font>'
    
@register.filter(name='formatmac')
def formatmac(value=None):
    if value == None:
        return str(None)
    if search('/', value):
        return value
    l = list(value.replace(' ', '').replace(':', '').replace('.', ''))
    mac = ''
    for i in xrange(len(l)):
        mac = mac + l[i].lower()
        if i < len(l) - 1 and i % 2 == 1:
            mac = mac + ':'
    return mac
    
@register.filter(name='dnsstrip')
def dnsstrip(value):
    if value == None: return None
    n = value.split('.')
    return n[0]
    
@register.filter(name='escapeforwardslash')
def escapeforwardslash(value):
    return value.replace( '/', '_' )
    
@register.filter(name='field')
def getfield(dict, arg):
    return dict[arg]
    
@register.filter(name='autoneg')
def autoneg(value):
    if value == True:
        return 'Auto'
    elif value == False:
        return 'Fixed'
    else:
        return 'Unknown'