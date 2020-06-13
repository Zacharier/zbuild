#!/usr/bin/python2
#
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

"""
https://www.gnu.org/software/make/manual/make.html
"""

import commands
import glob
import os
import re
import shelve
import shutil
import sys
import time

__version__ = '1.0.0'

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


class ArgError(BuildError): pass


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
    # sys.stdout.write(time.strftime('%Y-%m-%d %H:%M:%S ', time.localtime()))
    sys.stdout.write(colors[which] + (args and fmt % args or fmt) + '\033[0m')
    sys.stdout.write(nl)
    sys.stdout.flush()


def break_str(prereqs):
    """
    Break a string into multiline text.
    """
    return ' \\\n\t'.join(prereqs)


class Options:
    """
    A parsed options from command line.
    """

    def __init__(self, args=None):
        self._args = args or {}

    def get(self, name):
        return self._args.get(name)

    def __getattr__(self, name):
        try:
            return self._args[name]
        except KeyError:
            return None

    def __getitem__(self, name):
        return self._args[name]

    def __setitem__(self, name, val):
        self._args[name] = val

    def __contains__(self, name):
        return name in self._args

    def __str__(self):
        return str(self._args)


class OptionsParser:
    """
    Parse command line into a options object.
    """

    def __init__(self):
        self._args = {}
        self._actions = {}
        self.add_option('--help', help='Show this help',
                        typo='bool', default=False)

    def add_option(self, option, help, typo='str',
                   required=False, default=None):
        self._actions[option] = (typo, help, required, default)
        if not required:
            self._args[option] = default

    def parse_args(self, argv):
        def convert(key, s):
            types = {
                'str': str,
                'int': int,
                'float': float,
            }
            try:
                return types[key](s)
            except KeyError:
                return None

        if '--help' in argv:
            raise ArgError()

        opts = Options(self._args)
        size = len(argv)
        i = 0
        while i < size:
            arg = argv[i]
            if arg not in self._actions:
                raise ArgError('option %s is unrecognized' % arg)
            typo, _, __, ___ = self._actions[arg]
            if typo == 'bool':
                opts[arg[2:]] = True
            else:
                i += 1
                if i == size:
                    raise ArgError('option %s: too few arguments' % arg)
                val = convert(typo, argv[i])
                if val is None:
                    raise ArgError(
                        'option %s: %s is required' % (arg, typo))
                opts[arg[2:]] = val
            i += 1
        for option, (_, _, required, _) in self._actions.iteritems():
            if required and option[2:] not in opts:
                raise ArgError('option %s is required' % option)
        return opts

    def help(self, cmd='general'):
        s = cmd.title() + ' Options:\n'
        last = ''
        for key, (_, help, __, ___) in self._actions.iteritems():
            if '--help' == key:
                last = '  %-20s %s\n' % (key, help)
            else:
                s += '  %-20s %s\n' % (key, help)
        return s + last


class ArgumentParser:
    """
    Parse command and options from command line.
    """

    def __init__(self, version=None):
        self._commands = []
        self._command_map = {}
        self._version = version

        self.add_command('version', 'Show version')
        self.add_command('help', 'Show help')

    def usage(self, command='<command>'):
        return 'Usage:\n  biu %s [options]\n\n' % command

    def add_command(self, command, help, option_parser=None):
        self._commands.insert(-1, command)
        self._command_map[command] = (help, option_parser)

    def parse(self, argv):
        if len(argv) == 0 or argv[0] == 'help':
            self.print_help(self.help())
        if self._version and argv[0] == 'version':
            self.print_version(self._version)
        if argv[0] not in self._command_map:
            self.print_help(self.help(), 'command %s: unrecognized' % argv[0])
        _, parser = self._command_map[argv[0]]
        if parser is None:
            return argv[0], None
        try:
            options = parser.parse_args(argv[1:])
            return argv[0], options
        except ArgError as e:
            self.print_help(self.usage('build') + parser.help(argv[0]), e)

    def print_help(self, help=None, error=None, stream=sys.stdout):
        lines = [help or self.help()]
        if isinstance(error, ArgError):
            error = str(error)
        if error:
            lines.append(error)
        stream.write('\n'.join(lines))
        stream.write('\n')
        sys.exit(-1 if error else 0)

    def print_version(self, version):
        sys.stdout.write(version)
        sys.stdout.write('\n')
        sys.exit(0)

    def help(self):
        h = self.usage()
        h += 'Commands:\n'
        for cmd in self._commands:
            h += '  %-10s%s\n' % (cmd, self._command_map[cmd][0])
        return h


