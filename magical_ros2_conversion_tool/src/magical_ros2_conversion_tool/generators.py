from ros_introspection.cmake import Command, CMake, CommandGroup, SectionStyle
import os.path

BUILTIN_INTERFACES = {
  'duration': 'builtin_interfaces/Duration',
  'time': 'builtin_interfaces/Time'
}

def fix_generator_definition(gen):
    for section in gen.sections:
        for field in section.fields:
            if field.type in BUILTIN_INTERFACES:
                field.type = BUILTIN_INTERFACES[field.type]
                gen.changed = True
            elif field.type == 'Header':
                field.type = 'std_msgs/Header'
                gen.changed = True

def fix_generators(package):
    for gen in package.get_all_generators():
        fix_generator_definition(gen)

    # Update Dependencies
    package.manifest.insert_new_packages('buildtool_depend', ['rosidl_default_generators'])
    package.manifest.insert_new_packages('exec_depend', ['rosidl_default_runtime'])
    if package.manifest.format < 3:
        package.manifest._format = 3
        package.manifest.root.setAttribute('format', '3')
        package.manifest.insert_new_packages('member_of_group', ['rosidl_interface_packages'])

    # Enabling C++11
    initial_cmd = Command('if')
    initial_cmd.add_section('NOT')
    initial_cmd.add_section('WIN32')

    not32_contents = CMake(initial_contents=['\n'], depth=package.cmake.depth + 1)

    add_defs = Command('add_definitions')
    add_defs.add_section('', ['-std=c++11'])
    not32_contents.add_command(add_defs)

    cg = CommandGroup(initial_cmd, not32_contents, Command('endif'))
    package.cmake.add_command(cg)

    # Other msg operations
    fp = Command('find_package')
    fp.add_section('', ['rosidl_default_generators'])
    fp.add_section('REQUIRED')
    package.cmake.add_command(fp)

    my_style = SectionStyle('\n    ', '\n        ', '\n        ')
    idl = Command('rosidl_generate_interfaces')
    idl.add_section('', ['${PROJECT_NAME}'] +
                        [os.path.join(gen.type, gen.name) for gen in package.get_all_generators()],
                    my_style)
    idl.add_section('DEPENDENCIES', package.get_dependencies_from_msgs(), my_style)
    package.cmake.add_command(idl)

    for old_cmd_name in ['add_message_files', 'add_service_files', 'generate_messages']:
        for cmd in package.cmake.content_map[old_cmd_name]:
            package.cmake.remove_command(cmd)