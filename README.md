# exhaustive
Python library to support exhaustive testing and model checking

## Introduction

This is a single file Python project featuring the `exhaustive.py` module. 

When we talk about "exhaustive testing" we usually don't mean that all possible inputs and
outputs of a function will be checked but rather a simplified model of the function in the 
form of a state machine. The `exhaustive.py` library implements my favorite approach to this
problem using the `chooser` design pattern, which should be introduced here.

Historically, choosers have been invented by John McCarthy with a quite different intention
and under a different name. They are McCarthy's infamous `amb` operator in disguise. McCarthy 
wanted to express ambiguous or indeterministic computations, something which looks quite 
challening and for that reason `amb` has survived as some piece of recreational computing science
esoterics which entertains programmers. The name `chooser` goes back to an independent re-invention 
by a group of researchers who were examining exhaustive testing strategies in the context of 
the Unix kernel. That's also the use of the word I'll make here.

### Programming state machines

The biggest take away is that you can build state machine models that can be used to derive test
cases in the very same way you build state machines to handle user input or program flow in ordinary 
programs. You don't need a domain specific language to express state machines as graphs, neither 
do you have to spend your time drawing UML diagrams and fiddle with source code generators. A typical 
function using a `chooser` looks like this

	def f(chooser):
		state = "S0"
		sequence = ["S0"]
		while True:
			if state == "S0":
				state = chooser.choose(["S1", "S2"])
				sequence.append(state)
			elif state == "S1":
				state = chooser.choose(["S1", "S3", "S5"])
				sequence.append(state)
			...
			if failure_condition(sequence):
				return 
			elif success_condition(sequence):
				return sequence
			# just continue

The chooser provides *one* of the values in the list. You can consider this as an "ambiguous computation" but the function
is meaningless without a particular evaluation stratgey implemented by the chooser. The chooser invokes the function many
times, s.t. *all* possible values in the argument lists of choose() i.e. all possible choices will be made, something which
is fully deterministic. Actually, since choose() is evaluated in a while loop, all possible choices will be made an arbitrary 
number of times.

When we call 

	res = Chooser.apply(f)

a list of all possible state sequences is returned which meet the `success_condition()` called by the function `f`.

The success and failure conditions are guards which are required for program termination. Without them the implemented
state machine would loop forever. The magical bit is in the interaction between the call of `chooser.choose()` and
`Chooser.apply()` ( here `chooser` is an instance and `Chooser` its class ). The implementation is very brief though
and I recommend to look at the commented source code of the chooser implementation to get an intuitive understanding.

### What can we do with state sequences?

Generating all possible state sequences which meet the success conditions isn't a fully generated testcase and it is 
not intended to be one. The actual testcase implementation will be specific for the system under test. Giving meaning to 
the states {"S0", "S1", ...} and state transitions is out of the scope for a library such as `exhaustive.py`. In my 
experience the interpreter of state sequences is also a rather short piece of code which I would just program straight
away instead of considering the use of source code generators and other overengineered approaches. It suffices to 
shorten the testcase specification and set an end to far too many buggy test scripts, which cover half of the state 
transition diagram of some technical specification.

### exhaustive.py is fun to use!

The chooser approach we used to derive flows through a state machine can be applied to widely varying domains
of computational problem solving which otherwise need dedicated systems and techniques such as computer algebra systems 
and constraint satisfaction solvers.

For example, the following function below finds all solutions of the equation `(a+b+c)**2 == a*b*c` for a,b,c in {1,...,30}
with a<=b<=c:

    def equation(chooser):
        n = 30
        a = chooser.choose(range(1, n+1))
        b = chooser.choose(range(1, n+1))
        c = chooser.choose(range(1, n+1))
        
        if a<=b<=c and (a+b+c)**2 == a*b*c:
            return (a,b,c)

If we evaluate it with

	Chooser.apply(equation)            

we get the results

	(9, 9, 9), (8, 8, 16), (6, 12, 18), (5, 20, 25)

The implementation is naive but effortless. There is really nothing more about it than the chooser evaluation 
trick.








