import os
import sys
from Cython.Build import cythonize
from setuptools import Extension, setup

vi = sys.version_info
if vi < (3, 9):
    raise RuntimeError('picows requires Python 3.9 or greater')


if os.name == 'nt':
    libraries = ["Ws2_32"]
else:
    libraries = None

extensions = [
    Extension("websocket_benchmark.client_picows_cyt", ["websocket_benchmark/client_picows_cyt.pyx"], libraries=libraries),
]

setup(
    ext_modules=cythonize(
        extensions,
        compiler_directives={
            'language_level': vi[0],
            'profile': False,
            'nonecheck': False,
            'boundscheck': False,
            'wraparound': False,
            'initializedcheck': False,
            'optimize.use_switch': False,
            'cdivision': True
        },
        annotate=True,
        gdb_debug=False,
    )
)
