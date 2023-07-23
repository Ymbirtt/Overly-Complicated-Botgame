author_info = (
    ('Thierry Spetebroot', 'thierry.spetebroot@gmail.com'),
)

package_info = "Timer support for asyncio."
package_license = "MIT License"

version_info = (0, 0, 1)

__email__ = author_info[0][1]
__repo__ = "https://github.com/ThierrySpetebroot/aio-timers"

__author__ = ", ".join("{} <{}>".format(*info) for info in author_info)
__version__ = ".".join(map(str, version_info))
