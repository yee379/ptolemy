# Create your views here.

from django.http import HttpResponse

def test( request ):
    html = '<html><body>hello ' + str(request )+ '</body></html>'
    return HttpResponse( html )
