#!/usr/bin/python2
# Copyright 2019 Zacharier
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
import re
import commands
import os


WORK_PATH = os.path.join(os.getcwd(), '')


class BuildError(IOError): pass


def say(fmt, *args, **kwargs):
    colors = {
        'black': '\033[30m',
        'red': '\033[31m',
        'green': '\033[32m',
        'yellow': '\033[33m',
        'blue': '\033[34m',
        'purple': '\033[35m',
        'azure': '\033[36m',
        'white': '\033[37m',
        None: '\033[0m',
    }
    which = kwargs.get('color')
    fmt = str(fmt)
    print colors[which] + (args and fmt % args or fmt) + '\033[0m'


class Block:
    def __init__(self, target='', deps='', command=''):
        self.target = target
        self.deps = deps
        self.command = command

    def __str__(self):
        if self.target:
            s = '%s : %s' % (self.target, self.deps)
            if self.command:
                s += '\n\t%s' % self.command
            return s
        return ''


class OutputBlock(Block):
    def __init__(self, target, sources):
        self.target = target
        self.deps = ''

        dirs = ['bin', 'lib'] + sorted(
                set((os.path.dirname(source) for source in sources)))

        self.command = '\n\t'.join(
                ('mkdir -p ' + os.path.join(target, dir) for dir in dirs))


class CompileBlock(Block):
    def __init__(self, fname, deps, args):
        name, _ = os.path.splitext(fname)
        self.target = '%s%s.o' % (args['output'], name)
        args['target'] = self.target
        args['sources'] = fname
        self.deps = deps
        fmt = '%(compiler)s -o %(target)s -fPIC -c %(includes)s %(cxx_flags)s %(sources)s'
        self.command = fmt % args


class LinkBlock(Block):
    def __init__(self, target, objs, visibility, args):
        self.target = '%sbin/%s' % (args['output'], target)
        args['target'] = self.target
        args['visibility'] = 'default' if visibility else 'hidden'
        self.deps = objs
        args['objs'] = objs
        fmt = '%(compiler)s -o %(target)s -fvisibility=%(visibility)s -Wl,-E %(objs)s '\
              '-Xlinker "-(" -Wl,--whole-archive %(ld_libs)s '\
              '-Wl,--no-whole-archive -Xlinker "-)" %(ld_flags)s'

        self.command = fmt % args


class StaticBlock(Block):
    def __init__(self, target, objs, visibility, args):
        self.target = '%slib/lib%s.a' % (args['output'], target)
        args['target'] = self.target
        args['visibility'] = 'default' if visibility else 'hidden'
        self.deps = objs
        args['objs'] = objs

        self.command = 'ar rcs %(target)s %(objs)s' % args


class SharedBlock(Block):
    def __init__(self, target, objs, visibility, args):
        self.target = '%slib/lib%s.so' % (args['output'], target)
        args['target'] = self.target
        args['visibility'] = 'default' if visibility else 'hidden'
        self.deps = objs
        args['objs'] = objs

        fmt = '%(compiler)s -o %(target)s -fvisibility=%(visibility)s -shared -fPIC %(objs)s '\
              '-Xlinker "-(" %(ld_flags)s -Xlinker "-)"'
        self.command = fmt % args


class CleanBlock(Block):
    def __init__(self, objs):
        self.target = 'clean'
        self.deps = ''
        self.command = '-rm -fr %s' % ''.join(filter(lambda x:x, objs))


class Makefile:

    def __init__(self, args, dep_table):
        self._args = args
        self._blocks = []
        self._products = []
        self._dep_table = dep_table
        self._set = set()

    def setup(self, name, source, visibility, block_type):
        blocks = []
        for item in source:
            if item not in self._set:
                blocks.append(CompileBlock(item, self._dep_table[item], dict(self._args)))
                self._set.add(item)
        objs = ' '.join((block.target for block in blocks))
        product = block_type(name, objs, visibility, dict(self._args))
        self._blocks.extend(blocks)
        self._products.append(product)

    def write(self):
        blocks = []
        blocks.append(Block('all', 'build ' + ' '.join(
            (product.target for product in self._products))))
        blocks.append(Block())
        blocks.append(OutputBlock('build', self._dep_table.keys()))
        blocks.append(Block())
        blocks.extend(self._products)
        blocks.append(Block())
        blocks.extend(self._blocks)

        deletes = ' '.join([block.target for block in blocks[1:]][::-1])
        blocks.append(Block())
        blocks.append(Block('.PHONY', 'clean'))
        blocks.append(CleanBlock(deletes))

        with open('Makefile', 'w') as f:
            for block in blocks:
                f.write(str(block))
                f.write('\n')


