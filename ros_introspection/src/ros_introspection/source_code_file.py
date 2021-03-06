import re
import os
from ros_introspection.resource_list import is_package, get_python_dependency

PKG = '([^\.;]+)(\.?[^;]*)?'
PYTHON1 = '^import ' + PKG
PYTHON2 = 'from ' + PKG + ' import .*'
CPLUS = re.compile('#include\s*[<\\"]([^/]*)/?([^/]*)[>\\"]')          # Zero or one slash
CPLUS2 = re.compile('#include\s*[<\\"]([^/]*)/([^/]*)/([^/]*)[>\\"]')  # Two slashes
ROSCPP = re.compile('#include\s*<ros/ros.h>')

EXPRESSIONS = [re.compile(PYTHON1), re.compile(PYTHON2), CPLUS, CPLUS2]


def is_python_hashbang_line(s):
    return s[0:2] == '#!' and 'python' in s


class SourceCodeFile:
    def __init__(self, rel_fn, file_path):
        self.rel_fn = rel_fn
        self.file_path = file_path
        self.tags = set()
        self.changed_contents = None

        self.lines = map(str.strip, self.get_contents().split('\n'))
        if '.py' in self.file_path or (len(self.lines) > 0 and is_python_hashbang_line(self.lines[0])):
            self.language = 'python'
        else:
            self.language = 'c++'

        parts = os.path.split(rel_fn)
        if parts and parts[0] == 'test':
            self.tags.add('test')

    def get_contents(self):
        if self.changed_contents:
            return self.changed_contents
        return open(self.file_path).read()

    def replace_contents(self, contents):
        self.changed_contents = contents
        self.lines = map(unicode.strip, unicode(contents).split('\n'))

    def search_for_patterns(self, patterns):
        matches = []
        contents = self.get_contents()
        for pattern in patterns:
            matches += pattern.findall(contents)
        return matches

    def search_lines_for_patterns(self, patterns):
        matches = []
        for line in self.lines:
            for pattern in patterns:
                m = pattern.search(line)
                if m:
                    matches.append(m.groups())
        return matches

    def search_lines_for_pattern(self, pattern):
        return self.search_lines_for_patterns([pattern])

    def get_import_packages(self):
        pkgs = set()
        for match in self.search_lines_for_patterns(EXPRESSIONS):
            pkgs.add(match[0])
        if len(self.search_lines_for_pattern(ROSCPP)) > 0:
            pkgs.add('roscpp')
        return sorted(list(pkgs))

    def get_dependencies(self):
        deps = []
        for pkg in self.get_import_packages():
            if is_package(pkg):
                deps.append(pkg)
        return deps

    def get_external_python_dependencies(self):
        deps = []
        if self.language != 'python':
            return deps

        for pkg in self.get_import_packages():
            p_dep = get_python_dependency(pkg)
            if p_dep:
                deps.append(p_dep)
        return deps

    def is_executable(self):
        return os.access(self.file_path, os.X_OK)

    def __lt__(self, other):
        return self.rel_fn < other.rel_fn

    def __repr__(self):
        attribs = [self.language] + list(self.tags)
        return '%s (%s)' % (self.rel_fn, ', '.join(attribs))

    def write(self):
        if self.changed_contents:
            with open(self.file_path, 'w') as f:
                f.write(self.changed_contents)