class Scope(dict):
    """
    A two level dict.
    """

    def __init__(self, d):
        dict.__init__(self)
        self._parent = d

    def __getitem__(self, key):
        try:
            return dict.__getitem__(self, key)
        except KeyError:
            return self._parent[key]

    def __setitem__(self, key, val):
        return dict.__setitem__(self, key, val)


class Flags(list):
    def __str__(self):
        return ' '.join(iter(self))


class LdLibs(list):
    def __str__(self):
        return break_str(iter(self))


class Includes(list):
    def __str__(self):
        return ' '.join(('-I %s' % arg for arg in iter(self)))


class Storage:
    """
    Load a shelve db and compare with current cache.
    """

    def __init__(self, path='.biu'):
        if not os.path.exists(path):
            os.mkdir(path)

        self._cache = {}
        self._db = shelve.open(os.path.join(path, 'targets'))

    def set(self, target, prereqs, command, is_obj):
        self._cache[target] = (prereqs, command, is_obj)

    def save(self):
        if self._db:
            self.compare()

        self._db.clear()
        self._db.update(self._cache)
        self._db.close()

    def compare(self):

        def delete(fname):
            if os.path.exists(fname):
                os.remove(fname)

        updated_keys = set()
        for target, (prereqs, command, is_obj) in self._cache.iteritems():
            pair = self._db.get(target)
            if pair:
                old_prereqs, old_command, _ = pair
                if prereqs != old_prereqs or command != old_command:
                    delete(target)
                    updated_keys.add(target)
            else:
                updated_keys.add(target)

        expired_keys = set(self._db.keys()) - set(self._cache.keys())
        for key in expired_keys:
            delete(key)

        def clean_artifact(table, invalid_keys):
            for target, (prereqs, _, is_obj) in table.iteritems():
                if is_obj: continue
                if set(prereqs) & invalid_keys:
                    delete(target)
                    break

        clean_artifact(self._db, expired_keys)
        clean_artifact(self._cache, updated_keys)


class MakeRule:
    """
    Generate a makefile rule which has a following style:
    TARGETS: PREREQUISITES (; COMMAND)
        COMMAND
    """

    def __init__(self, target, prereqs=(), command=''):
        self._target = target
        self._prereqs = prereqs
        self._command = command

    def target(self):
        return self._target

    def prereqs(self):
        return self._prereqs

    def command(self):
        return self._command

    def __str__(self):
        prereqs = break_str(self._prereqs) if hasattr(self, '_prereqs') else ''
        s = '%s : %s' % (self._target, prereqs)
        if self._command:
            s += '\n\t%s' % self._command
        return s


class CompileRule(MakeRule):
    """
    Generate a rule which compiles source file to object file.
    """

    def __init__(self, fname, prereqs, args, artifact):
        target = os.path.join(args['output'], 'objs',
                              fname + '.' + artifact + '.o')
        args['target'] = target
        args['sources'] = fname
        cc_fmt = '%(cc)s -o %(target)s -c %(cflags)s %(includes)s ' \
                 '%(sources)s'
        cxx_fmt = '%(cxx)s -o %(target)s -c %(cxxflags)s %(includes)s ' \
                  '%(sources)s'
        fmt = cc_fmt if fname.endswith('.c') else cxx_fmt
        command = fmt % args
        MakeRule.__init__(self, target, prereqs, command)


class LinkRule(MakeRule):
    """
    Generate a rule which links some object files.
    """

    def __init__(self, name, prereqs, objs, args, test=False):
        target = os.path.join(args['output'],
                              'test' if test else 'bin', name)
        args['target'] = target
        args['objs'] = break_str(objs)
        fmt = '%(cxx)s -o %(target)s ' \
              '-Wl,-E %(objs)s %(ldflags)s -Xlinker "-(" %(ldlibs)s ' \
              '-Xlinker "-)"'
        command = fmt % args
        MakeRule.__init__(self, target, prereqs, command)


