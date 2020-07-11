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


class ArgError(IOError): pass


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
    newline = kwargs.get('nl', '\n')
    fmt = str(fmt)
    sys.stdout.write(colors[which] + (args and fmt % args or fmt) + '\033[0m')
    sys.stdout.write(newline)
    sys.stdout.flush()


def break_str(prereqs):
    """
    Break a string into multiline text.
    """
    return ' \\\n\t'.join(prereqs)


class Options(dict):
    """
    A parsed options from command line.
    """

    def __init__(self, d=None):
        dict.__init__(self, d)

    def __getattr__(self, name):
        try:
            return self._args[name]
        except KeyError:
            return None


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

    def __init__(self, name, version=None):
        self._commands = []
        self._command_map = {}
        self._name = name
        self._version = version

        self.add_command('version', 'Show version')
        self.add_command('help', 'Show help')

    def usage(self, command='<command>'):
        return 'Usage:\n  %s %s [options]\n\n' % (self._name, command)

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
            self.print_help(self.usage(argv[0]) + parser.help(argv[0]), e)

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
    A extended dict.
    """

    def __init__(self, d):
        dict.__init__(self, d)

    def extend(self, subscope):
        for key, val in subscope.iteritems():
            refval = self.get(key)
            if refval:
                refval += val
            else:
                self[key] = val


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
    Load and store a shelve db, also compare with current cache.
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
        delete = lambda x: os.path.exists(x) and os.remove(x)
        for target, (prereqs, command, _) in self._cache.iteritems():
            old_prereqs, old_command, _ = self._db.get(target, [None] * 3)
            if prereqs != old_prereqs or command != old_command:
                delete(target)
        expired_keys = set(self._db.keys()) - set(self._cache.keys())
        for key in expired_keys:
            delete(key)
        for target, (prereqs, _, is_obj) in self._db.iteritems():
            if is_obj: continue
            if set(prereqs) & expired_keys:
                delete(target)


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
            # Merges multiple consecutive Spaces
            command = ' '.join(filter(None, self._command.split(' ')))
            s += '\n\t%s' % command
        return s


class CompileRule(MakeRule):
    """
    Generate a rule which compiles source file to object file.
    """

    def __init__(self, fname, prereqs, args, artifact):
        target = os.path.join(args['output'], 'objs', artifact, fname + '.o')
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
        fmt = '%(cxx)s -o %(target)s %(objs)s %(ldflags)s ' \
              '-Xlinker "-(" %(ldlibs)s -Xlinker "-)"'
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
    Generate a rule which cleans all of targets generated by makefile.
    """

    def __init__(self, targets):
        target = 'clean'
        command = '-rm -fr ' + break_str(sorted(set(targets)))
        MakeRule.__init__(self, target, (), command)


class Artifact:
    """
    An abstract class which produces a snippet of makefile. In which
    a snippet can makes a executable file(.out) or a shared object(.so)
    or a archived file(.a).
    """

    def __init__(self, name, args, sources, sub_modules):
        self._name = name
        self._args = args
        self._sources = sources
        self._sub_modules = sub_modules
        self._objs = []
        self._rule = None
        self._sub_rules = []

    def name(self):
        return self._name

    def rule(self):
        return self._rule

    def obj_rules(self):
        return self._sub_rules

    def build(self):
        pattern = re.compile(r'^#include\s+"([^"]+)"', re.M)

        def expand(headers, includes):
            prereq_paths = []
            for header in headers:
                paths = [os.path.join(include, header) for include in includes]
                for path in paths:
                    if os.path.exists(path):
                        prereq_paths.append(path)
                        break
            return prereq_paths

        def search(source):
            prereq_paths = []
            # Create a dummy of original `includes` to append.
            includes = list(self._args.get('includes', []))
            seen = set()
            queue = [source]
            parent = os.path.dirname(source)
            if parent:
                includes.append(parent)
            while queue:
                first = queue.pop(0)
                prereq_paths.append(first)
                with open(first) as f:
                    headers = pattern.findall(f.read())
                    new_headers = filter(lambda x: x not in seen, headers)
                    queue += expand(new_headers, includes)
                    seen.update(new_headers)
            return prereq_paths

        fmt = '[%%%dd/%%d] analyze %%s' % len(str(len(self._sources)))
        for i, source in enumerate(self._sources):
            say(fmt, i + 1, len(self._sources), source)
            prereqs = search(source)
            rule = CompileRule(source, prereqs, self._args, self._name)
            self._objs.append(rule.target())
            self._sub_rules.append(rule)


class Binary(Artifact):
    """
    Binary file.
    """

    def build(self):
        Artifact.build(self)
        self._rule = LinkRule(self._name, self._objs + self._sub_modules,
                              self._objs, self._args)


class Test(Artifact):
    """
    Unit Test.
    """

    def build(self):
        Artifact.build(self)
        self._rule = LinkRule(self._name, self._objs + self._sub_modules,
                              self._objs, self._args, True)


