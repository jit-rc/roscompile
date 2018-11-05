from ros_introspection.cmake import Command
from roscompile.cmake import enforce_cmake_ordering, remove_empty_cmake_lines
from roscompile.installs import get_multiword_section
from .util import REPLACE_PACKAGES


CATKIN_CMAKE_VARS = {
   '${CATKIN_GLOBAL_BIN_DESTINATION}': 'bin',
   '${CATKIN_GLOBAL_INCLUDE_DESTINATION}': 'include',
   '${CATKIN_GLOBAL_LIB_DESTINATION}': 'lib',
   '${CATKIN_GLOBAL_LIBEXEC_DESTINATION}': 'lib',
   '${CATKIN_GLOBAL_SHARE_DESTINATION}': 'share',
   '${CATKIN_PACKAGE_BIN_DESTINATION}': 'bin',
   '${CATKIN_PACKAGE_INCLUDE_DESTINATION}': 'include/${PROJECT_NAME}',
   '${CATKIN_PACKAGE_LIB_DESTINATION}': 'lib',
   '${CATKIN_PACKAGE_SHARE_DESTINATION}': 'share/${PROJECT_NAME}',
}


def rename_commands(cmake, source_name, target_name, remove_sections=[]):
    for cmd in cmake.content_map[source_name]:
        cmd.command_name = target_name
        cmd.changed = True
        for name in remove_sections:
            cmd.remove_sections(name)
    cmake.content_map[target_name] = cmake.content_map[source_name]
    del cmake.content_map[source_name]


def set_up_include_exports(package):
    cat_var = '${catkin_INCLUDE_DIRS}'
    dirs = ['${%s_INCLUDE_DIRS}' % s for  s in package.source_code.get_build_dependencies()]
    for cmd in package.cmake.content_map['include_directories']:
        section = cmd.sections[0]
        if cat_var in section.values:
            section.values.remove(cat_var)
            section.values += dirs
            cmd.changed = True

def set_up_catkin_libs(package):
    deps = ['"{}"'.format(s) for s in package.source_code.get_build_dependencies()]

    cat_var = '${catkin_LIBRARIES}'
    rename_commands(package.cmake, 'target_link_libraries', 'ament_target_dependencies')
    for cmd in package.cmake.content_map['ament_target_dependencies']:
        for section in cmd.get_real_sections():
            if cat_var in section.values:
                section.values.remove(cat_var)
                section.values += deps
                cmd.changed = True

def convert_cmake(package):
    # Upgrade minimum version
    for cmd in package.cmake.content_map['cmake_minimum_required']:
        section = cmd.get_section('VERSION')
        version_str = section.values[0]
        version = map(int, version_str.split('.'))
        if version[0] < 3:
            section.values = ['3.5']
            cmd.changed = True

    # convert find_package commands to find one package at a time
    for cmd in package.cmake.content_map['find_package']:
        tokens = cmd.get_tokens()
        if len(tokens) == 0 or tokens[0] != 'catkin':
            continue
        components = ['ament_cmake']
        if cmd.get_section('REQUIRED'):
            cmps = cmd.get_section('COMPONENTS')
            if cmps:
                components += cmps.values
        package.cmake.remove_command(cmd)
        for component in components:
            if component == 'message_generation':
                continue
            if component in REPLACE_PACKAGES:
                component = REPLACE_PACKAGES[component]
            cmd = Command('find_package')
            cmd.add_section('', [component])
            cmd.add_section('REQUIRED')
            package.cmake.add_command(cmd)

    # Change Variables in installation directories
    for cmd in package.cmake.content_map['install']:
        for section in cmd.get_sections('DESTINATION'):
            for i, value in enumerate(section.values):
                if value in CATKIN_CMAKE_VARS:
                    section.values[i] = CATKIN_CMAKE_VARS[value]
                    cmd.changed = True

    # Remove Cpp11 flag
    to_remove = []
    for cmd in package.cmake.content_map['set_directory_properties']:
        section = cmd.get_section('COMPILE_OPTIONS')
        bits = filter(None, section.values[0][1:-1].split(';'))
        if '-std=c++11' in bits:
            bits.remove('-std=c++11')
        if len(bits) == 0:
            to_remove.append(cmd)
        else:
            section.values = ['"%s"' % ';'.join(bits)]
            cmd.changed = True
    for cmd in to_remove:
        package.cmake.remove_command(cmd)

    pkg_cmd = package.cmake.content_map['catkin_package'][0]
    for sname, cmd_name in [('CATKIN_DEPENDS', 'ament_export_dependencies'),
                            ('INCLUDE_DIRS', 'ament_export_include_directories'),
                            ('LIBRARIES', 'ament_export_libraries')]:
        section = pkg_cmd.get_section(sname)
        if not section:
            continue
        cmd = Command(cmd_name)
        cmd.add_section('', section.values)
        package.cmake.add_command(cmd)

    cmd = Command('ament_package')
    package.cmake.add_command(cmd)

    # Set up include exports
    set_up_include_exports(package)
    set_up_catkin_libs(package)

    # Remove deprecated Commands
    for old_cmd_name in ['catkin_python_setup', 'add_dependencies', 'catkin_package']:
        package.cmake.remove_all_commands(old_cmd_name)
    enforce_cmake_ordering(package)
    remove_empty_cmake_lines(package)