class SharedRule(MakeRule):
    """
    Generate a rule which links some object files to a Shared Object file.
    """

    def __init__(self, name, prereqs, objs, args):
        target = os.path.join(args['output'], 'lib', name)
        args['target'] = self._target
        args['objs'] = break_str(objs)
        fmt = '%(cxx)s -o %(target)s shared -fPIC' \
              '%(objs)s %(ldflags)s -Xlinker "-(" %(ldlibs)s -Xlinker "-)"'
        command = fmt % args
        MakeRule.__init__(self, target, prereqs, command)


class StaticRule(MakeRule):
    """
    Generate a rule which archive some object files to an archived file.
    """

    def __init__(self, name, prereqs, objs, args):
        target = os.path.join(args['output'], 'lib', name)
        args['target'] = target
        args['objs'] = break_str(objs)
        command = 'ar rcs %(target)s %(objs)s' % args
        MakeRule.__init__(self, target, prereqs, command)


class CleanRule(MakeRule):
    """
    Generate a rule which cleans all of files generated by makefile.
    """

    def __init__(self, objs):
        target = 'clean'
        command = '-rm -fr ' + break_str(sorted(set(objs)))
        MakeRule.__init__(self, target, (), command)


class Artifact:
    """
    An abstract class which produces a snippet of makefile. In which
    a snippet can makes a executable file(.out) ora shared object(.so)
    or a archived file(.a).
    """

    def __init__(self, name, args, sources):
        self._name = name
        self._args = args
        self._sources = sources
        self._objs = []
        self._rule = None
        self._sub_rules = []

    def name(self):
        return self._name

    def sources(self):
        return self._sources

    def build(self, modules):
        includes = self._args.get('includes', ())
        pattern = re.compile(r'^#include\s+"([^"]+)"', re.M)

        def expand(headers):
            prereq_paths = []
            for header in headers:
                for include in includes:
                    path = os.path.join(include, header)
                    if os.path.exists(path):
                        prereq_paths.append(path)
                        break
            return prereq_paths

        def search(source):
            prereq_paths = []
            seen = set()
            queue = [source]
            while queue:
                first = queue.pop(0)
                prereq_paths.append(first)
                with open(first) as f:
                    headers = pattern.findall(f.read())
                    hs = filter(lambda x: x not in seen, headers)
                    seen.update(headers)
                    queue += expand(hs)
            return prereq_paths

        prereq_table = {}
        fmt = '[%%%dd/%%d] analyzing %%s' % len(str(len(self._sources)))
        for i, source in enumerate(self._sources):
            say(fmt, i + 1, len(self._sources), source)
            prereqs = search(source)
            rule = CompileRule(source, prereqs, self._args, self._name)
            self._objs.append(rule.target())
            self._sub_rules.append(rule)

    def obj_rules(self):
        return self._sub_rules

    def rule(self):
        return self._rule


class Binary(Artifact):
    """
    Binary file.
    """

    def build(self, modules):
        Artifact.build(self, modules)
        self._rule = LinkRule(self._name, self._objs + modules,
                              self._objs, self._args)


class Test(Artifact):
    """
    Unit Test.
    """

    def build(self, modules):
        Artifact.build(self, modules)
        self._rule = LinkRule(self._name, self._objs + modules,
                              self._objs, self._args, True)


class SharedLibrary(Artifact):
    """
    Shared Object.
    """

    def build(self, modules):
        Artifact.build(self, modules)
        self._rule = SharedRule(self._name, self._objs + modules,
                                self._objs, self._args)


class StaticLibrary(Artifact):
    """
    Static Libary
    """

    def build(self, modules):
        Artifact.build(self, modules)
        self._rule = StaticRule(self._name, self._objs + modules,
                                self._objs, self._args)


def globs(args):
    sources = []
    for path in args:
        if path.startswith('~/'):
            path = os.path.expanduser(path)
        sources += glob.glob(path)
    return sources


