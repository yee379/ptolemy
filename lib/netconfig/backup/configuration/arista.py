from netconfig.backup.configuration import Configuration
        
        
class Arista( Configuration ):
    scrub_matches = [
        r'password-label (?P<redact>.*)',
        r'key "(?P<redact>.*)"',
    ]
    
