#!/usr/local/bin/managed_python3
'''Processes python modules in the facts directory and adds the info they
return to our ConditionalItems.plist'''

from __future__ import absolute_import, print_function

import importlib
import json
import os
import plistlib
import subprocess
import sys
from xml.parsers.expat import ExpatError

# pylint: disable=no-name-in-module
from CoreFoundation import CFPreferencesCopyAppValue
# pylint: enable=no-name-in-module


def main():
    # pylint: disable=too-many-locals
    '''Run all our fact plugins and collect their data'''
    module_dir = os.path.join(os.path.dirname(__file__), 'facts')
    facts = {}

    # Check if running under WS1
    if 'AirWatch/Data' in module_dir:
        ws1 = True
        # Get sensor values from hubcli
        try:
            proc = subprocess.Popen(['/usr/local/bin/hubcli', 'sensors', '--list', '--json'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text="UTF-8")
            values, _ = proc.communicate()
        except (IOError, OSError):
            values = None

        if values:
            for sensor in json.loads(values):
                try:
                    value = json.loads(sensor['resultValue'].replace("'", '"'))
                except ValueError:
                    value = sensor['resultValue']
                facts.update({sensor['name']: value})

    # find all the .py files in the 'facts' dir
    fact_files = [
        os.path.splitext(name)[0]
        for name in os.listdir(module_dir)
        if name.endswith('.py') and not name == '__init__.py']

    for name in fact_files:
        # load each file and call its fact() function
        file_path = os.path.join(module_dir, name + '.py')
        try:
            # Python 3.4 and higher only
            spec = importlib.util.spec_from_file_location(name, file_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            facts.update(module.fact())
        # pylint: disable=broad-except
        except BaseException as err:
            print(u'Error %s in file %s' % (err, file_path), file=sys.stderr)
        # pylint: enable=broad-except

    if facts:
        # Handle cases when facts return None - convert them to empty
        # strings.
        for key, value in facts.items():
            if value is None:
                facts[key] = ''

        # If running under ws1, set managedinstalldir
        if ws1:
            managedinstalldir = '/Library/Application Support/AirWatch/Data/Munki/Managed Installs'
        else:
            # Read the location of the ManagedInstallDir from ManagedInstall.plist
            bundle_id = 'ManagedInstalls'
            pref_name = 'ManagedInstallDir'
            managedinstalldir = CFPreferencesCopyAppValue(pref_name, bundle_id)
        conditionalitemspath = os.path.join(
                managedinstalldir, 'ConditionalItems.plist')

        conditional_items = {}
        # read the current conditional items
        if os.path.exists(conditionalitemspath):
            try:
                with open(conditionalitemspath, "rb") as file:
                    conditional_items = plistlib.load(file)
            except (IOError, OSError, ExpatError) as err:
                pass

        # update the conditional items
        conditional_items.update(facts)

        # and write them out
        try:
            with open(conditionalitemspath, "wb") as file:
                plistlib.dump(conditional_items, file)
        except (IOError, OSError) as err:
            print('Couldn\'t save conditional items: %s' % err, file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