class SharedLibrary(Artifact):
    """
    Shared Object.
    """

    def build(self):
        Artifact.build(self)
        self._rule = SharedRule(self._name, self._objs + self._sub_modules,
                                self._objs, self._args)


class StaticLibrary(Artifact):
    """
    Static Libary
    """

    def build(self):
        Artifact.build(self)
        self._rule = StaticRule(self._name, self._objs + self._sub_modules,
                                self._objs, self._args)


def to_list(args):
    """
    Convert the following types to list:
    1. 'a b c' -> ['a', 'b', 'c']
    2. list/set/tuple/dict -> list
    """
    return args.split(' ') if isinstance(args, str) else list(args)


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
        self._proto_srcs = []
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
        libs = [os.path.join(output, lib) for lib in to_list(libs)]
        for lib in libs:
            self.add_ldlibs(lib)
        self._sub_modules.append((name, workspace, libs))
        self._phonies.append(name)

    def sub_modules(self):
        return self._sub_modules

    def name(self):
        return self._name

    def set_protoc(self, name_or_path):
        self._protoc = name_or_path

    def proto_srcs(self):
        return self._proto_srcs

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
        sources = globs(to_list(sources))
        protos = globs(to_list(protos))
        kwargs = {key: to_list(val) for key, val in kwargs.iteritems() if val}
        pbs = [proto.replace('.proto', '.pb.cc') for proto in protos]
        self._protos.update(protos)
        scope = Scope(self._vars)
        scope.extend(self._adjust(kwargs))
        return scope, sources + pbs

    def _add_artifact(self, cls, name, sources, protos, kwargs):
        scope, srcs = self._sanitize(sources, protos, kwargs)
        sub_modules = [module for module, _, _ in self._sub_modules]
        artifact = cls(name, scope, srcs, sub_modules)
        self._artifacts.append(artifact)

    def add_binary(self, name, sources, protos, kwargs):
        self._add_artifact(Binary, name, sources, protos, kwargs)

    def add_test(self, name, sources, protos, kwargs):
        self._add_artifact(Binary, name, sources, protos, kwargs)

    def add_shared(self, name, sources, protos, kwargs):
        self._add_artifact(SharedLibrary, name, sources, protos, kwargs)

    def add_static(self, name, sources, protos, kwargs):
        self._add_artifact(StaticLibrary, name, sources, protos, kwargs)

    def artifacts(self):
        return self._artifacts

    def phonies(self):
        return self._phonies

    def _save(self):
        storage = self._storage
        for artifact in self._artifacts:
            for obj_rule in artifact.obj_rules():
                storage.set(obj_rule.target(), obj_rule.prereqs(),
                            obj_rule.command(), True)
            rule = artifact.rule()
            storage.set(rule.target(), rule.prereqs(), rule.command(), False)
        storage.save()

    def build(self, makefile):
        for proto in self._protos:
            pbname, _ = os.path.splitext(proto)
            pbh, pbcc = pbname + '.pb.h', pbname + '.pb.cc'
            self._proto_srcs += (pbh, pbcc)
            if os.path.exists(pbh) and os.path.exists(pbcc):
                pbh_mtime = os.path.getmtime(pbh)
                pbcc_mtime = os.path.getmtime(pbcc)
                proto_mtime = os.path.getmtime(proto)
                if pbh_mtime > proto_mtime and pbcc_mtime > proto_mtime:
                    continue

            proto_dirs = set([os.path.dirname(path) for path in self._protos])
            proto_paths = ' '.join(
                ['--proto_path ' + proto_dir for proto_dir in proto_dirs])
            command = '%s %s --cpp_out=%s %s' % (self._protoc, proto_paths,
                                                 os.path.dirname(proto), proto)
            say(command, color='green')
            status, text = commands.getstatusoutput(command)
            assert status == 0, text

        for artifact in self._artifacts:
            say('[%s] artifact: %s', self._name, artifact.name())
            artifact.build()
            say('-' * 60)

        self._make(makefile)
        self._save()

    def _make(self, makefile):
        targets = set()
        art_rules = []
        obj_rules = []
        for artifact in self._artifacts:
            for obj_rule in artifact.obj_rules():
                obj_rules.append(obj_rule)
                targets.add(obj_rule.target())
            rule = artifact.rule()
            art_rules.append(rule)
            targets.add(rule.target())

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
            rules.append('')
        rules.append('')
        rules.append(CleanRule(sorted(targets)))

        self._make_env(targets)
        self._write_to(rules, makefile)

    def _make_env(self, targets):
        for dirc in sorted((os.path.dirname(target) for target in targets)):
            if not os.path.exists(dirc):
                os.makedirs(dirc)
        for name, workspace, _ in self._sub_modules:
            output = os.path.join(self._output_path, name)
            output = os.path.join(workspace, output)
            linked_output = os.path.join(self._output_path, name)
            if os.path.islink(linked_output):
                os.unlink(linked_output)
            os.symlink(output, os.path.join(self._output_path, name))

    def _write_to(self, rules, makefile):
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
        module.add_binary(name, sources, protos, kwargs)

    def TEST(name, sources, protos=(), **kwargs):
        module.add_test(name, sources, protos, kwargs)

    def LIBRARY(name, sources, protos=(), **kwargs):
        assert name.endswith('.a') or name.endswith('.so')
        if name.endswith('.a'):
            module.add_static(name, sources, protos, kwargs)
        else:
            module.add_shared(name, sources, protos, kwargs)

    def SUBMODULE(workspace, libs):
        module.add_sub_module(workspace, libs)

    return locals()


