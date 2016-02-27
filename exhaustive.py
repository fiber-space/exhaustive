from __future__ import print_function

__all__ = ["ChooserException", "Chooser", "flow", "Chart", "Assignments"]

class ChooserException(Exception):
    pass

class _ChooserEscape(Exception):
    "Only used for internal purposes. Don't ever catch this exception in your application code!"

class Chooser(object):
    """
    A Chooser is a close relative of John McCarthy's amb operator but designed with a different intention.     
    
    It is meant to evaluate in sequential order a given function with all possible values presented as choices by the Chooser.
    
    If f is a function defined as

        def f(chooser):
            ...
            x = chooser.choose([1,2,3,4])
            ...

    then 

        Chooser.apply(f)

    will evaluate f four times, one time for each choice made for x. This replicates the behavior of amb but the emphasis
    is on the evaluation protocol. The Chooser is not build to express one shot, indeterministic evaluation of f but 
    deterministic multiple evaluations of f. 
    """
    def __init__(self, chosen, stack):
        self._chosen  = chosen
        self._stack   = stack
        self._choosit = iter(chosen)

    def choose(self, choices):
        '''
        Method used to present a list of choices to a function which calls it. There are
        no constraints on the nature and multiplicity of those choices. 
        '''        
        try:
            # check for chosen value first
            c = next(self._choosit)
            if c not in choices:
                raise ChooserException("Program is not deterministic")
            return c
        except StopIteration:
            # if _choosit was exhausted, build for each value in choices a new
            # list which will be used as a new chosen list in a subsequent
            # iteration
            self._stack.extend([self._chosen + [choice] for choice in choices])
            # escape the caller of choose() for a next iteration with a fresh
            # chooser
            raise _ChooserEscape

    @classmethod
    def apply(chooser, f):            
        '''
        An inside-out evaluation of a function f given a chooser. 
        :param f: a function of a single chooser instance argument.
        '''
        results = []
        # collection of lists of choices
        stack   = [[]]
        while stack:
            chosen = stack.pop()
            try:
                res = f(chooser(chosen, stack))
                if res:
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
        Wrap a function into a Chart object and create all flows for that function.
        execute() returns the assignments of that Chart object.
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

    def fix(self, **assignments):
        '''
        Building a subset of assignments by using variable constraints or `facts`. The behavior
        is as follows

        The fix function doesn't act as a filter. If for example fix(x=1) passes a fact x=1 
        and A = {'y':0, 'a':5} is in the assignments list, then A will be accepted by fix(). A is
        'orthogonal' to the constraint imposed by x=1 and fix lets it pass. 

        Use filter() if A should be accepted if and only if A[name] exists and A[name] == value
        '''
        fixed = self.assignments.fix(**assignments)
        chart    = self.__class__(self.chooser)
        # accept only dependent solutions as valid assignments
        # for a derived chart
        chart.assignments = fixed
        return chart

    def filter(self, **assignments):
        chart = self.fix(**assignments)
        chart.assignments = chart.assignments.filter(**assignments)
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

    Here an "assignment" is a dict which originates from binding values to names in function scope. 
    Usually an assignment is the value of a function returning its vars()

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
        Building new assignments by updating each of this assignment set by each of the other.

        Note that this operation is not commutative, because update my destroy information.
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
                trans = chooser.choose(["T4:closing", "T6:fullyClosed", "T5:buttonInterrupt"])
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
    assert primes == [97, 89, 83, 79, 73, 71, 67, 61, 59, 53, 47, 43, 41, 37, 31, 29, 23, 19, 17, 13, 11, 7, 5, 3, 2]
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


if __name__ == '__main__':
    test_fix_and_filter()
    test_input_modification()
    test_door_controller()
    test_fetch()
    test_composite_chart()
