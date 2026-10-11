"""Where does an idhazh command install its text-free crash printer?

The shared implementation uses the standard library alone, so programs that
run before dependencies are installed keep the same printer.
"""

from idhazh.event_lines import print_trace as print_trace
