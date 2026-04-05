from setuptools import setup, find_packages

setup(
    name='coral-lang',
    version='1.0.2',
    author='Coral Contributors',
    description='Coral – a statically-typed, structured Python variant',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    packages=find_packages(),
    python_requires='>=3.10',
    entry_points={
        'console_scripts': [
            'coral=coral.cli:main',
        ],
    },
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Topic :: Software Development :: Compilers',
        'Topic :: Software Development :: Interpreters',
    ],
)

