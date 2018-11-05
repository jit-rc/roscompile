from ros_introspection.source_code_file import CPLUS2
from ros_introspection.resource_list import PACKAGES, MESSAGES, SERVICES
from .util import convert_to_underscore_notation, convert_to_caps_notation
import re

ROS2_INCLUDE_PATTERN = '#include <%s/%s/%s.hpp>'

LOGGERS = {
    'ROS_DEBUG': 'RCLCPP_DEBUG',
    'ROS_INFO': 'RCLCPP_INFO',
    'ROS_ERROR': 'RCLCPP_ERROR',
    'ROS_WARN': 'RCLCPP_WARN'
}

def make_include_pattern(s):
    return '#include\s*[<\\"]' + s + '[>\\"]'


CPP_CODE_REPLACEMENTS = {
    make_include_pattern('ros/ros.h'): '#include "rclcpp/rclcpp.hpp"',
    'ros::Time': 'rclcpp::Time',
    'ros::Rate': 'rclcpp::Rate',
    'ros::Duration': 'rclcpp::Duration',
    'ros::ok\(\)': 'rclcpp::ok()',
    '( *)ros::init\(argc, argv, "([^"]*)"\);':
        '$0rclcpp::init(argc, argv);\n$0auto node = rclcpp::Node::make_shared("$1");',
    'ros::spinOnce\(\);': 'rclcpp::spin_some(node);',
    'ros::spin\(\);': 'rclcpp::spin(node);',
    'ros::NodeHandle': 'rclcpp::Node',
    'ros::Publisher (.*) = (.*)advertise(.*);': 'auto $0 = $1advertise$2;',

    # boost stuff
    make_include_pattern('boost/shared_ptr.hpp'): '#include <memory>',
    'boost::shared_ptr': 'std::shared_ptr',
    make_include_pattern('boost/thread/mutex.hpp'): '#include <mutex>',
    'boost::mutex': 'std::mutex',
    'boost::mutex::scoped_lock': 'std::unique_lock<std::mutex>',
    make_include_pattern('boost/unordered_map.hpp'): '#include <unordered_map>',
    'boost::unordered_map': 'std::unordered_map',
    make_include_pattern('boost/function.hpp'): '#include <functional>',
    'boost::function': 'std::function',

    # tf stuff
    make_include_pattern('tf/transform_listener.h'):
        '#include "tf2_ros/buffer.h"\n#include "tf2_ros/transform_listener.h"',
    'tf::TransformListener': 'tf2_ros::TransformListener',
    'tf::Stamped': 'tf2::Stamped',
    'tf::Pose': 'tf2::Pose',
    'tf::get': 'tf2::get',
}

def replace_source_code(package, patterns, language='c++'):
    for source in package.source_code.get_source_by_language(language):
        s = source.get_contents()
        changed = False
        for needle, replacement in patterns.iteritems():
            pattern = re.compile(needle)
            m = pattern.search(s)
            while m:
                this_replacement = replacement
                if len(m.groups()) > 0:
                    for i, chunk in enumerate(m.groups()):
                        key = '$%d' % i
                        this_replacement = this_replacement.replace(key, chunk)
                before, middle, after = s.partition(m.group(0))
                print 'In %s, replacing %s with %s' % (source.rel_fn, middle, this_replacement)
                s = before + this_replacement + after

                changed = True
                m = pattern.search(s)
            if changed:
                source.replace_contents(s)

def get_full_msg_dependencies_from_source(package):
    messages = set()
    for gen_type, full_list in [('msg', MESSAGES), ('srv', SERVICES)]:
        for pkg, gen_name in full_list:
            gen_pattern = re.compile(pkg + '.*' + gen_name)
            if package.source_code.search_for_pattern(gen_pattern):
                messages.add((pkg, gen_name, gen_type))
    return messages

