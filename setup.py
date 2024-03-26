from setuptools import setup

setup(name='phx-fix-base',
      version='1.0',
      description='Phoenix Prime FIX base functionality',
      author='Matrixport',
      author_email='daniel.egloff@matrixport.com',
      url='https://github.com/mtxpt/phx-fix-base',
      packages=['phx',
                'phx.fix',
                'phx.fix.app',
                'phx.fix.model',
                'phx.fix.specs',
                'phx.fix.tracker',
                'phx.fix.utils',
                'phx.utils'],
      package_data={'': ['phx/fix/specs/FIX44.xml']},
      )
