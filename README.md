# Build

The Build is a simple but powerful `Makefile` generator, which generates a `Makefile` by a `BUILD` file located to the root path of project. In the progress of building, it can deductions relationships of dependency between source files. In addtion, it also can watch some files were updated or deleted or added and re-generate a new `Makefile`.

NOTE: The user should executes `make` command after building is complete.

## How to use

The help of this tool is as follows:

```shell
Usage:
  biu <command> [options]

Commands:
  help      Show help
  create    Create BUILD file
  build     Build project and create a makefile
  clean     Clean this project
  version   Show version

```

## Create BUILD

A Simplest method to create a `BUILD` if you have only source file:

```shell
echo "BINARY('app', ['src/main.cc'])" > BUILD
```

Another method to create a `BUILD` is automatic generation by Build, eg:

```shell
python build.py create
```

The generated BUILD was placed to current directory, `cat` the content:

```
CC('gcc')

CXX('g++')

# PROTOC('protoc')

CFLAGS('-g -pipe -Wall -std=c99')

CXXFLAGS('-g -pipe -Wall -std=c++11')

LDFLAGS('-L.')

LDLIBS('-lpthread')

BINARY('app', includes=['src/'], sources=['src/*.cc', 'src/*.cpp'])
```

### Execute BUILD

A typical structure of project is as follows:

```shell
$ ls
BUILD  build.py  LICENSE  protos  README.md  src
$ ls src/
foo.cc  foo.h  main.cc
$ ls protos/
person.pb.cc  person.pb.h  person.proto
```

The `Makefile` was generated after executing `python build.py build`, then need to excute `make` to compile and link the program. Finallay, a executable binary file was built in the path:

```shell
$ ls output/build/bin/app
output/build/bin/app
```

## Contribute

## Bug Report