class Module:
    """
    Module represents a builder which builds a Makefile file.
    """

    def __init__(self, workspace, build_path='.biu', output_path='output'):
        self._name = os.path.basename(workspace)
        self._vars = self._adjust({
            'cflags': [],
            'cxxflags': [],
            'ldflags': [],
            'ldlibs': [],
            'includes': [],
            'output': os.path.join(output_path, self._name, ''),
            'cc': 'gcc',
            'cxx': 'g++',
        })
        self._protoc = 'protoc'
        self._storage = Storage(build_path)
        self._protos = set()
        self._artifacts = []
        self._sub_modules = []
        self._phonies = ['all', 'clean']
        self._output_path = output_path

    def set_cc(self, name_or_path):
        self._vars['cc'] = name_or_path

    def set_cxx(self, name_or_path):
        self._vars['cxx'] = name_or_path

    def add_cflags(self, flags):
        self._vars['cflags'].append(flags)

    def add_cxxflags(self, flags):
        self._vars['cxxflags'].append(flags)

    def add_ldflags(self, flags):
        self._vars['ldflags'].append(flags)

    def add_ldlibs(self, libs):
        self._vars['ldlibs'].append(libs)

    def add_sub_module(self, workspace, libs):
        workspace = os.path.abspath(workspace)
        name = os.path.basename(workspace.rstrip('/'))
        output = os.path.join(workspace, self._output_path, name, '')
        libs = [os.path.join(output, lib) for lib in libs]
        for lib in libs:
            self.add_ldlibs(lib)
        self._sub_modules.append((name, workspace, libs))
        self._phonies.append(name)

    def sub_modules(self):
        return self._sub_modules

    def output(self):
        return self._vars['output']

    def set_protoc(self, name_or_path):
        self._protoc = name_or_path

    def protoc(self):
        return self._protoc

    def _adjust(self, kwargs):
        if 'includes' in kwargs:
            kwargs['includes'] = Includes(globs(kwargs['includes']))
        if 'ldlibs' in kwargs:
            kwargs['ldlibs'] = LdLibs(kwargs['ldlibs'])
        for flags in ('cflags', 'cxxflags', 'ldflags'):
            if flags in kwargs:
                kwargs[flags] = Flags(kwargs[flags])
        return kwargs

    def _sanitize(self, sources, protos, kwargs):
        pbs = [proto.replace('.proto', '.pb.cc') for proto in protos]
        self._protos.update(protos)
        scope = Scope(self._vars)
        scope.update(self._adjust(kwargs))
        return scope, sources + pbs

    def add_binary(self, name, sources, protos, kwargs):
        scope, srcs = self._sanitize(sources, protos, kwargs)
        app = Binary(name, scope, srcs)
        self._artifacts.append(app)

    def add_test(self, name, sources, protos, kwargs):
        scope, srcs = self._sanitize(sources, protos, kwargs)
        app = Test(name, scope, srcs)
        self._artifacts.append(app)

    def add_shared(self, name, sources, protos, kwargs):
        scope, srcs = self._sanitize(sources, protos, kwargs)
        shared = SharedLibrary(name, scope, srcs)
        self._artifacts.append(shared)

    def add_static(self, name, sources, protos, kwargs):
        scope, srcs = self._sanitize(sources, protos, kwargs)
        static = StaticLibrary(name, scope, srcs)
        self._artifacts.append(static)

    def _save(self):
        storage = self._storage
        for artifact in self._artifacts:
            for obj_rule in artifact.obj_rules():
                storage.set(obj_rule.target(), obj_rule.prereqs(),
                            obj_rule.command(), True)
            rule = artifact.rule()
            storage.set(rule.target(), rule.prereqs(), rule.command(), False)
        storage.save()

    def _build(self, protos):
        proto_dirs = set([os.path.dirname(path) for path in protos])
        proto_paths = ' '.join(
            ['--proto_path ' + proto_dir for proto_dir in proto_dirs])
        for proto in protos:
            command = '%s %s --cpp_out=%s %s' % (self.protoc(), proto_paths,
                                                 os.path.dirname(proto), proto)
            say(command, color='green')
            status, text = commands.getstatusoutput(command)
            if status:
                raise BuildError(text)

    def build(self, makefile):
        if self._protos:
            self._build(self._protos)
        modules = [module for module, _, _ in self._sub_modules]
        for artifact in self._artifacts:
            say('artifact: %s', artifact.name())
            artifact.build(modules)

        self._write(makefile)
        self._save()

    def _write(self, makefile):
        dircs = set()
        art_rules = []
        obj_rules = []

        for artifact in self._artifacts:
            for obj_rule in artifact.obj_rules():
                obj_rules.append(obj_rule)
                dircs.add(os.path.dirname(obj_rule.target()))
            rule = artifact.rule()
            art_rules.append(rule)
            dircs.add(os.path.dirname(rule.target()))

        rules = []
        rules.append(MakeRule('.PHONY', self._phonies))
        rules.append('')
        rules.append(MakeRule('all',
                              [product.target() for product in art_rules]))
        rules.append('')
        rules.append('')
        rules.extend(art_rules)
        rules.append('')
        rules.extend(obj_rules)
        rules.append('')

        for name, workspace, _ in self._sub_modules:
            rules.append(MakeRule(name, (), 'make -C ' + workspace))
        rules.append(CleanRule([rule.target() for rule in obj_rules]))

        notice = '\n'.join((
            '# file : Makefile',
            '# brief: this file was generated by `biu`',
            '# date : %s' % time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        ))

        with open(makefile, 'w') as out:
            out.write(notice)
            out.write('\n')
            out.write('\n')
            for rule in rules:
                out.write(str(rule))
                out.write('\n')

        for dirc in sorted(dircs):
            if not os.path.exists(dirc):
                os.makedirs(dirc)
        for name, workspace, _ in self._sub_modules:
            output = os.path.join(self._output_path, name)
            output = os.path.join(workspace, output)
            linked_output = os.path.join(self._output_path, name)
            if os.path.islink(linked_output):
                os.unlink(linked_output)
            os.symlink(output, os.path.join(self._output_path, name))

    def artifacts(self):
        return self._artifacts

    def phonies(self):
        return self._phonies


