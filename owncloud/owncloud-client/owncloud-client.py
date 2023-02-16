import configparser
import glob
import io
import os
import re
import subprocess
import sys

import info
from Packager.NullsoftInstallerPackager import NullsoftInstallerPackager


class subinfo(info.infoclass):
    def registerOptions(self):
        self.options.dynamic.registerOption("buildVfsWin", False)
        self.options.dynamic.registerOption("buildNumber", "")
        self.options.dynamic.registerOption("enableCrashReporter", False)
        self.options.dynamic.registerOption("enableAppImageUpdater", False)
        self.options.dynamic.registerOption("enableLibcloudproviders", False)
        self.options.dynamic.registerOption("forceAsserts", False)

    def setTargets(self):
        self.versionInfo.setDefaultValues(
            tarballUrl="https://download.owncloud.com/desktop/stable/owncloudclient-${VERSION}.tar.xz",
            tarballInstallSrc="owncloudclient-${VERSION}",
            gitUrl="[git]https://github.com/owncloud/client",
        )

        self.description = "ownCloud Desktop Client"
        self.displayName = "ownCloud"
        self.webpage = "https://owncloud.org"

    def setDependencies(self):
        self.buildDependencies["craft/craft-blueprints-owncloud"] = None
        self.buildDependencies["dev-utils/cmake"] = None
        self.buildDependencies["kde/frameworks/extra-cmake-modules"] = None
        self.buildDependencies["libs/libre-graph-api-cpp-qt-client"] = None

        self.runtimeDependencies["libs/sparkle"] = None
        self.runtimeDependencies["libs/zlib"] = None
        self.runtimeDependencies["libs/sqlite"] = None
        self.runtimeDependencies["libs/qt5/qtbase"] = None
        self.runtimeDependencies["libs/qt5/qtmacextras"] = None
        self.runtimeDependencies["libs/qt5/qtwinextras"] = None
        self.runtimeDependencies["libs/qt5/qttranslations"] = None
        self.runtimeDependencies["libs/qt5/qtsvg"] = None
        self.runtimeDependencies["libs/qt5/qtxmlpatterns"] = None
        self.runtimeDependencies["qt-libs/qtkeychain"] = None

        if CraftCore.compiler.isLinux:
            self.runtimeDependencies["libs/qt5/qtwayland"] = None

        if self.options.dynamic.buildVfsWin:
            self.runtimeDependencies["owncloud/client-desktop-vfs-win"] = None

        if self.options.dynamic.enableAppImageUpdater:
            self.runtimeDependencies["libs/libappimageupdate"] = None

        if self.options.dynamic.enableLibcloudproviders:
            self.runtimeDependencies["libs/libcloudproviders"] = None

        if self.options.dynamic.enableCrashReporter:
            self.buildDependencies["dev-utils/breakpad"] = None


from Package.CMakePackageBase import *


