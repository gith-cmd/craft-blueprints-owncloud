import info
from Package.CMakePackageBase import *


class subinfo(info.infoclass):
    def setTargets(self):
        self.description = "Implements functionality for dealing with AppImage files"

        for ver in ["1.0.4"]:
            self.targets[ver] = f"https://github.com/AppImage/libappimage/archive/refs/tags/v{ver}.tar.gz"
            self.targetInstSrc[ver] = f"libappimage-{ver}"

        self.targetDigests["1.0.4"] = (
            ["2af2adb682e8bf67dd726e79b3bc3af5a0d7c1533848bda56efa5cafa0dac931"],
            CraftHash.HashAlgorithm.SHA256,
        )

        self.defaultTarget = "1.0.4"

    def setDependencies(self):
        self.runtimeDependencies["libs/liblzma"] = None
        self.runtimeDependencies["libs/squashfuse"] = None
        self.runtimeDependencies["libs/libarchive"] = None
        self.runtimeDependencies["libs/boost/boost-filesystem"] = None
        self.runtimeDependencies["libs/xdg-utils-cxx"] = None


class Package(CMakePackageBase):
    def __init__(self, **args):
        CMakePackageBase.__init__(self)

        self.subinfo.options.configure.args += [
            "-DUSE_SYSTEM_XZ=ON",
            "-DUSE_SYSTEM_SQUASHFUSE=ON",
            "-DUSE_SYSTEM_LIBARCHIVE=ON",
            "-DUSE_SYSTEM_BOOST=ON",
            "-DUSE_SYSTEM_XDGUTILS=ON",
            "-DBUILD_TESTING=OFF",
        ]