def api(module):
    """
    Api offers some functions which can be invoked by BUILD.
    """

    def CC(arg):
        module.set_cc(arg)

    def CXX(arg):
        module.set_cxx(arg)

    def CFLAGS(arg):
        module.add_cflags(arg)

    def CXXFLAGS(arg):
        module.add_cxxflags(arg)

    def LDFLAGS(arg):
        module.add_ldflags(arg)

    def LDLIBS(arg):
        module.add_ldlibs(arg)

    def PROTOC(arg):
        module.set_protoc(arg)

    def BINARY(name, sources, protos=(), **kwargs):
        module.add_binary(name, globs(sources), globs(protos), kwargs)

    def TEST(name, sources, protos=(), **kwargs):
        module.add_test(name, globs(sources), globs(protos), kwargs)

    def LIBRARY(name, sources, protos=(), **kwargs):
        if name.endswith('.a'):
            module.add_static(name, globs(sources), globs(protos), kwargs)
        elif name.endswith('.so'):
            module.add_shared(name, globs(sources), globs(protos), kwargs)
        else:
            raise BuildError('Unrecognized: ' + name)

    def SUBMODULE(workspace, libs):
        module.add_sub_module(workspace, libs)

    return locals()


class Template:
    """
    Build Template which generates a BUILD file.
    """

    def __init__(self):
        self._cc = 'gcc'
        self._cxx = 'g++'
        self._protoc = 'protoc'
        self._cflags = ['-g -pipe -Wall -std=c99']
        self._cxxflags = ['-g -pipe -Wall -std=c++11']
        self._ldflags = ['-L.']
        self._ldlibs = ['-lpthread']
        self._protos = ['proto/*.proto']
        self._sources = ['src/*.cc', 'src/*.cpp']
        self._includes = ['src/']
        self._app = 'app'

    def cc(self, cc):
        return "CC('%s')" % (cc or self._cc)

    def cxx(self, cxx):
        return "CXX('%s')" % (cxx or self._cxx)

    def protoc(self, protoc):
        return "# PROTOC('%s')" % (protoc or self._protoc)

    def cflags(self, cflags):
        flags = cflags.split(',') if cflags else self._cflags
        return "CFLAGS(%s)" % ', '.join([repr(flag) for flag in flags])

    def cxxflags(self, cxxflags):
        flags = cxxflags.split(',') if cxxflags else self._cxxflags
        return "CXXFLAGS(%s)" % ', '.join([repr(flag) for flag in flags])

    def ldflags(self, ldflags):
        flags = ldflags.split(',') if ldflags else self._ldflags
        return "LDFLAGS(%s)" % ', '.join([repr(flag) for flag in flags])

    def ldlibs(self, ldlibs):
        libs = ldlibs.split(',') if ldlibs else self._ldlibs
        return "LDLIBS(%s)" % ', '.join([repr(lib) for lib in libs])

    def includes(self, includes):
        incs = includes.split(',') if includes else self._includes
        return "INCLUDES(%s)" % ', '.join([repr(inc) for inc in incs])

    def binary(self, app, includes, sources):
        incs = includes.split(',') if includes else self._includes
        include = ', '.join([repr(inc) for inc in incs])
        srcs = sources.split(',') if sources else self._sources
        source = ', '.join([repr(src) for src in srcs])
        args = (app or self._app, include, source)
        return "BINARY('%s', includes=[%s], sources=[%s])" % args

    def format(self, kwargs):
        lines = []
        lines.append(self.cc(kwargs.get('cc')))
        lines.append(self.cxx(kwargs.get('cxx')))
        lines.append(self.protoc(kwargs.get('protoc')))
        lines.append(self.cflags(kwargs.get('cflags')))
        lines.append(self.cxxflags(kwargs.get('cxxflags')))
        lines.append(self.ldflags(kwargs.get('ldflags')))
        lines.append(self.ldlibs(kwargs.get('ldlibs')))
        lines.append(self.binary(kwargs.get('binary'),
                                 kwargs.get('includes'),
                                 kwargs.get('sources')))
        return '\n\n'.join(lines)