class Template:
    """
    Build Template which generates a BUILD file.
    """

    def format(self, kwargs):
        kwargs.setdefault('name', 'app')
        lines = [
            "CC('gcc')",
            "CXX('g++')",
            "# PROTOC('protoc')",
            "CFLAGS('-g -pipe -Wall -std=c99')",
            "CXXFLAGS('-g -pipe -Wall -std=c++11')",
            "LDFLAGS('-L.')",
            "LDLIBS('-lpthread')",
            "BINARY(name='%(name)s', sources=['src/*.cc', 'src/*.cpp'])"
        ]
        return '\n\n'.join(lines) % kwargs


class BiuBiu:
    """
    Collect all of rules and generate a makefile file.
    """

    def __init__(self):
        self._build_path = '.biu'
        self._output_path = 'output'
        self._modules_path = os.path.join(self._build_path, 'modules')
        self._pbsrc_path = os.path.join(self._build_path, 'protos')

    def _write_modules(self, workspaces):
        with open(self._modules_path, 'w') as f:
            for workspace in workspaces:
                f.write(workspace)
                f.write('\n')

    def _write_lines(self, fname, lines):
        with open(fname, 'w') as f:
            for line in lines:
                f.write(line)
                f.write('\n')

    def build(self):
        say('=' * 60)

        pwd = os.getcwd()
        workspace = pwd
        major = Module(workspace, self._build_path, self._output_path)
        execfile(os.path.join(workspace, 'BUILD'), api(major))
        major.build('Makefile')

        module_paths = [pwd]
        pbsrc_paths = list(major.proto_srcs())
        for name, workspace, _ in major.sub_modules():
            os.chdir(workspace)
            module = Module(workspace, self._build_path, self._output_path)
            execfile(os.path.join(workspace, 'BUILD'), api(module))
            module.build('Makefile')
            os.chdir(pwd)
            module_paths.append(workspace)
            pbsrc_paths += module.proto_srcs()

        self._write_lines(self._modules_path, module_paths)
        self._write_lines(self._pbsrc_path, pbsrc_paths)

        say('build makefile : Makefile')
        say('build output   : %s', os.path.join(self._output_path, ''))
        say('build date     : %s', time.strftime('%Y-%m-%d %H:%M:%S ',
                                                 time.localtime()))

        say('\nplease execute `make` command to make this project.',
            color='yellow')

    def clean(self):
        modules = [os.getcwd()]
        if os.path.exists(self._modules_path):
            with open(self._modules_path) as f:
                modules = [line.strip() for line in f.readlines()]
        if os.path.exists(self._pbsrc_path):
            with open(self._pbsrc_path) as f:
                for line in f:
                    fname = line.strip()
                    if os.path.exists(fname):
                        os.remove(fname)
        for workspace in modules:
            makefile_path = os.path.join(workspace, 'Makefile')
            build_path = os.path.join(workspace, self._build_path)
            output_path = os.path.join(workspace, self._output_path)
            if os.path.exists(makefile_path):
                os.remove(makefile_path)
            shutil.rmtree(build_path, True)
            shutil.rmtree(output_path, True)

    def create(self, options):
        tpl = Template()
        content = tpl.format(options)
        with open('BUILD', 'w') as f:
            f.write(content)
        say('the `BUILD` has been generated in the current directory',
            color='yellow')


def do_args(argv):
    name, args = argv[0], argv[1:]

    create_parser = OptionsParser()
    create_parser.add_option('--name',
                             help='Artifact name. eg: app')

    parser = ArgumentParser(name, version=__version__)
    parser.add_command('create', 'Create BUILD file', create_parser)
    parser.add_command('build', 'Build project and generate a makefile', None)
    parser.add_command('clean', 'Clean this project', None)
    command, options = parser.parse(args)
    return command, options


def main(args):
    say(LOGO)
    command, options = do_args(args)
    biu = BiuBiu()
    if command == 'create':
        biu.create(options)
    elif command == 'build':
        biu.build()
    elif command == 'clean':
        biu.clean()


if __name__ == '__main__':
    main(sys.argv)
