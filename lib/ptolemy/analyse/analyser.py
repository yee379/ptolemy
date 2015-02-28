# from iepm_sonar.perfcelery.perfsonar import Datum, TimeSeriesDataTable

from iepm_sonar.analyse.manager import AnalyseQueueFactory

import multiprocessing

from uuid import uuid1 as uuid
import numpy
import math

import logging

# analysis results; ensure more sever has higher numeric value
NONE    = 0
OK      = 1
WARN    = 3
ERROR   = 5


class TimeSeriesDataTable:
    pass


class Analyser( object ):
    """
    An analyser object initiates and keeps data for analysis
    when analysing it will iterate through a list of matcher objects and determines if the matcher
    objects think that the data is anomalous
    each matcher object is instaniated from the parameters
    """
    # private
    metric= None
    measurement = None
    
    working = False
    last_state = None
    
    alert_map = {
        None: NONE,
        'UNKNOWN': NONE,
        'OK': OK,
        'OKAY': OK,
        'WARN': WARN,
        'ERROR': ERROR,
    }
        
    human_map = {
        None: 'UNKNOWN',
        NONE: 'UNKNOWN',
        OK: 'OK',
        WARN: 'WARN',
        ERROR: 'ERROR',
    }

    def __init__(self, measurement_hash, parameters, initial_data=None, last_state=None ):
        # parameters = { 
        #     'matcher': 'Mean|TwoSigma|Range' # type of analysing to do (actually creates instance of matcher class)
        #     'metric': 'loss'  # what metric (column to use) # TODO, deal with many

        #     'initial_history': '6h', # how long to have history for when first startup
        #     'max_history': '1d', # will remove data entries older than this in the cache
        #     'alert_on': {
        #         'range': { 'ok': ( 0, 1 ), 'warn': ( 1, 10 ), 'error': ( 10, None ) },
        #         'value': { 'ok': 'gt|gte|lt|lte|eq', 'error': ...  }
        #      }
        # }

        """
        
        future:
        
        support complex analysis from many different sources
        - need to determine how to get data from the sources (need to refetch the data?)
        - how to change teh input:
        
            __init__( self, parameters ):
                parameters = {
                    measurement_hash1: { 'matcher': Range, 'metric': blah },
                    measurement_hash2: { 'matcher': Change, 'metric': blah },
                }
        
        """

        self.measurement_hash = measurement_hash
        # covert if necessary
        self.last_state = last_state
        if not self.last_state == None:
            self.last_state = self.last_state.upper()
        if self.last_state in self.alert_map:
            self.last_state = self.alert_map[self.last_state]

        self.data = initial_data
        
        if not 'matcher' in parameters:
            raise SyntaxError, 'parameter must contain a matcher type'
        if not parameters['matcher'] in ENGINE_MAP:
            raise NotImplementedError, 'unknown matcher type ' + str(parameters['matcher'])
        if not 'alert_on' in parameters:
            raise SyntaxError, 'parameter must contain alert_on dict'

        # normalise alert_on analysis keys
        alert = {}
        for t in parameters['alert_on'].keys():
            alert[t] = {}
            for k in parameters['alert_on'][t]:
                if k in self.alert_map:
                    alert[t][self.alert_map[k]] = parameters['alert_on'][t][k]
                else:
                    raise Exception, "unknown state " + str(k)
        self.alert_on = alert

        # create matcher class
        self.matcher = ENGINE_MAP[parameters['matcher']]( self.alert_on )

        if not 'metric' in parameters:
            raise SyntaxError, 'no metric defined'
        self.metric = parameters['metric']
        
        # format of data?
        self.initial_data = initial_data
        
        self.data = TimeSeriesDataTable()
        
    
    def get_metric( self, datum, metric=None, dtype=float ):
        """ returns the float value of the datum provided  """
        if metric == None:
            metric = self.metric
        if metric in datum:
            try:
                return dtype( datum[metric] )
            except:
                logging.error("could not cast " + str(datum[metric]) + " to " + str(dtype) )
        return None

    def initial( self ):
        # pre populate
        self.matcher.initial_pre()
        if not self.initial_data == None:
            # self.data = self.initial_fetch( duration=self.initial_history )
            self.matcher.initial_process( self.initial_data )
        self.matcher.initial_post()

    
    # def initial_fetch(self, duration=None ):
    #     """
    #     retrieves and initial set of data to enable analysis
    #     """
    #     start, end = determine_time_range( None, None, duration )
    #     data = None
    #     try:
    #         data = iepm_sonar.sonar.tasks.get_data( self.measurement_hash, start_time=start, end_time=end )
    #     except Exception, e:
    #         logging.error("Error: " + str(e))
    #     logging.debug("initiate: " + str( self.data.tsv() ) )
    #     return data

    def start( self, data=None ):
        self.initial()
        return self.analyse( data )

    def analyse( self, data ):
        """ keep a matrix of results for each pre/process/post return """
        new_data = False
        n = len(data)
        c = 0
        datum_results = []
        for t, datum in data:
            c = c + 1
            i = self.get_metric( datum )
            logging.info("  datum: " + str(datum)  + ", i=" + str(i))
            if self.data.add( datum ):
                this = [ int(self.matcher.per_datum_pre( ) or NONE), int(self.matcher.per_datum_process( i ) or NONE), int(self.matcher.per_datum_post( i ) or NONE) ]
                new_data = True
                # TODO: only care about the last entry for notification?
                logging.info("  per datum (" + str(c) + "/" + str(n) + "): \t" + str(datum.timestamp) + ", " + str(this)  )
                # determine status from aggregate bitwise of outputs (ignore Nones), use max
                datum_results.append( ( datum.timestamp, i, max(this), datum ) )

        logging.info("datums : " + str(datum_results) )
                
        set_t, set_v, set_res = ( NONE, NONE, NONE )
        if new_data:
            this = [ int( self.matcher.dataset_pre() or NONE ), int( self.matcher.dataset_process( self.data ) or NONE ), int( self.matcher.dataset_post( self.data ) or NONE ) ]
            set_t, set_v, set_res = ( datum.timestamp, max(this), this )

        logging.info("dataset: " + str(set_t) + ', ' + str(set_v) + ', ' + str(set_res) )

        # compare our individual datum analysis results with that of the dataset
        state = set_v
        res = {}
        # assume chronological sequence of datums
        for datum in datum_results:
            t, i, v, d = datum
            # don't alert the first run!
            if v > state:
                if not self.last_state == None:
                    logging.error("  datum states: v=" + str(v) + ", state=" + str(state) + "\t" + str(i) )
                    res = { 'timestamp': t, 'value': self.get_metric(d), 'metric': self.metric, 'datum': d }
                state = v

        # notify that a problem has occured
        fm = self.last_state
        # if not self.last_state == None and not state == self.last_state:
        #     logging.error("STATE CHANGED: " + str(self.last_state) + " -> " + str(state) )

        # keep an eye on this state to compare to next iteration
        self.last_state = state
        
        logging.error("ANALYSED STATE TRANSITION: " + str(self.human_map[fm]) + " to " + str(self.human_map[state]))
        return { 'state': self.human_map[state], 'previous_state': self.human_map[fm], 'message': res }
        

