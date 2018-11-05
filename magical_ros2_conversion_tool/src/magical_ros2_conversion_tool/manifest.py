from roscompile.manifest import replace_package_set
from .util import REPLACE_PACKAGES

def set_build_type(manifest, build_type):
    export_tags = manifest.root.getElementsByTagName('export')
    if len(export_tags) == 0:
        export_tag = manifest.tree.createElement('export')
        manifest.insert_new_tag(export_tag)
        export_tags = [export_tag]
    ex_el = export_tags[0]
    built_type_tag = manifest.tree.createElement('build_type')
    built_type_tag.appendChild(manifest.tree.createTextNode(build_type))
    manifest.insert_new_tag_inside_another(ex_el, built_type_tag)

    for build_tool in manifest.root.getElementsByTagName('buildtool_depend'):
        name = build_tool.childNodes[0].nodeValue
        if name == 'catkin':
            build_tool.childNodes[0] = manifest.tree.createTextNode(build_type)

def update_manifest(package):
    manifest = package.manifest
    if manifest.format < 2:
        manifest._format = 2
        manifest.root.setAttribute('format', '2')
        replace_package_set(manifest, ['build_depend', 'run_depend'], 'depend')
        replace_package_set(manifest, ['run_depend'], 'exec_depend')
    # Replace some packages
    for old_and_busted, new_hotness in REPLACE_PACKAGES.items():
        if old_and_busted in package.manifest.get_packages():
            package.manifest.remove_dependencies('depend', [old_and_busted])
            if new_hotness not in package.manifest.get_packages():
                package.manifest.insert_new_packages('depend', [new_hotness])
