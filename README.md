# geg

A groking tool for gcc/g++ error messages.

Install with:

`$ pip install geg`

Or, from local source:

`$ pip install -e .`

in the base repo directory.

Then, invoke gcc/g++, but preceding it with geg:

`$ python -m geg g++ ...`

It may behoove you to add a function to your `~/.bashrc:`

    function geg() {
            python3 -m geg $*
    }

    export -f geg


Then you can invoke it as:

`$ geg g++ ...`

Be aware that scripts might not be so great with interactive tools, so you may want to conditionally alias the invocation.
