# -*- coding: UTF-8 -*-

# Build customizations
# Change this file instead of sconstruct or manifest files, whenever possible.


# Since some strings in `addon_info` are translatable,
# we need to include them in the .po files.
# Gettext recognizes only strings given as parameters to the `_` function.
# To avoid initializing translations in this module we simply roll our own "fake" `_` function
# which returns whatever is given to it as an argument.
def _(arg):
	return arg


# Add-on information variables
addon_info = {
	# add-on Name/identifier, internal for NVDA
	"addon_name": "nvdaPiperDriver",
	# Add-on summary, usually the user visible name of the addon.
	# Translators: Summary for this add-on
	# to be shown on installation and add-on information found in Add-ons Manager.
	"addon_summary": _("NVDA Piper Driver"),
	# Add-on description
	# Translators: Long description to be shown for this add-on on add-on information from add-ons manager
	"addon_description": _("""NVDA Piper Driver is a maintained NVDA 2026 AMD64 adaptation of Sonata Neural Voices, originally developed by Musharraf Omer. It provides local neural Piper voices, bundled offline starter voices, and an accessible Voice Manager for installing additional voices."""),
	# version
	"addon_version": "3.2.1",
	# Author(s)
	"addon_author": "Musharraf Omer (upstream); Hosein Rezaii <rezaii.hosein@gmail.com> (maintainer)",
	"addon_publisher": "Hosein Rezaii <rezaii.hosein@gmail.com>",
	# URL for the add-on documentation support
	"addon_url": "https://github.com/rezaei-hossein-python/sonata-nvda",
	# URL for the add-on repository where the source code can be found
	"addon_sourceURL": "https://github.com/rezaei-hossein-python/sonata-nvda",
	# Documentation file name
	"addon_docFileName": "readme.html",
	# Minimum NVDA version supported (e.g. "2018.3.0", minor version is optional)
	"addon_minimumNVDAVersion": "2026.1.0",
	# Last NVDA version supported/tested (e.g. "2018.4.0", ideally more recent than minimum version)
	"addon_lastTestedNVDAVersion": "2026.1.1",
	# Add-on update channel (default is None, denoting stable releases,
	# and for development releases, use "dev".)
	# Do not change unless you know what you are doing!
	"addon_updateChannel": "stable",
	# Add-on license such as GPL 2
	"addon_license": "GPL v2",
	# URL for the license document the ad-on is licensed under
	"addon_licenseURL": "https://www.gnu.org/licenses/gpl-2.0.html",
	# Permanent release asset URL used by generated Add-on Store metadata.
	"addon_releaseURL": "https://github.com/rezaei-hossein-python/sonata-nvda/releases/download/v3.2.1/nvdaPiperDriver-3.2.1.nvda-addon",
	"addon_changelog": (
		"Automatically schedules Sonata Neural Voices 3.1.1 for removal during "
		"installation through NVDA's supported add-on lifecycle. Existing downloaded "
		"voices and the shared Sonata voice directory remain unchanged."
	),
}

pythonSources = [
    "addon/globalPlugins/*/*.py",
    "addon/synthDrivers/*/*.*"
]

# Files that contain strings for translation. Usually your python sources
i18nSources = pythonSources + ["buildVars.py"]

# Files that will be ignored when building the nvda-addon file
# Paths are relative to the addon directory, not to the root directory of your addon sources.
# Exclude compiled bytecode caches and transient build artifacts added for cleanliness.
excludedFiles = [
	"**/__pycache__/**",
	"**/*.pyc",
	"**/*.pyo",
	"**/*.bak",
	"**/*.bak2",
]

# Base language for the NVDA add-on
# If your add-on is written in a language other than english, modify this variable.
# For example, set baseLanguage to "es" if your add-on is primarily written in spanish.
baseLanguage = "en"

# Markdown extensions for add-on documentation
# Most add-ons do not require additional Markdown extensions.
# If you need to add support for markup such as tables, fill out the below list.
# Extensions string must be of the form "markdown.extensions.extensionName"
# e.g. "markdown.extensions.tables" to add tables.
markdownExtensions = []

