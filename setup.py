from setuptools import setup

packages=['volumina', 
          'volumina.pixelpipeline',
          'volumina.colorama',
          'volumina.widgets',
          'volumina.widgets.ui',
          'volumina.view3d',
          'volumina.resources',
          'volumina.resources.icons']

package_data={'volumina.resources.icons': ['*.png', 'LICENSES'],
              'volumina.widgets.ui': ['*.ui']}

setup(name='volumina',
      version='0.6a',
      description='Volume Slicing and Editing',
      url='https://github.com/Ilastik/volumina',
      packages=packages,
      package_data=package_data
     )
