from __future__ import print_function

__all__ = ["ChooserException", "Chooser", "flow", "Chart", "Assignments"]

class ChooserException(Exception):
    "Exception used to indicate nondeterminist execution"

class _ChooserEscape(Exception):
    "Used for the implementation of the choose/Chooser.apply protocol."
    "Don't ever catch this exception in your application code!"

class Chooser(object):
    def __init__(self, chosen = (), stack = None):
        self._chosen  = chosen           # a list of previously made choices
        self._stack   = stack            # a list of all lists of choices being made

        self._choosit = iter(chosen)     # use the iterator on chosen values to emit
                                         # choices at the call site of choose()
        if stack is None:
            self._single_choice = True   # if this value is True the first entry 
        else:                            # of the choices list in choose(choices) 
            self._single_choice = False  # will be returned
            

    def choose(self, choices):
        '''
        Present a list of choices at the call site of this function.
        :param choices: a list, tuple of set of values
        '''
        # use the first element of choices as a default value
        if self._single_choice:
            return choices[0]
        try:
            # get a chosen value first and try to return it as the current
            # choice
            c = next(self._choosit)
            if c not in choices:
                raise ChooserException("Program is not deterministic")
            return c
        except StopIteration:
            # if _choosit was exhausted at the site of this choose() call then for each 
            # value in the choices argument list, create a new chosen list by adding the choice
            # to the current chosen one. In the next round the iterator won't
            # fail at this call site because it has an additional choice.
            self._stack.extend([self._chosen + [choice] for choice in choices])
            # escape the caller of choose() for a next iteration which uses a fresh
            # chooser object.
            raise _ChooserEscape
        

    @classmethod
    def apply(chooser_cls, f, *args, **kwds):            
        '''
        An inside-out evaluation of a function f given a chooser. 

        :param f: a function which takes at least one `chooser` keyword argument 
                  and is called line

                  f(*args, chooser = ..., **kwds)

        :returns: a list of all return values of f with respect to the chooser 
                  iteration. If f returns with None, this None won't be collected 
                  in the list.
        '''
        results = []
        # collection of lists of choices
        stack   = [[]]
        while stack:
            chosen = stack.pop()
            try:
                # create a new chooser instance and either build new lists of choices
                # when the iteration over chosen at the call sites of chooser.choose() fails
                # with a _ChooserEscape exception or return the evaluation result of f and
                # collect it
                res = f(*args, chooser = chooser_cls(chosen, stack), **kwds)
                # None as return value will be ignored
                if res is not None:
                    results.append(res)
            except _ChooserEscape:
                pass
        return results

def flow(f):
    "Simple decorator which marks a function for application in a Chart object"
    f.flow = True
    return f

class Chart:
    def __init__(self, chooser_cls = Chooser):
        self.chooser = Chooser
        self.assignments = None        

    def create(self):
        '''
        Calls all flow decorated methods of this class with choosers.
        '''
        self.assignments = Assignments([])    

        # reflect on function which are decorated by 'flow'    
        for name in dir(self):
            f = getattr(self, name)
            if hasattr(f, "flow"):
                self._collect(self.chooser.apply(f))

    def _collect(self, results):
        '''
        Collect results in assignment list.
        '''
        for result in results:
            if isinstance(result, list):
                self.assignments.extend(result)
            elif isinstance(result, dict):
                # remove function inputs which may be collected as results
                for name in ("chooser", "self"):
                    if name in result:
                        del result[name]
                if result:
                    self.assignments.append(result)        
            else:
                self.assignments.append(result) 

    def execute(self, func):
        '''
        Wrap a function into a Chart object and create all flows for that 
        function. execute() returns the assignments of that Chart object.
        '''
        class SubChart(Chart):
            @flow
            def subFlow(self, chooser):
                return func(chooser)
            subFlow.__name__ = func.__name__
            subFlow.__doc__  = func.__doc__
        
        subchart = SubChart()
        subchart.create()
        return subchart.assignments

    def fix(self, **C):
        '''
        Building a subset of assignments by using variable constraints C. 

        Let A be an assignment in the assignment list.
        
          if ('x' in A) and ('x' in C) then A is collected only if A['x'] == C['x']

        Note that A will also be collected if no such 'x' exists. fix() means 
        that a variables constraint must not be violated, not that it has to exist. 
        Use filter() if you want to impose the existence of the constraint.
        '''
        fixed = self.assignments.fix(**C)
        chart    = self.__class__(self.chooser)
        # accept only dependent solutions as valid assignments
        # for a derived chart
        chart.assignments = fixed
        return chart

    def filter(self, **constraints):
        '''
        Building a subset of assignments by using variable constraints. 

        Let A be an assignment in the assignment list. 
        
          A is collected if constraints if a proper sub dictionary which can be 
          defined as:
          
          	There is a dictionary D which has no keys in common with C 
          	( D and C are disjoint )and A == D.update(C).

        
        
        
        '''

        chart = self.fix(**constraints)
        chart.assignments = chart.assignments.filter(**constraints)
        return chart

    def fetch(self, varname):
        return self.assignments.fetch(varname)

    # some convenience methods which simplify extraction

    def __len__(self):
        return len(self.assignments)

    def __nonzero__(self):
        return self.assignments!=[]

    def __iter__(self):
        return iter(self.assignments)


