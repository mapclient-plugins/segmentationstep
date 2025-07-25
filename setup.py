"""
MAP Client, a program to generate detailed musculoskeletal models for OpenSim.
    Copyright (C) 2012  University of Auckland
    
This file is part of MAP Client. (http://launchpad.net/mapclient)

    MAP Client is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    MAP Client is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with MAP Client.  If not, see <http://www.gnu.org/licenses/>..
"""

from setuptools import setup, find_packages
import io


def readfile(filename, split=False):
    with io.open(filename, encoding="utf-8") as stream:
        if split:
            return stream.read().split("\n")
        return stream.read()


# This reads the plugin version from __init__.py.
file = open('mapclientplugins/segmentationstep/__init__.py', 'r')
lines = file.readlines()
for line in lines:
    if line.startswith('__version__'):
        delim = '"' if '"' in line else "'"
        version = line.split(delim)[1]
    elif line.startswith('__author__'):
        delim = '"' if '"' in line else "'"
        author = line.split(delim)[1]

package_readme = readfile("README.md", split=True)[3:]  # skip title
package_license = readfile("LICENSE")
package_dependencies = [
    "setuptools",
    "PySide6",
    "numpy",
    "cmlibs.zinc"
]

setup(name=u'mapclientplugins.segmentationstep',
      version=version,
      description='',
      long_description='\n'.join(package_readme) + package_license,
      classifiers=[
          "Development Status :: 3 - Alpha",
          "License :: OSI Approved :: Apache Software License",
          "Programming Language :: Python",
      ],
      author=author,
      author_email='',
      url='https://github.com/mapclient-plugins/segmentationstep',
      license='APACHE',
      packages=find_packages(exclude=['ez_setup', ]),
      include_package_data=True,
      zip_safe=False,
      install_requires=package_dependencies,
      )