class BiuBiu:
    """
    Collect all of rules and generate a makefile file.
    """

    def __init__(self):
        self._build_path = '.biu'
        self._output_path = 'output'
        self._modules_path = os.path.join(self._build_path, 'modules')

    def _write_modules(self, workspaces):
        with open(self._modules_path, 'w') as f:
            for workspace in workspaces:
                f.write(workspace)
                f.write('\n')

    def build(self):
        pwd = os.getcwd()
        workspace = pwd
        name = os.path.basename(workspace)
        say('=' * 40 + ' build ' + name + ' ' + '=' * 40)

        major = Module(workspace, self._build_path, self._output_path)
        execfile(os.path.join(workspace, 'BUILD'), api(major))
        major.build('Makefile')

        module_paths = [pwd]
        for name, workspace, _ in major.sub_modules():
            say('=' * 40 + ' build ' + name + ' ' + '=' * 40)
            os.chdir(workspace)
            module = Module(workspace, self._build_path, self._output_path)
            execfile(os.path.join(workspace, 'BUILD'), api(module))
            module.build('Makefile')
            os.chdir(pwd)
            module_paths.append(workspace)

        self._write_modules(module_paths)

        say('-' * 50)
        say('build makefile : Makefile')
        say('build output   : %s', os.path.join(major.output(), ''))
        say('build date     : %s', time.strftime('%Y-%m-%d %H:%M:%S ',
                                                 time.localtime()))

        say('\nplease execute `make` command to make this project.',
            color='yellow')

    def clean(self):
        modules = [os.getcwd()]
        if os.path.exists(self._modules_path):
            with open(self._modules_path) as f:
                modules = [line.strip() for line in f.readlines()]
        for workspace in modules:
            makefile_path = os.path.join(workspace, 'Makefile')
            build_path = os.path.join(workspace, self._build_path)
            output_path = os.path.join(workspace, self._output_path)
            if os.path.exists(makefile_path):
                os.remove(makefile_path)
            shutil.rmtree(build_path, True)
            shutil.rmtree(output_path, True)

    def create(self, kwargs):
        tpl = Template()
        content = tpl.format(kwargs)
        with open('BUILD', 'w') as f:
            f.write(content)


def do_args(args):
    create_parser = OptionsParser()
    create_parser.add_option('--name', help='Binary name')
    create_parser.add_option('--sources', help='Directory of source codes')

    parser = ArgumentParser(version=__version__)
    parser.add_command('create', 'Create BUILD file', create_parser)
    parser.add_command('build', 'Build project and create a makefile', None)
    parser.add_command('clean', 'Clean this project', None)
    command, options = parser.parse(args)
    return command, options


def main(args):
    command, options = do_args(args)
    biu = BiuBiu()
    try:
        if command == 'create':
            biu.create(options)
        elif command == 'build':
            say(LOGO)
            biu.build()
        elif command == 'clean':
            biu.clean()
    except Exception as e:
        say(e, color="red")
        raise


if __name__ == '__main__':
    main(sys.argv[1:])
