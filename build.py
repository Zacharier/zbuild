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
import commands
import os
import re
import sys
import time


LOGO = '''\
 __________________________________________________________
|                                                          |
|  .______    __   __    __     .______    __   __    __   |
|  |   _  \  |  | |  |  |  |    |   _  \  |  | |  |  |  |  |
|  |  |_)  | |  | |  |  |  |    |  |_)  | |  | |  |  |  |  |
|  |   _  <  |  | |  |  |  |    |   _  <  |  | |  |  |  |  |
|  |  |_)  | |  | |  `--'  |    |  |_)  | |  | |  `--'  |  |
|  |______/  |__|  \______/     |______/  |__|  \______/   |
|                                                          |
|__________________________________________________________|
'''

class BuildError(IOError): pass


def say(fmt, *args, **kwargs):
    """
    Print a formatted message with a specified color.
    """
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
    nl = kwargs.get('nl', '\n')
    fmt = str(fmt)
    sys.stdout.write(colors[which] + (args and fmt % args or fmt) + '\033[0m')
    sys.stdout.write(nl)
    sys.stdout.flush()


def break_str(deps):
    return ' \\\n\t'.join(deps)


class MakeRule:
    """
    Generate a makefile rule which has a following style:
    TARGETS: PREREQUISITES (; COMMAND)
        COMMAND
    """
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


class OutputRule(MakeRule):
    """
    Generate a rule which creates output directories.
    """
    def __init__(self, target, sources):
        self.target = target
        self.deps = ''
        dirs = ['bin', 'lib'] + sorted(
                set((os.path.dirname(source) for source in sources)))

        self.command = '\n\t'.join(
                ('mkdir -p ' + os.path.join(target, dir) for dir in dirs))


class CompileRule(MakeRule):
    """
    Generate a rule which compiles source file to object file.
    """
    def __init__(self, fname, deps, args):
        name, _ = os.path.splitext(fname)
        self.target = '%s%s.o' % (args['output'], name)
        args['target'] = self.target
        args['sources'] = fname
        self.deps = break_str(deps)
        fmt = '%(compiler)s -o %(target)s -fPIC -c %(includes)s '\
            '%(cxx_flags)s %(sources)s'
        self.command = fmt % args


class LinkRule(MakeRule):
    """
    Generate a rule which links some object files.
    """
    def __init__(self, target, objs, visibility, args):
        self.target = '%sbin/%s' % (args['output'], target)
        args['target'] = self.target
        args['visibility'] = 'default' if visibility else 'hidden'
        self.deps = args['objs'] = break_str(objs)
        fmt = '%(compiler)s -o %(target)s -fvisibility=%(visibility)s '\
            '-Wl,-E %(objs)s -Xlinker "-(" -Wl,--whole-archive %(ld_libs)s '\
            '-Wl,--no-whole-archive -Xlinker "-)" %(ld_flags)s'
        self.command = fmt % args


class StaticRule(MakeRule):
    """
    Generate a rule which archive some object files to an archived file.
    """
    def __init__(self, target, objs, visibility, args):
        self.target = '%slib/lib%s.a' % (args['output'], target)
        args['target'] = self.target
        args['visibility'] = 'default' if visibility else 'hidden'
        self.deps = args['objs'] = break_str(objs)
        self.command = 'ar rcs %(target)s %(objs)s' % args


class SharedRule(MakeRule):
    """
    Generate a rule which links some object files to a so(shared object) file.
    """
    def __init__(self, target, objs, visibility, args):
        self.target = '%slib/lib%s.so' % (args['output'], target)
        args['target'] = self.target
        args['visibility'] = 'default' if visibility else 'hidden'
        self.deps = args['objs'] = break_str(objs)
        fmt = '%(compiler)s -o %(target)s -fvisibility=%(visibility)s '\
            '-shared -fPIC %(objs)s -Xlinker "-(" %(ld_flags)s -Xlinker "-)"'
        self.command = fmt % args


class CleanRule(MakeRule):
    """
    Generate a rule which cleans all of files generated by makefile.
    """
    def __init__(self, objs):
        self.target = 'clean'
        self.deps = ''
        self.command = '-rm -fr %s' % break_str(filter(lambda x:x.strip(),
            objs))


