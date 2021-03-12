# We're linking against '../build/bin/libhumon-d.a' which is built by `../build.py`.

from setuptools import setup, find_packages

with open ('README.md', 'r') as f:
      long_desc = f.read()

setup(name="geg",
      version='0.0.1',
      description='gcc error grok. Prettifies and makes interactive the complex errors from gcc/g++ build.',
      long_description = long_desc,
      long_description_content_type = 'text/markdown',
      author='Trevor Schrock',
      author_email='spacemeat@gmail.com',
      url='https://github.com/spacemeat/geg',

      packages=find_packages(include=["geg", "geg.*"]),
      classifiers=[
            "Programming Language :: Python :: 3",
            "License :: OSI Approved :: MIT License",
            "Operating System :: POSIX :: Linux",
            "Programming Language :: C++",
            "Topic :: Software Development"
      ],
      install_requires = [
      ],
      extras_require = {
            'dev': ['check-manifest', 'twine']
      },
      python_requires='>=3.8'
)

