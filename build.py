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


ARGS = {
    'compiler': 'g++',
    'c_flags': '',
    'cxx_flags': '',
    'ld_flags': '',
    'includes': '',
    'output': 'build/'
}

WORK_PATH = os.path.join(os.getcwd(), '')

def COMPILER(path):
    ARGS['compiler'] = path

def C_FLAGS(*args):
    ARGS['c_flags'] = ' '.join(args)

def CXX_FLAGS(*args):
    ARGS['cxx_flags'] = ' '.join(args)

def LD_FLAGS(*args):
    flags = ARGS['ld_flags'] and ARGS['ld_flags'] + ' '
    ARGS['ld_flags'] = flags + ' '.join(args)

LD_LIBS = LD_FLAGS

def INCLUDE(*args):
    ARGS['includes'] = ' '.join(('-I %s' % arg for arg in args))

def SOURCE(*args):
    sources = []
    for arg in args:
        path = arg
        # path = os.path.join(WORK_PATH, arg)
        parent = os.path.dirname(path)
        if os.path.isfile(arg):
            sources.append(arg)
            continue
        elif os.path.isdir(arg):
            os.path.join(path, '*')
        ret, text = commands.getstatusoutput('ls ' + path)
        if ret == 0:
            for item in text.split('\n'):
                sources.append(item)
    return sources

def OUTPUT(path):
    ARGS['output'] = path

class Makefile:
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
        def __init__(self, fname):
            name, _ = os.path.splitext(fname)
            args = dict(ARGS)
            self.target = '%s%s.o' % (args['output'], name)
            args['target'] = self.target

            self.deps = fname
            args['deps'] = self.deps

            is_cpp = any(self.deps.endswith(suffix)
                    for suffix in ('.cpp', '.cc'))
            fmt = '%(compiler)s -o %(target)s -c %(includes)s %(cxx_flags)s %(deps)s'
            self.command = fmt % args

    class LinkBlock(Block):
        def __init__(self, target, objs):
            args = dict(ARGS)
            self.target = '%sbin/%s' % (args['output'], target)
            args['target'] = self.target

            self.deps = objs
            args['deps'] = objs

            fmt = '%(compiler)s -o %(target)s %(cxx_flags)s %(deps)s %(ld_flags)s'
            self.command = fmt % args

    class StaticBlock(Block):
        def __init__(self, target, objs):
            args = dict(ARGS)
            self.target = '%slib/lib%s.a' % (args['output'], target)
            args['target'] = self.target

            self.deps = objs
            args['deps'] = objs

            self.command = 'ar rcs %(target)s %(deps)s' % args

    class SharedBlock(Block):
        def __init__(self, target, objs):
            args = dict(ARGS)
            self.target = '%slib/lib%s.so' % (args['output'], target)
            args['target'] = self.target

            self.deps = objs
            args['deps'] = objs

            fmt = '%(compiler)s -o %(target)s -shared -fPIC %(deps)s '\
                  ' -Xlinker "-(" %(ld_flags)s -Xlinker "-)"'
            self.command = fmt % args

    class CleanBlock(Block):
        def __init__(self, objs):
            self.target = 'clean'
            self.deps = ''
            self.command = '-rm -fr %s' % ''.join(filter(lambda x:x, objs))

    def __init__(self, args):
        self._args = args
        self._blocks = []
        self._products = []
        self._sources = []
        self._set = set()


    def setup(self, name, source, block_type):
        blocks = []
        for item in source:
            if item not in self._set:
                blocks.append(self.CompileBlock(item))
                self._set.add(item)
        objs = ' '.join((block.target for block in blocks))
        product = block_type(name, objs)
        self._blocks.extend(blocks)
        self._products.append(product)
        self._sources.extend(source)

    def setup_execute(self, name, source):
        return self.setup(name, source, self.LinkBlock)

    def setup_shared(self, name, source):
        return self.setup(name, source, self.SharedBlock)

    def setup_static(self, name, source):
        return self.setup(name, source, self.StaticBlock)

    def build(self):
        blocks = []
        blocks.append(self.Block('all', 'build ' + ' '.join(
            (product.target for product in self._products))))
        blocks.append(self.Block())
        blocks.append(self.OutputBlock('build', self._sources))
        blocks.append(self.Block())
        blocks.extend(self._products)
        blocks.append(self.Block())
        blocks.extend(self._blocks)

        deletes = ' '.join([block.target for block in blocks[1:]][::-1])
        blocks.append(self.Block())
        blocks.append(self.Block('.PHONY', 'clean'))
        blocks.append(self.CleanBlock(deletes))
        self._blocks = blocks
        return self

    def write(self):
        with open('Makefile', 'w') as f:
            for block in self._blocks:
                f.write(str(block))
                f.write('\n')


makefile = Makefile(ARGS)
def APPLICATION(name,
        source=None,
        visibility=False,
        deps=False):
    makefile.setup_execute(name, source)

def STATIC_LIBRARY(name, source=None, visibility=False):
    makefile.setup_static(name, source)

def SHARED_LIBRARY(name, source=None, visibility=False):
    makefile.setup_shared(name, source)


if __name__ == '__main__':
    exec(open('BUILD').read(), globals())
    makefile.build().write()