class StreamingAnalyser( multiprocessing.Process, Analyser ):
    """
    An Analyser is a Process that listens for incoming data and analyses that data
    using approrpriate initial parameters and running process() will generate 
    an alert automatically
    An inherited analyser should implement processing in two parts:
    - initial: setup of the object
    - per_datum: analysis on each and every new datum that comes in
    things that come free:
    - repeated data (by timestamp) will be ignored
    """    
    q = None
        
    def __init__(self, measurement, parameters, initial_data=None ):
        Analyser.__init__(self)
        self.q = None
        # initiate processing
        multiprocessing.Process.__init__(self)
        
    def run(self):
        """ start listening for new data and analyse it forever """
        # logging.info("Analysis engine " + str(self) + " for " + str(self.measurement_hash) + ": " + str(self.params))
        # self.name = self.measurement_hash
        self.working = True

        # queue to get data from
        self.q = AnalyseQueueFactory().get( consume=True, key=self.measurement_hash )
        self.inital()

        # forever
        self.q.consume( self.analyse )
    
    def analyse( self, json, envelope ):
        if not envelope == None:
            envelope.ack()
        data = []
        for d in json:
            datum = Datum.deserialize( d )
            data.append( datum )
        return super( StreamingAnalyser, self ).analyse( data )



class Matcher( object ):
    
    alert_on = None
    
    def __init__(self, alert_on ):
        self.alert_on = alert_on
    
    def initial_pre(self):
        pass
    def initial_process( self, data ):
        pass
    def initial_post( self ):
        pass

    def per_datum_pre( self ):
        pass
    def per_datum_process( self, datum ):
        pass
    def per_datum_post( self, datum ):
        pass

    def dataset_pre( self ):
        pass
    def dataset_process( self, data ):
        pass
    def dataset_post( self, data ):
        pass
        
        
    def do( self, i, against=None, range=None ):
        """
        do a comparision of value i against the registered alert_on method
        """
        status = NONE
        for k in self.alert_on.keys():
            ds = self.alert_on[k]
            if k == 'value':
                if not range == None:
                    status = self._alert_on_value_range( i, ds, range=range )
                else:
                    status = self._alert_on_value( i, against, ds )
            elif k == 'range':
                status = self._alert_on_range( i, ds )
            else:
                raise SyntaxError, 'unknown alert_on type ' + str(k)
        return status

    def _alert_on_value(self, i, x, params ):
        status = None
        for msg in params.keys():
            k = params[msg]
            if k == 'lte':
                if i <= x:
                    status = msg
            elif k == 'lt':
                if i < x:
                    status = msg
            elif k == 'gte':
                if i >= x:
                    status = msg
            elif k == 'gt':
                if i > x:
                    status = msg
            elif k == 'eq':
                if str(k) == str(x):
                    status = msg
            elif k == 'ne':
                if not str(k) == str(x):
                    status = msg
            if not status == None:
                return status
        return status

    def _alert_on_range( self, i, params ):
        status = None
        for r in params.keys():
            one, two = params[r]
            if one == None:
                one = float("-inf")
            if two == None:
                two = float("inf")
            # make code easier for ourselves
            if one > two:
                tmp = one
                one = two
                two = one
            one = float(one)
            two = float(two)

            # compare!
            if one == two and i == two:
                status = r
            elif i >= one and i < two:
                status = r

            logging.info("    i=" + str(i) + "\t bwtn: ( " + str(one) + ", " + str(two) + " )\tstatus: " + str(status) )
            if not status == None:
                return status
        return status
    
    def _alert_on_value_range( self, i, params, range=( None, None ) ):
        one, two = range
        logging.info("pre: value=" + str(i) + ", lower=" + str(one) + ", upper=" + str(two))
        status = None
        for msg in params.keys():
            k = params[msg]
            if k == 'lte':
                if i >= one or i <= two:
                    status = msg
            elif k == 'lt':
                if i > one or i < two:
                    status = msg
            elif k == 'gte':
                if i <= one or i >= two:
                    status = msg
            elif k == 'gt':
                if i < one or i > two:
                    status = msg
            if not status == None:
                return status
        return status


