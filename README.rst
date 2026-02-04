Build C++ Boost.Beast websocket echo server and client
======================================================

1. Create or reuse some python virtual environment. I use conda environments but it could be anything.

.. code-block::

  $ conda create -n wsbench
  $ conda activate wsbench

2. Install conan. Conan is a C++ package manager (simular to pip).
  $ pip install conan

3. Initialize conan default profile

.. code-block::

  $ conan profile detect

4. Install C++ dependencies, create build project using default cmake generator.

.. code-block::

  $ conan install . --output-folder=build --build=missing
  $ cd build
  $ cmake .. -DCMAKE_TOOLCHAIN_FILE=conan_toolchain.cmake -DCMAKE_BUILD_TYPE=Release
  # Go back to the root folder
  $ cd ..

5. Build server and client

.. code-block::

  $ cmake --build ./build --parallel

6. Run websocket echo server. Must be run from the project root folder, otherwise it will complain about missing certificate. Server will listen on 2 ports, 9001: plain websocket, 9002: ssl websocket

.. code-block::

  $ ./build/src/ws_echo_server 127.0.0.1 9001 9002

7. Test websocket echo client. Must be run from the project root folder. After succeful run, the client will dumpl RPS to stdout.
  Usage: ws_echo_client <is_async{1|0} is_secure{1|0}> <host> <port> <msg_size> <duration_sec>

.. code-block::

  ./build/src/ws_echo_client 1 0 127.0.0.1 9001 256 10

Build python benchmark
======================

1. Install dependencies

.. code-block::

  $ pip install -r requirements.txt

2. Compile cython extensions

.. code-block::

  $ python setup.py build_ext --inplace

3. Run benchmark for 256 message size, 10 seconds duration per client. Run it from the project root folder. ws_echo_server should be run manually prior to running benchmark.

.. code-block::

  $ python -m websocket_benchmark.benchmark --msg-size 256 --duration 10