def get_generator_based_replacements(package):
    SERVICE_REPLACEMENTS = {}
    GENERATOR_REPLACEMENTS = {}
    for pkg, msg, gen_type in get_full_msg_dependencies_from_source(package):
        key = make_include_pattern('%s/%s.h' % (pkg, msg))
        value = ROS2_INCLUDE_PATTERN % (pkg, gen_type, convert_to_underscore_notation(msg))
        GENERATOR_REPLACEMENTS[key] = value

        two_colons = '%s::%s' % (pkg, msg)
        four_colons = '%s::%s::%s' % (pkg, gen_type, msg)
        GENERATOR_REPLACEMENTS[two_colons] = four_colons

        if gen_type == 'srv':
            key = 'bool ([^\(]+)\(\s*' + two_colons + '::Request\s+&\s+([^,]+),\s+'
            key += two_colons + '::Response\s+&\s+([^\)]+)\)'
            value = 'void $1(const std::shared_ptr<' + four_colons + '::Request> $2, '
            value += 'std::shared_ptr<' + four_colons + '::Response> $3)'
            SERVICE_REPLACEMENTS[key] = value
    return GENERATOR_REPLACEMENTS, SERVICE_REPLACEMENTS

def get_logger_replacements(package):
    LOGGER_REPLACEMENTS = {}
    PackageName = convert_to_caps_notation(package.name)
    for old_logger, new_logger in LOGGERS.items():
        LOGGER_REPLACEMENTS[old_logger + '\('] = new_logger + '(rclcpp::get_logger("' + PackageName + '"), '
        #old_pattern = old_logger + '([_A-Z]*)\('
        LOGGER_REPLACEMENTS[old_logger + '_NAMED\(([^,]+),'] = new_logger + '(rclcpp::get_logger($0),'
    return LOGGER_REPLACEMENTS

def templatize_publishers(package):
    pub_pattern = re.compile('( *)(ros::Publisher )([^);]+);', re.DOTALL)
    all_matches = package.source_code.search_for_pattern(pub_pattern, False)
    for filename, matches in all_matches.iteritems():
        source_file = package.source_code.sources[filename]
        source = source_file.get_contents()
        last_include = source.rindex('#include')
        new_line = source.index('\n', last_include)
        current_includes = source_file.search_lines_for_pattern(CPLUS2)
        new_includes = ''

        for ws, start, match in matches:
            full_str = ws + start + match
            new_str = ''
            s = match.replace('\n', ' ')
            while '  ' in s:
                s = s.replace('  ', ' ')
            for pub in s.split(', '):
                p_pattern = re.compile(pub + '.*advertise<([^>]+)>')
                p_matches = package.source_code.search_for_pattern(p_pattern)
                if len(p_matches) > 0:
                    pub_type = p_matches.values()[0][0][0]
                    parts = pub_type.split('::')
                    if len(parts) == 2:
                        parts = [parts[0], 'msg', parts[1]]
                        pub_type = '%s::msg::%s' % (parts[0], parts[2])

                    new_str += ws + 'rclcpp::Publisher<%s>::SharedPtr %s;\n' % (pub_type, pub)
                    parts[2] = convert_to_underscore_notation(parts[2])
                    search_parts = list(parts)
                    search_parts[2] += '.hpp'
                    if tuple(search_parts) not in current_includes:
                        new_include = ROS2_INCLUDE_PATTERN % tuple(parts)
                        if new_include not in new_includes:
                            new_includes += '\n' + new_include
            source = source.replace(full_str + ';', new_str[:-1])
        if len(new_includes) > 0:
            source = source[:new_line] + new_includes + source[new_line:]
        source_file.replace_contents(source)

    advertise_pattern = re.compile('(advertise<([^>]+)>\(([^,]+),\s+\d+\))', re.DOTALL)
    for filename, matches in package.source_code.search_for_pattern(advertise_pattern, False).iteritems():
        source_file = package.source_code.sources[filename]
        source = source_file.get_contents()
        for match in matches:
            source = source.replace(match[0], 'create_publisher<%s>(%s)' % (match[1], match[2]))
        source_file.replace_contents(source)

def convert_cplusplus(package):
    GENERATOR_REPLACEMENTS, SERVICE_REPLACEMENTS = get_generator_based_replacements(package)
    replace_source_code(package, SERVICE_REPLACEMENTS)
    replace_source_code(package, GENERATOR_REPLACEMENTS)
    replace_source_code(package, get_logger_replacements(package))
    replace_source_code(package, CPP_CODE_REPLACEMENTS)
    templatize_publishers(package)