class ProgressBar:
    def __init__(self, capacity, width=50):
        self._capacity = capacity
        self._size = 0
        self._width = width
        self._curr = 0
        self._print()

    def __enter__(self, *args):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self._curr = self._width
            self._print()
        sys.stdout.write('\n')
        sys.stdout.flush()

    def forward(self):
        self._size += 1
        percent = float(self._size) / self._capacity
        curr = int(percent * self._width)
        if self._curr != curr:
            self._curr = curr
            self._print()

    def _print(self):
        num_total = (len(str(self._capacity)), ) * 2
        line = '\r%%%dd/%%%dd |' % num_total
        line = line % (self._size, self._capacity)
        line += '=' * self._curr
        line += '>'
        line += ' ' * (self._width - self._curr)
        line += '| %3d%%' % int(float(self._curr) / self._width * 100)
        sys.stdout.write(line)
        sys.stdout.flush()


class Builder:
    def __init__(self):
        self.compiler = 'g++'
        self.c_flags = []
        self.cxx_flags = []
        self.ld_flags = []
        self.ld_libs = []
        self.includes = []
        self.output = 'build/'
        self.sources = []

        self.products = []

    def add_app(self, name, sources, visibility):
        self.products.append((name, sources, visibility, LinkBlock))

    def add_static(self, name, sources, visibility):
        self.products.append((name, sources, visibility, StaticBlock))

    def add_shared(self, name, sources, visibility):
        self.products.append((name, sources, visibility, SharedBlock))

    def analyze(self):
        pattern = re.compile(r'#include\s+"([^"]+)"')
        htable = {}
        def find(source, deps):
            with open(source) as f:
                headers = pattern.findall(f.read())
                for header in headers:
                    found = False
                    for include in self.includes:
                        path = os.path.join(include, header)
                        if path in htable:
                            deps.extend(htable[path])
                            found = True
                            break
                        if os.path.exists(path):
                            deps.append(path)
                            local_deps = []
                            find(path, local_deps)
                            htable[path] = local_deps
                            deps.extend(local_deps)
                            found = True
                            break
                    if not found:
                        raise BuildError('Not Found: %s' % header)

        source_set = set()
        for _, sources, __, ____ in self.products:
            source_set.update(sources)
        source_size = len(source_set)
        say('collected %d sources', source_size)
        table = {}
        with ProgressBar(source_size) as bar:
            for source in sorted(source_set):
                deps = []
                find(source, deps)
                table[source] = source + ' ' + ' '.join(deps)
                bar.forward()
        return table


    def args(self):
        return {
            'c_flags': ' '.join(self.c_flags),
            'cxx_flags': ' '.join(self.cxx_flags),
            'ld_flags': '\\\n '.join(self.ld_flags),
            'ld_libs': '\\\n '.join(self.ld_libs),
            'includes': ' '.join(('-I %s' % arg for arg in self.includes)),
            'output': self.output,
            'compiler': self.compiler
        }

    def build(self):
        dep_table = self.analyze()
        makefile = Makefile(self.args(), dep_table)
        for product in self.products:
            makefile.setup(*product)
        makefile.write()


builder = Builder()


def COMPILER(path):
    builder.compiler = path

def C_FLAGS(*args):
    builder.c_flags.extend(args)

def CXX_FLAGS(*args):
    builder.cxx_flags.extend(args)

def LD_FLAGS(*args):
    builder.ld_flags.extend(args)

def LD_LIBS(*args):
    builder.ld_libs.extend(args)

def INCLUDE(*args):
    builder.includes.extend(args)

def OUTPUT(path):
    builder.output = path

def SOURCE(*args):
    sources = []
    for path in args:
        # parent = os.path.dirname(path)
        if os.path.isfile(path):
            sources.append(path)
            continue
        elif os.path.isdir(path):
            os.path.join(path, '*')
        ret, text = commands.getstatusoutput('ls ' + path)
        if ret == 0:
            for item in text.split('\n'):
                sources.append(item)
    return sources

def APPLICATION(name, source, visibility=True):
    builder.add_app(name, source, visibility)

def STATIC_LIBRARY(name, source, visibility=True):
    builder.add_static(name, source, visibility)

def SHARED_LIBRARY(name, source, visibility=True):
    builder.add_shared(name, source, visibility)


if __name__ == '__main__':
    exec(open('BUILD').read(), globals())
    try:
        builder.build()
    except Exception as e:
        say(e, color="red")
