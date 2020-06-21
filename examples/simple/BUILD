CC('gcc')

CXX('g++')

# PROTOC('protoc')

CFLAGS('-g -pipe -Wall -std=c99')

CXXFLAGS('-g -pipe -Wall -std=c++11')

LDFLAGS('-L.')

LDLIBS('-lpthread')

BINARY('app', includes=['src/'], sources=['src/*.cc', 'src/*.cpp'])