class Compare( Matcher ):
    """
    simply compares the provided against the last one
    """
    last_value = None
    
    def initial_process( self, data ):
        """
        save the last value so that we can compare
        """
        self.last_value = self.get_metric( data[-1], dtype=str )
        logging.error("COMPARE initial: " + str(self.last_value) + ", from " + str(data[-1]) )


    def per_datum_process( self, i ):
        logging.error("COMPARE: " + str(self.last_value) + " == " + str(i))
        return self.do( i, against=self.last_value )

class Range( Matcher ):
    """
    simple analyser to determine if values are within a specified range or not
    """
    def per_datum_process( self, i ):
        # logging.info(" analysing: " + str(datum) + " for " + str(self.params['metric']))
        return self.do( i )
        
class Mean( Matcher ):
    
    def initial_pre( self ):
        self.array = numpy.array([], dtype=float)

    def initial_process( self, data ):
        # parse through self.data and add to array
        for t, d in data:
            # logging.error("initial datum: " + str(d))
            i = self.get_metric( d ) # TODO
            if not i == None:
                self.array = numpy.append( self.array, i )

    def initial_post( self, data ):
        self.mean = self.array.mean()
        
    def per_datum_process( self, i ):
        # compare this value against the mean and alert
        logging.info("  value=" + str(i) + ",\tmean=" + str(self.mean))
        return self.do( i )

    def per_datum_post( self, i ):
        # add to array and recalculate mean
        self.array = numpy.append( self.array, i )
        self.mean = self.array.mean()
        logging.info("  process: mean=" + str(self.mean))