class Makefile:
    """
    Collect all of rules and generate a makefile file.
    """

    __notice__ = '\n'.join((
        '# file : Makefile',
        '# brief: this file was generated by `biu`',
        '# date : %s' % time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    ))

    def __init__(self, args, dep_table):
        self.args = args
        self.rules = []
        self.products = []
        self.dep_table = dep_table
        self.set = set()

    def setup(self, name, source, visibility, rule_type):
        rules = []
        for item in source:
            if item not in self.set:
                rules.append(CompileRule(item, self.dep_table[item], dict(self.args)))
                self.set.add(item)
        # objs = '\n\t'.join((rule.target for rule in rules))
        objs = (rule.target for rule in rules)
        product = rule_type(name, objs, visibility, dict(self.args))
        self.rules.extend(rules)
        self.products.append(product)

    def write(self):
        rules = []
        rules.append(MakeRule('all', 'build ' + ' '.join(
            (product.target for product in self.products))))
        rules.append(MakeRule())
        rules.append(OutputRule('build', self.set))
        rules.append(MakeRule())
        rules.extend(self.products)
        rules.append(MakeRule())
        rules.extend(self.rules)
        deletes = [rule.target for rule in rules[1:]][::-1]
        rules.append(MakeRule())
        rules.append(MakeRule('.PHONY', 'clean'))
        rules.append(CleanRule(deletes))

        with open('Makefile', 'w') as f:
            f.write(self.__notice__)
            f.write('\n')
            f.write('\n')
            for rule in rules:
                f.write(str(rule))
                f.write('\n')


class ProgressBar:
    """
    Print a progress bar in terminal.
    """
    def __init__(self, capacity, width=50):
        self.capacity = capacity
        self.size = 0
        self.width = width
        self.curr = 0
        self.pprint()

    def __enter__(self, *args):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.curr = self.width
            self.pprint()
        sys.stdout.write('\n')
        sys.stdout.flush()

    def forward(self):
        self.size += 1
        percent = float(self.size) / self.capacity
        curr = int(percent * self.width)
        if self.curr != curr:
            self.curr = curr
            self.pprint()

    def pprint(self):
        num_total = (len(str(self.capacity)), ) * 2
        line = '\r%%%dd/%%%dd |' % num_total
        line = line % (self.size, self.capacity)
        line += '=' * self.curr
        line += '>'
        line += ' ' * (self.width - self.curr)
        line += '| %3d%%' % int(float(self.curr) / self.width * 100)
        sys.stdout.write(line)
        sys.stdout.flush()


class Builder:
    """
    A core which controls how to genertate a makefile.
    additionally, in order to generate valid commands,
    it always verifies dependent files before making a makefile.
    """
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
        self.products.append((name, sources, visibility, LinkRule))

    def add_static(self, name, sources, visibility):
        self.products.append((name, sources, visibility, StaticRule))

    def add_shared(self, name, sources, visibility):
        self.products.append((name, sources, visibility, SharedRule))

    def analyze(self):
        pattern = re.compile(r'^#include\s+"([^"]+)"', re.M)
        where = None
        includes = []
        htable = {}
        def find(source, deps):
            with open(source) as f:
                headers = pattern.findall(f.read())
            for header in headers:
                # if 'client_api.h' in header:
                subdir = os.path.dirname(header)
                #     if subdir:
                #         print os.path.join(parent, subdir)
                #         includes.append(os.path.join(parent, subdir))
                found = False
                for include in includes:
                    path = os.path.join(include, header)
                    if path.startswith('./'): path = path[2:]
                    if path in htable:
                        #deps.extend(htable[path])
                        found = True
                        break
                    if os.path.exists(path):
                        if subdir:
                            includes.append(os.path.dirname(path))
                        deps.append(path)
                        local_deps = []
                        htable[path] = local_deps
                        find(path, local_deps)
                        deps.extend(local_deps)
                        found = True
                        break
                if not found:
                    raise BuildError('Not Found: %s in %s' % (header, where))

        source_set = set()
        for _, sources, __, ____ in self.products:
            source_set.update(sources)
        source_size = len(source_set)
        say('Collected %d sources', source_size)
        say('Analyzing dependences...')
        table = {}
        with ProgressBar(source_size) as bar:
            for source in sorted(source_set):
                where = source
                includes = list(self.includes)
                deps = [source]
                find(source, deps)
                table[source] = deps
                bar.forward()
        return table


    def args(self):
        return {
            'c_flags': ' '.join(self.c_flags),
            'cxx_flags': ' '.join(self.cxx_flags),
            'ld_flags': ' '.join(self.ld_flags),
            'ld_libs': break_str(self.ld_libs),
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
    say(LOGO)
    try:
        exec(open('BUILD').read(), globals())
        builder.build()
    except Exception as e:
        say(e, color="red")
