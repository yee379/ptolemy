"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""

from django.test import TestCase


class L3HostTest(TestCase):
    
    def test_get(self):
        h = L3Host.objects.filter( )