class TwoSigma( Mean ):

    def initial_post( self, data ):
        self.mean = self.array.mean()
        self.twosigma = 2*self.array.std()

    def per_datum_pre( self ):
        self.lower = self.mean - self.twosigma
        self.upper = self.mean + self.twosigma

    def per_datum_process( self, i ):
        state = self.do( i, range=( self.lower, self.upper ) )
        return state

    def per_datum_post( self, i ):
        self.array = numpy.append( self.array, i )
        self.mean = self.array.mean()
        self.twosigma = 2 * self.array.std()
        
        
class Plateau( Matcher ):
    """
    based on Calyam's modified plateau code
    """
    NO_EVENT = OK
    EVENT_IMPENDING = WARN
    EVENT_DETECTED = ERROR
        
    summary_window = []
    sample_window1 = []
    sample_window2 = []
    
    summary_window_count = 20
    sample_window2_count = 0
    sample_window1_count = 1
    trigger_count = 0
    trigger_duration = 7
    stcnt = 0
    
    elevate_value = 1.4
    elevate_value_small = 1.2
    sensitivity = 2
    
    def __init__(self, alert_on ):
        self.alert_on = alert_on

        self.elevate_value_small = 1.2
        self.elevate_value = 1.4
        self.sensitivity = 2
        self.trigger_duration = 7
    
    def calc_mean(self):
        self.mean = 0
        for i in xrange( 0, len(self.summary_window) ):
            self.mean = self.mean + self.summary_window[i]
        self.mean = self.mean / len( self.summary_window )
    
    def calc_new_thresh(self):
        l = self.sample_window1[0]
        for i in xrange( 0, len(self.sample_window2) ):
            # MAX?
            if self.sample_window2[i] > l:
                l = self.sample_window2[i]
        for i in xrange( 1, len(self.sample_window1) ):
            if self.sample_window1[i] > l:
                l = self.sample_window1[i]
        if self.sample_window1[0] == 0:
            s = self.sample_window1[0]
            for i in xrange( 1, len( self.sample_window1 ) ):
                if self.sample_window1[i] < s:
                    s = self.sample_window1[i]
            for i in xrange( 0, len( self.sample_window2 ) ):
                if self.sample_window2[i] < s:
                    s = self.sample_window2[i]
        else:
            s = self.sample_window2[0]
            for i in xrange( 0, len(self.sample_window2) ):
                if self.sample_window2[i] < s:
                    s = self.sample_window2[i]
                    
        self.newthresh1h = self.elevate_value * l
        self.newthresh2h = self.elevate_value_small * l
        self.newthresh1l = ( 2 - self.elevate_value_small ) * s
        self.newthresh1l = ( 2 - self.elevate_value ) * s
        
    def calc_var(self):
        var = 0
        for i in xrange( 0, len(self.summary_window) ):
            var = var + ( self.summary_window[i] - self.mean ) * ( self.summary_window[i] - self.mean )
        var = var / ( len(self.summary_window) - 1 )

    def calc_thresholds(self):
        sens = self.sensitivity * math.sqrt( var )
        self.threshold1h = self.mean + sens
        self.threshold1l = self.mean - sens
        sens_twice = 2 * sens
        self.threshold2h = self.mean + sens_twice
        self.threshold2l = self.mean - sens_twice

    def calc(self, current_data):
        state = self.NO_EVENT
        
        if self.stcnt == 0:
            self.calc_mean()
            self.calc_var()
            self.calc_thresholds()
        else:
            self.threshold1h = self.newthresh1h
            self.threshold1l = self.newthresh1l
            self.threshold2h = self.newthresh2h
            self.threshold2l = self.newthresh2l
            
            self.stcnt = self.stcnt + 1
            if self.stcnt == self.summary_window_count:
                self.stcnt = 0

        if math.floor( 1e10 * ( current_data - self.threshold2h ) ) > 0 or math.floor( 1e10 * ( self.threshold2l - current_data ) ):
            self.sample_window2_count = self.sample_window2_count + 1
            self.sample_window2[ self.sample_window2_count ] = current_data
            self.trigger_count = self.trigger_count + 1
            
        elif math.floor( 1e10 * ( current_data - self.threshold1h ) ) > 0 or math.floor( 1e10 * ( self.threshold1h - current_data ) ) > 0:
            self.sample_window1_count = self.sample_window1_count + 1
            self.sample_window1[ self.sample_window1_count ] = current_data
            self.trigger_count = self.trigger_count + 1
            
        else:
            for k in xrange( 0, self.summary_window_count - 1 ):
                self.summary_window[k] = self.summary_window[k+1]
            self.summary_window_count = self.sample_window1_count - 1
            self.summary_window[ self.summary_window_count ] = current_data
            if not self.trigger_count == 0:
                self.trigger_count = self.trigger_count - 1
            
        if self.trigger_count == 0 and ( self.sample_window1_count > 0 or self.sample_window2_count > 0 ):
            for k in xrange( 0, self.summary_window_count - self.sample_window1_count ):
                self.summary_window[k] = self.summary_window[k+self.sample_window1_count]
            k = self.summary_window_count - self.sample_window1_count
            m = 0
            while k < self.summary_window_count:
                self.summary_window[k] = self.sample_window1[m]
                k = k + 1
                m = m + 1
            self.sample_window1_count = 0
            self.sample_window2_count = 0
            
        if self.trigger_count >= math.floor( 0.75 * self.trigger_duration ):
            state = self.EVENT_IMPENDING
        
        if self.trigger_count == self.trigger_duration:
            self.trigger_count = 0
            state = self.EVENT_DETECTED
            self.stcnt = 1
            for k in xrange( 0, self.summary_window_count - self.sample_window1_count ):
                self.summary_window[ k ] = self.summary_window[ k + self.sample_window1_count ]
            k = self.summary_window_count - self.sample_window1_count
            m = 0
            while k < self.summary_window_count:
                self.summary_window[ k ] = self.sample_window1[ m ]
                k = k + 1
                m = m + 1

            self.calc_thresholds()
            self.sample_window1_count = 0
            self.sample_window2_count = 0
        
        return state


    def initial_pre( self ):
        # initial configs
        self.summary_window = []
        self.sample_window1 = []
        self.sample_window2 = []
        
        self.summary_window_count = 20
        self.sample_window1_count = 1
        self.sample_window2_count = 0

        self.trigger_count = 0
        self.trigger_duration = 7
        self.stcnt = 0

    def initial_process( self, data ):
        # do an initial calculation
        for t, d in data:
            if not d == None:
                state = self.calc( self.get_metric( d ) )
                logging.error( "  " + str(t) + "\t" + str(d) + "\t" + str(state))
        # don't return anything as we only care about the new data


    def initial_post( self, data ):
        pass
        
    def per_datum_process( self, i ):
        state = self.calc( i )
        logging.info("  value=" + str(i) + ",\tstate=" + str(state) )
        return state

    def per_datum_post( self, i ):
        pass


# map string to class for instantiation
ENGINE_MAP = {
    'Range':    Range,
    'Mean':     Mean,
    'TwoSigma': TwoSigma,
    'Compare':  Compare,
    'Plateau':  Plateau,
}