class Assignments:
    '''
    Auxiliary class used to filter through sets of assignments. 

    Here an "assignment" is a dict which originates from binding values to names 
    in function scope. Usually an assignment is the value of a function returning 
    its vars()

        def f(self, chooser):
            ...
            return vars()
    '''
    def __init__(self, assignments):
        self.assignments  = assignments
        self.dependent    = []

    def __mul__(self, other):
        return self.combine(other)

    def __rmul__(self, other):
        if isinstance(other, dict):
            other = Assignments([other])
        return other.combine(self)

    def combine(self, other):
        """
        Building new assignments by updating each of this assignment set by each 
        of the other.

        Note that this operation is not commutative, because update my destroy 
        information.
        """
        if isinstance(other, dict):
            other = Assignments([other])
        asn3 = Assignments([])
        for asn1 in self.assignments:
            for asn2 in other.assignments:
                c = asn1.copy()
                c.update(asn2)
                asn3.append(c)
        return asn3

    def extend(self, assignments):
        if isinstance(assignments, Assignments):
            # merge the Assignments objects
            self.assignments += assignments.assignments
            self.dependent += assignments.dependent
        else:
            # assume a simple list of fail
            self.assignments+=assignments        

    def append(self, assignment):
        self.assignments.append(assignment)

    def fix(self, **constraining_assignments):
        return self._fix(constraining_assignments, set())

    def filter(self, **constraining_assignments):
        assignments = self.fix(**constraining_assignments)
        keys = set(constraining_assignments.keys())
        L = []
        for asgn in assignments:
            if keys.issubset(asgn.keys()):
                L.append(asgn)
        return Assignments(L)

    def fetch(self, varname):
        return [asgn[varname] for asgn in self.assignments if varname in asgn]

    def __iter__(self):
        return iter(self.assignments)

    def __len__(self):
        return len(self.assignments)        

    def _fix(self, constraining_assignments, visited):
        asnlist  = Assignments([])
        for asgn in self.assignments:
            for name, value in constraining_assignments.items():
                # check if client assignment value fits that of a given assignment
                # if not, cancel the assignment
                if name in asgn and asgn[name] != value:
                    break
            else:
                asnlist.append(asgn)
        return asnlist



########################### samples ##############################################

class ExampleChart(Chart):

    @flow
    def r1(self, chooser):
        x = chooser.choose([0,1])
        y = chooser.choose([0,1])
        if x == 1:
            if y == 0:
                 z = 1
            else:
                 z = 0
        return vars()

    @flow
    def r2(self, chooser):
        z = chooser.choose([0,1])
        if z == 1:
            b = 1
        else:
            b = 0
        return vars()

    @flow
    def r3(self, chooser):
        p = chooser.choose([0,1])
        x = chooser.choose([0,1])
        if p == 1:
            if x == 0:
                 a = 1
            else:
                 a = 0
        return vars()

class CompositeChart(Chart):

    def f(self, chooser):
        x = chooser.choose([0,1])
        y = chooser.choose([2,3])
        return vars()

    def g(self, chooser):
        a = chooser.choose([0,1])
        b = chooser.choose([2,3])
        return vars()

    @flow
    def h(self, chooser):
        f_res = self.execute(self.f)
        g_res = self.execute(self.g)
        return list(f_res*g_res)


class Preferences(Chart):
    @flow
    def matching(self, chooser):
        "build all {'X': R1[i], 'Y':R2[j], 'Z':R3[k]} with i,j,k being pairwise distinct"
        R1 = [2, 5, 6]
        R2 = [3, 6, 5]
        R3 = [4, 6, 6]
        L = list(range(3))
        index = []
        for k in range(3):
            i = chooser.choose(L)
            L.remove(i)
            index.append(i)
        return {"X": R1[index[0]], "Y": R2[index[1]], "Z": R3[index[2]]}

class AlgebraicCSP(Chart):
    @flow
    def equation(self, chooser):
        # setup variable domains
        n = 30
        a = chooser.choose(range(1, n+1))
        b = chooser.choose(range(1, n+1))
        c = chooser.choose(range(1, n+1))

        # define the constraint
        if a<=b<=c and (a+b+c)**2 == a*b*c:
            return {"(a+b+c)**2 == a*b*c, with a<=b<=c and a,b,c in {1,...%s}"%n : (a,b,c)}

    @flow
    def primes(self, chooser):
        # setup variable domains
        M = 100
        K = int(M**0.5)
        p = chooser.choose(range(2,M))
        for k in range(2, K):
            if p!=k and p % k == 0:
                return {}
        return {"prime": p}


