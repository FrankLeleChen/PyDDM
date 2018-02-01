import numpy as np
import itertools

from paranoid.types import NDArray, Number, List, String, Self, Positive, Positive0, Range, Natural0
from paranoid.decorators import *

# TODO require passing non-decision trials
@verifiedclass
class Sample(object):
    """Describes a sample from some (empirical or simulated) distribution.

    Similarly to Solution, this is a glorified container for three
    items: a list of correct reaction times, a list of error reaction
    times, and the number of non-decision trials.  Each can have
    different properties associated with it, known as "conditions"
    elsewhere in this codebase.  This is to specifiy the experimental
    parameters of the trial, to allow fitting of stimuli by (for
    example) color or intensity.

    To specify conditions, pass a keyword argument to the constructor.
    The name should be the name of the property, and the value should
    be a tuple of length two or three.  The first element of the tuple
    should be a list of length equal to the number of correct trials,
    and the second should be equal to the number of error trials.  If
    there are any non-decision trials, the third argument should
    contain a list of length equal to `non_decision`.

    Optionally, additional data can be associated with each
    independent data point.  These should be passed as keyword
    arguments, where the keyword name is the property and the value is
    a tuple.  The tuple should have either two or three elements: the
    first two should be lists of properties for the correct and error
    reaction times, where the properties correspond to reaction times
    in the correct or error lists.  Optionally, a third list of length
    equal to the number of non-decision trials gives a list of
    conditions for these trials.  If multiple properties are passed as
    keyword arguments, the ordering of the non-decision time
    properties (in addition to those of the correct and error
    distributions) will correspond to one another.
    """
    @classmethod
    def _test(cls, v):
        # Most testing is done in the constructor and the data is read
        # only, so this isn't strictly necessary
        assert type(v) is cls
    @staticmethod
    def _generate():
        aa = lambda x : np.asarray(x)
        yield Sample(aa([.1, .2, .3]), aa([.2, .3, .4]), non_decision=0)
        yield Sample(aa([.1, .2, .3]), aa([]), non_decision=0)
        yield Sample(aa([]), aa([.2, .3, .4]), non_decision=0)
        yield Sample(aa([.1, .2, .3]), aa([.2, .3, .4]), non_decision=5)
        
    def __init__(self, sample_corr, sample_err, non_decision=0, **kwargs):
        assert sample_corr in NDArray(d=1, t=Number), "sample_corr not a numpy array, it is " + str(type(sample_corr))
        assert sample_err in NDArray(d=1, t=Number), "sample_err not a numpy array, it is " + str(type(sample_err))
        assert non_decision in Natural0(), "non-decision not a natural number"
        self.corr = sample_corr
        self.err = sample_err
        self.non_decision = non_decision
        # Values should not change
        self.corr.flags.writeable = False
        self.err.flags.writeable = False
        # Make sure the kwarg parameters/conditions are in the correct
        # format
        for _,v in kwargs.items():
            # Make sure shape and type are correct
            assert isinstance(v, tuple)
            assert len(v) in [2, 3]
            assert v[0] in NDArray(d=1, t=Number)
            assert v[1] in NDArray(d=1, t=Number)
            assert len(v[0]) == len(self.corr)
            assert len(v[1]) == len(self.err)
            # Make read-only
            v[0].flags.writeable = False
            v[1].flags.writeable = False
            if len(v) == 3:
                assert len(v[2]) == non_decision
            else:
                assert non_decision == 0
        self.conditions = kwargs
    def __len__(self):
        """The number of samples"""
        return len(self.corr) + len(self.err) + self.non_decision
    def __iter__(self):
        """Iterate through each reaction time, with no regard to whether it was a correct or error trial."""
        return np.concatenate([self.corr, self.err]).__iter__()
    def __add__(self, other):
        assert sorted(self.conditions.keys()) == sorted(other.conditions.keys()), "Canot add with unlike conditions"
        corr = self.corr + other.corr
        err = self.err + other.err
        non_decision = self.non_decision + other.non_decision
        conditions = {}
        for k in self.conditions.keys():
            sc = self.conditions
            oc = other.conditions
            conditions[k] = (sc[k][0]+oc[k][0], sc[k][1]+oc[k][1],
                             (sc[k][2] if len(sc[k]) == 3 else [])
                             + (oc[k][2] if len(oc[k]) == 3 else []))
        return Sample(corr, err, non_decision, **conditions)
    @staticmethod
    @accepts(NDArray(d=2, t=Number), List(String))
    @returns(Self)
    @requires('data.shape[1] >= 2')
    @requires('set(list(data[:,1])) - {0, 1} == set()')
    @requires('all(data[:,0].astype("float") == data[:,0])')
    @requires('data.shape[1] - 2 == len(column_names)')
    @ensures('len(column_names) == len(return.condition_names())')
    def from_numpy_array(data, column_names):
        """Generate a Sample object from a numpy array.
        
        `data` should be an n x m array (n rows, m columns) where
        m>=2. The first column should be the response times, and the
        second column should be whether the trial was correct or an
        error (1 == correct, 0 == error).  Any remaining columns
        should be conditions.  `column_names` should be a list of
        length m of strings indicating the names of the conditions.
        The first two values can be anything, since these correspond
        to special columns as described above.  (However, for the
        bookkeeping, it might be wise to make them "rt" and "correct"
        or something of the sort.)  Remaining elements are the
        condition names corresponding to the columns.  This function
        does not yet work with no-decision trials.
        """
        # TODO this function doesn't do validity checks yet
        c = data[:,1].astype(bool)
        nc = (1-data[:,1]).astype(bool)
        def pt(x): # Pythonic types
            arr = np.asarray(x)
            if np.all(arr == np.round(arr)):
                arr = arr.astype(int)
            return arr

        conditions = {k: (pt(data[c,i+2]), pt(data[nc,i+2]), []) for i,k in enumerate(column_names[2:])}
        return Sample(pt(data[c,0]), pt(data[nc,0]), 0, **conditions)
    def items(self, correct):
        """Iterate through the reaction times.

        This takes only one argument: a boolean `correct`, true if we
        want to iterate through the correct trials, and false if we
        want to iterate through the error trials.  

        For each iteration, a two-tuple is returned.  The first
        element is the reaction time, the second is a dictionary
        containing the conditions associated with that reaction time.
        """
        return _Sample_Iter_Wraper(self, correct=correct)
    @accepts(Self)
    @returns(Self)
    def subset(self, **kwargs):
        """Subset the data by filtering based on specified properties.

        Each keyword argument should be the name of a property.  These
        keyword arguments may have one of three values:

        - A list: For each element in the returned subset, the
          specified property is in this list of values.
        - A function: For each element in the returned subset, the
          specified property causes the function to evaluate to True.
        - Anything else: Each element in the returned subset must have
          this value for the specified property.

        Return a sample object representing the filtered sample.
        """
        mask_corr = np.ones(len(self.corr)).astype(bool)
        mask_err = np.ones(len(self.err)).astype(bool)
        mask_non = np.ones(self.non_decision).astype(bool)
        for k,v in kwargs.items():
            if hasattr(v, '__call__'):
                mask_corr = np.logical_and(mask_corr, map(v, self.conditions[k][0]))
                mask_err = np.logical_and(mask_err, map(v, self.conditions[k][1]))
                mask_non = [] if self.non_decision == 0 else np.logical_and(mask_non, map(v, self.conditions[k][2]))
            if hasattr(v, '__contains__'):
                mask_corr = np.logical_and(mask_corr, [i in v for i in self.conditions[k][0]])
                mask_err = np.logical_and(mask_err, [i in v for i in self.conditions[k][1]])
                mask_non = [] if self.non_decision == 0 else np.logical_and(mask_non, [i in v for i in self.conditions[k][2]])
            else:
                mask_corr = np.logical_and(mask_corr, [i == v for i in self.conditions[k][0]])
                mask_err = np.logical_and(mask_err, [i == v for i in self.conditions[k][1]])
                mask_non = [] if self.non_decision == 0 else np.logical_and(mask_non, [i == v for i in self.conditions[k][2]])
        filtered_conditions = {k : (list(itertools.compress(v[0], mask_corr)),
                                    list(itertools.compress(v[1], mask_err)),
                                    (list(itertools.compress(v[2], mask_non)) if len(v) == 3 else []))
                               for k,v in self.conditions.items()}
        return Sample(np.asarray(list(itertools.compress(self.corr, list(mask_corr)))),
                      np.asarray(list(itertools.compress(self.err, list(mask_err)))),
                      sum(mask_non),
                      **filtered_conditions)
    @accepts(Self)
    @returns(List(String))
    def condition_names(self):
        """The names of conditions which hold some non-zero value in this sample."""
        return list(self.conditions.keys())
    @accepts(Self, String)
    @requires('cond in self.condition_names()')
    @returns(List(Number))
    def condition_values(self, cond):
        """The values of a condition that have at least one element in the sample.

        `cond` is the name of the condition from which to get the
        observed values.  Returns a list of these values.
        """
        cs = self.conditions
        return sorted(list(set(cs[cond][0]).union(set(cs[cond][1]))))
    def condition_combinations(self, required_conditions=None):
        """Get all values for set conditions and return every combination of them.

        Since PDFs of solved models in general depend on all of the
        conditions, this returns a list of dictionaries.  The keys of
        each dictionary are the names of conditions, and the value is
        a particular value held by at least one element in the sample.
        Each list contains all possible combinations of condition values.

        If `required_conditions` is iterable, only the conditions with
        names found within `required_conditions` will be included.
        """
        cs = self.conditions
        conditions = []
        names = self.condition_names()
        if required_conditions is not None:
            names = [n for n in names if n in required_conditions]
        for c in names:
            conditions.append(list(set(cs[c][0]).union(set(cs[c][1]))))
        combs = []
        for p in itertools.product(*conditions):
            if len(self.subset(**dict(zip(names, p)))) != 0:
                combs.append(dict(zip(names, p)))
        if len(combs) == 0:
            return [{}]
        return combs

    @staticmethod
    @accepts(dt=Positive, T_dur=Positive)
    @returns(NDArray(d=1, t=Positive0))
    @requires('T_dur/dt < 1e5') # Too large of a number
    def t_domain(dt=.01, T_dur=2):
        """The times that corresponds with pdf/cdf_corr/err parameters (their support)."""
        return np.linspace(0, T_dur, T_dur/dt+1)

    @accepts(Self, dt=Positive, T_dur=Positive)
    @returns(NDArray(d=1, t=Positive0))
    @requires('T_dur/dt < 1e5') # Too large of a number
    @ensures('len(return) == len(self.t_domain(dt=dt, T_dur=T_dur))')
    def pdf_corr(self, dt=.01, T_dur=2):
        """The correct component of the joint PDF."""
        return np.histogram(self.corr, bins=int(T_dur/dt)+1, range=(0-dt/2, T_dur+dt/2))[0]/len(self)/dt # dt/2 terms are for continuity correction

    @accepts(Self, dt=Positive, T_dur=Positive)
    @returns(NDArray(d=1, t=Positive0))
    @requires('T_dur/dt < 1e5') # Too large of a number
    @ensures('len(return) == len(self.t_domain(dt=dt, T_dur=T_dur))')
    def pdf_err(self, dt=.01, T_dur=2):
        """The error (incorrect) component of the joint PDF."""
        return np.histogram(self.err, bins=int(T_dur/dt)+1, range=(0-dt/2, T_dur+dt/2))[0]/len(self)/dt # dt/2 terms are for continuity correction

    @accepts(Self, dt=Positive, T_dur=Positive)
    @returns(NDArray(d=1, t=Positive0))
    @requires('T_dur/dt < 1e5') # Too large of a number
    @ensures('len(return) == len(self.t_domain(dt=dt, T_dur=T_dur))')
    def cdf_corr(self, dt=.01, T_dur=2):
        """The correct component of the joint CDF."""
        return np.cumsum(self.pdf_corr(dt=dt, T_dur=T_dur))*dt

    @accepts(Self, dt=Positive, T_dur=Positive)
    @returns(NDArray(d=1, t=Positive0))
    @ensures('len(return) == len(self.t_domain(dt=dt, T_dur=T_dur))')
    def cdf_err(self, dt=.01, T_dur=2):
        """The error (incorrect) component of the joint CDF."""
        return np.cumsum(self.pdf_err(dt=dt, T_dur=T_dur))*dt

    @accepts(Self)
    @returns(Range(0, 1))
    def prob_correct(self):
        """The probability of selecting the right response."""
        return len(self.corr)/len(self)

    @accepts(Self)
    @returns(Range(0, 1))
    def prob_error(self):
        """The probability of selecting the incorrect (error) response."""
        return len(self.err)/len(self)

    @accepts(Self)
    @returns(Range(0, 1))
    def prob_undecided(self):
        """The probability of selecting neither response (undecided)."""
        return self.non_decision/len(self)

    @accepts(Self)
    @returns(Range(0, 1))
    def prob_correct_forced(self):
        """The probability of selecting the correct response if a response is forced."""
        return self.prob_correct() + self.prob_undecided()/2.

    @accepts(Self)
    @returns(Range(0, 1))
    def prob_error_forced(self):
        """The probability of selecting the incorrect response if a response is forced."""
        return self.prob_error() + self.prob_undecided()/2.

class _Sample_Iter_Wraper(object):
    """Provide an iterator for sample objects.

    `sample_obj` is the Sample which we plan to iterate.  `correct`
    should be either True (to iterate through correct responses) or
    False (to iterate through error responses).

    Each step of the iteration returns a two-tuple, where the first
    element is the reaction time, and the second element is a
    dictionary of conditions.
    """
    def __init__(self, sample_obj, correct):
        self.sample = sample_obj
        self.i = 0
        self.correct = correct
    def __iter__(self):
        return self
    def next(self):
        if self.i == len(self.sample):
            raise StopIteration
        self.i += 1
        if self.correct:
            rt = self.sample.corr
            ind = 0
        elif not self.correct:
            rt = self.sample.err
            ind = 1
        return (rt[self.i-1], {k : self.sample.conditions[k][ind][self.i-1] for k in self.sample.conditions.keys()})
        