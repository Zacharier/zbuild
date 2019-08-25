
COMPILER('g++')
CXX_FLAGS('-g -Wall -O0 -std=c++11')
LD_FLAGS('-pthread')
LD_LIBS('~/.local/lib/libgtest.a')

INCLUDE('include')

STATIC_LIBRARY('hello', source=SOURCE('src/hello.cc'))
SHARED_LIBRARY('hello', source=SOURCE('src/hello.cc'))
APPLICATION('hello', source=SOURCE('src/*.cc'))