class DoorController(Chart):
    @flow
    def controller(self, chooser):
        states = [("*","start")]
        trans  = "T1:setTimer"
        while True:
            n = len(states)
            if trans in ("T1:setTimer", "T2:waitTimer"):
                states.append((trans, "wait"))            
                trans = chooser.choose(["T2:waitTimer", "T3:ready"])
            elif trans in ("T3:ready","T4:closing", "T12:timeout"):
                states.append((trans, "closing"))            
                trans = chooser.choose(["T4:closing", "T6:fullyClosed", 
                	                    "T5:buttonInterrupt"])
            elif trans in ("T6:fullyClosed","T7:closeTimer"):
                states.append((trans, "closed"))            
                trans = chooser.choose(["T7:closeTimer", "T8:open"])
            elif trans in ("T8:open","T9:opening"):
                states.append((trans, "opening"))  
                trans = chooser.choose(["T9:opening", "T10:fullyOpened"])          
            elif trans in ("T10:fullyOpened","T11:openTimer"):
                states.append((trans, "opened"))            
                trans = chooser.choose(["T11:openTimer", "T12:timeout"])          
            elif trans == "T5:buttonInterrupt":
                states.append((trans, "opening"))            
                trans = chooser.choose(["T9:opening", "T10:fullyOpened"])          

            # stop conditions
            if (len(states)>=2 and states[-1] == states[-2]) or len(states)>15:
                # no state repeatition
                return 
            if len(states)==10 and states[-1][1] == "closed":
                return tuple(states)

########################### tests ##############################################

def test_fix_and_filter():
    chart = ExampleChart()
    chart.create()
    assert list(chart.assignments) == [ {'y': 1, 'x': 1, 'z': 0},
                                        {'y': 0, 'x': 1, 'z': 1},
                                        {'y': 1, 'x': 0},
                                        {'y': 0, 'x': 0},
                                        {'b': 1, 'z': 1},
                                        {'b': 0, 'z': 0},
                                        {'a': 0, 'x': 1, 'p': 1},
                                        {'a': 1, 'x': 0, 'p': 1},
                                        {'x': 1, 'p': 0},
                                        {'x': 0, 'p': 0}]
    print("Initial assignments")
    print("-"*40)
    for asgn in chart:
        print(str(asgn)+",")

    print("\nFix x=1, y=0")
    print("-"*40)    
    S1 = list(chart.fix(x=1).fix(y=0))
    S2 = list(chart.fix(y=0).fix(x=1))
    S3 = list(chart.fix(x=1, y=0))
    assert len(S1) == len(S2) == len(S3)
    for s in S1:
        assert s in S2
        assert s in S3
    for asgn in chart.fix(x=1).fix(y=0):
        print(asgn)    

    print("\nFilter x=1, y=0")
    print("-"*40)    
    S1 = list(chart.filter(x=1).filter(y=0))
    S2 = list(chart.filter(y=0).filter(x=1))
    S3 = list(chart.filter(x=1, y=0))
    assert len(S1) == len(S2) == len(S3)
    for s in S1:
        assert s in S2
        assert s in S3
    for asgn in chart.filter(x=1).filter(y=0):
        print(asgn)    


def test_input_modification():
    prf = Preferences()
    prf.create()
    assert list(prf) == [{'Y': 6, 'X': 6, 'Z': 4},
                        {'Y': 3, 'X': 6, 'Z': 6},
                        {'Y': 5, 'X': 5, 'Z': 4},
                        {'Y': 3, 'X': 5, 'Z': 6},
                        {'Y': 5, 'X': 2, 'Z': 6},
                        {'Y': 6, 'X': 2, 'Z': 6}]

def test_fetch():
    acsp = AlgebraicCSP()
    acsp.create()
    primes = acsp.fetch("prime")
    assert primes == [97, 89, 83, 79, 73, 71, 67, 61, 59, 53, 47, 43, 41, 37, 31, 
                      29, 23, 19, 17, 13, 11, 7, 5, 3, 2]
    solutions = acsp.fetch('(a+b+c)**2 == a*b*c, with a<=b<=c and a,b,c in {1,...30}')
    assert solutions == [(9, 9, 9), (8, 8, 16), (6, 12, 18), (5, 20, 25)]
    print("primes", acsp.fetch("prime"))
    print("solutions of (a+b+c)**2 == a*b*c, with a<=b<=c and a,b,c in {1,...30} :", 
        solutions)

def test_door_controller():
    ctrl = DoorController()
    ctrl.create()
    assert len(ctrl) == 84
    for states in set(ctrl):
        print("(")
        for state in states:
            print(" ", state)
        print(")")
        break
    print("...")

def test_composite_chart():
    cs = CompositeChart()
    cs.create()
    assert len(cs) == 16
    assert all(len(x)==4 for x in cs)

def test_single_evaluation():
	def f(x,y, chooser = Chooser()):
	    z = chooser.choose([True, False])
	    if z:
	        return x+y
	    else:
	        return x-y
	assert f(1,2) == 3
	assert Chooser.apply(f,1,2) == [-1, 3]	

if __name__ == '__main__':
    test_fix_and_filter()
    test_input_modification()
    test_door_controller()
    test_fetch()
    test_composite_chart()