class Package(CMakePackageBase):
    def __init__(self):
        CMakePackageBase.__init__(self)
        self.subinfo.options.fetch.checkoutSubmodules = True
        # TODO: fix msi generation which expects the existance of a /translation dir
        self.subinfo.options.package.moveTranslationsToBin = False

        extraParam = os.environ.get("OWNCLOUD_CMAKE_PARAMETERS", "")
        if extraParam:
            # appending a string will convert the args to a string
            self.subinfo.options.configure.args += self.subinfo.options.configure.args
        if self.subinfo.options.dynamic.buildVfsWin:
            self.win_vfs_plugin = CraftPackageObject.get("owncloud/client-desktop-vfs-win")
            self.subinfo.options.configure.args += [f"-DVIRTUAL_FILE_SYSTEM_PLUGINS=off;suffix;{self.win_vfs_plugin.instance.sourceDir()}"]
        if self.subinfo.options.dynamic.enableCrashReporter:
            self.subinfo.options.configure.args += ["-DWITH_CRASHREPORTER=ON"]
        if self.subinfo.options.dynamic.enableAppImageUpdater:
            self.subinfo.options.configure.args += ["-DWITH_APPIMAGEUPDATER=ON"]
        if self.subinfo.options.dynamic.enableLibcloudproviders:
            self.subinfo.options.configure.args += ["-DWITH_LIBCLOUDPROVIDERS=ON"]
        if self.subinfo.options.dynamic.forceAsserts:
            self.subinfo.options.configure.args += ["-DFORCE_ASSERTS=ON"]
        if self.subinfo.options.dynamic.buildNumber:
            self.subinfo.options.configure.args += [f"-DMIRALL_VERSION_BUILD={self.subinfo.options.dynamic.buildNumber}"]

    @property
    def applicationExecutable(self):
        return os.environ.get("ApplicationExecutable", "owncloud")

    def fetch(self):
        if self.subinfo.options.dynamic.buildVfsWin:
            if not self.win_vfs_plugin.instance.fetch(noop=False):
                return False
        return super().fetch()

    def unpack(self):
        if self.subinfo.options.dynamic.buildVfsWin:
            if not self.win_vfs_plugin.instance.unpack(noop=False):
                return False
        return super().unpack()

    def install(self):
        if not super().install():
            return False
        if CraftCore.compiler.isWindows:
            # ensure we can find the sync-exclude.lst
            configDir = Path(self.installDir()) / "config" / os.environ.get("ApplicationShortname", self.applicationExecutable)
            if not configDir.exists():
                configDir = Path(self.installDir()) / "etc" / os.environ.get("ApplicationShortname", self.applicationExecutable)
            if configDir.exists():
                if not utils.mergeTree(configDir, Path(self.installDir()) / "bin"):
                    return False
        return True

    # Loosely based on https://chromium.googlesource.com/chromium/chromium/+/34599b0bf7a14ab21a04483c46ecd9b5eaf86704/components/breakpad/tools/generate_breakpad_symbols.py#92
    def dumpSymbols(self, binaryFiles: [], dest: str) -> bool:
        dest = Path(dest) / "symbols"
        utils.cleanDirectory(dest)
        moduleRe = re.compile("^MODULE [^ ]+ [^ ]+ ([0-9aA-fF]+) (.*)")
        skipDump = re.compile(r"icu\d\d\.dll|asprintf-0\.dll")
        finderSyncExtRe = re.compile(r"FinderSyncExt")
        cmdRe = re.compile(r".*cmd")
        crashReporterRe = re.compile(r".*_crash_reporter")

        for binaryFile in binaryFiles:
            binaryFile = Path(binaryFile)
            if CraftCore.compiler.isWindows and skipDump.match(binaryFile.name):
                CraftCore.log.warning(f"dump_symbols: {binaryFile} is blacklisted because it has no symbols")
                continue

            if CraftCore.compiler.isMacOS and (
                finderSyncExtRe.match(binaryFile.name) or cmdRe.match(binaryFile.name) or crashReporterRe.match(binaryFile.name)
            ):
                CraftCore.log.warning(
                    f"dump_symbols: {binaryFile} is blacklisted because we have no crash reporter for the finder extension, the cmdline client or the crash reporter itself"
                )
                continue

            CraftCore.log.info(f"Dump symbols for: {binaryFile}")

            # We use the path to the install prefix as the symbol files need to be located close to the library
            installedBinary = CraftCore.standardDirs.craftRoot() / binaryFile.relative_to(self.archiveDir())

            command = ["dump_syms"]
            if CraftCore.compiler.isMacOS:
                debugInfoPath = installedBinary
                bundleDir = list(filter(lambda x: x.name.endswith(".framework") or x.name.endswith(".app"), debugInfoPath.parents))
                if bundleDir:
                    debugInfoPath = bundleDir[-1]
                debugInfoPath = Path(f"{debugInfoPath}.dSYM/Contents/Resources/DWARF/") / installedBinary.name
                if debugInfoPath.exists():
                    command += ["-g", debugInfoPath]
            command.append(installedBinary)

            tmpFile = (dest / binaryFile.name).with_suffix(".tmp")
            with tmpFile.open("wb") as out:
                CraftCore.log.info(" ".join([str(x) for x in command]))
                subprocess.run(command, stdout=out, stderr=subprocess.DEVNULL)

            if not tmpFile.stat().st_size:
                CraftCore.log.warning(f"Found no valid output for {binaryFile}")
                tmpFile.unlink()
                return False

            with tmpFile.open("rb") as output:
                firstLine = str(output.readline(), "utf-8").strip()
                CraftCore.log.info(f"Module line: {firstLine}")

            if CraftCore.compiler.isWindows:
                if firstLine.startswith("loadDataForPdb and loadDataFromExe failed for"):
                    CraftCore.log.warning(f"Module does not contain debug symbols: {binaryFile}")
                    tmpFile.unlink()
                    return False

            CraftCore.log.debug("regex: %s" % moduleRe)
            moduleLine = moduleRe.match(firstLine)
            if not moduleLine:
                tmpFile.unlink()
                CraftCore.log.warning("Failed to parse dump_symbols output")
                return False
            CraftCore.log.debug("regex: %s" % moduleLine)
            outputPath = dest / moduleLine.group(2) / moduleLine.group(1)

            utils.createDir(outputPath)
            symbolFile = outputPath / moduleLine.group(2)
            if CraftCore.compiler.isWindows:
                symbolFile = symbolFile.with_suffix(".sym")
            else:
                symbolFile = f"{symbolFile}.sym"
            if not utils.moveFile(tmpFile, symbolFile):
                tmpFile.unlink()
                return False
            CraftCore.log.info("Writing symbols to: %s" % symbolFile)
        return True

    def owncloudVersion(self):
        versionFile = self.sourceDir() / "VERSION.cmake"
        if not versionFile.exists():
            CraftCore.log.warning(f"Failed to find {versionFile}")
            return None

        print_var_script = os.path.join(self.packageDir(), "print-var.cmake")

        def get_var(name) -> str:
            command = ["cmake", f"-DTARGET_SCRIPT={os.path.basename(versionFile)}", f"-DTARGET_VAR={name}"]

            if self.subinfo.options.dynamic.buildNumber:
                command.append(f"-DMIRALL_VERSION_BUILD={self.subinfo.options.dynamic.buildNumber}")

            command += ["-P", print_var_script]

            value = subprocess.check_output(
                command,
                cwd=os.path.dirname(versionFile),
                # make sure this call returns str instead of bytes
                universal_newlines=True,
            )
            value = value.strip()
            assert value, f"{name} empty"
            return value

        version_str = get_var("MIRALL_VERSION_STRING")

        print(f"*** version string fetched with CMake: {version_str} ***")

        return version_str

    def createPackage(self):
        self.blacklist_file.append(os.path.join(self.packageDir(), "blacklist.txt"))
        self.defines["appname"] = self.applicationExecutable
        self.defines["apppath"] = "Applications/KDE/" + self.applicationExecutable + ".app"
        self.defines["company"] = "ownCloud GmbH"
        self.defines["shortcuts"] = [
            {
                "name": self.subinfo.displayName,
                "target": f"{self.defines['appname']}{CraftCore.compiler.executableSuffix}",
                "description": self.subinfo.description,
            }
        ]
        self.defines["icon"] = Path(self.buildDir()) / "src/gui/owncloud.ico"
        self.defines["pkgproj"] = Path(self.buildDir()) / "admin/osx/macosx.pkgproj"
        ver = self.owncloudVersion()
        if ver:
            self.defines["version"] = ver

        self.blacklist.append(re.compile(r"bin[/|\\](?!" + self.applicationExecutable + r").*" + re.escape(CraftCore.compiler.executableSuffix)))

        self.ignoredPackages += ["binary/mysql"]
        if not CraftCore.compiler.isLinux:
            self.ignoredPackages += ["libs/dbus"]

        if self.subinfo.options.dynamic.enableCrashReporter:
            sep = "\\%s" % os.sep
            regex = r"symbols%s.*" % sep
            self.whitelist.append(re.compile(regex))
        return super().createPackage()

    def preArchiveMove(self):
        if self.subinfo.options.dynamic.enableCrashReporter:
            binaries = utils.filterDirectoryContent(
                self.archiveDir(), whitelist=lambda x, root: utils.isBinary(os.path.join(root, x)), blacklist=lambda x, root: True
            )
            if not self.dumpSymbols(binaries, self.archiveDebugDir()):
                return False
        return super().preArchive()
