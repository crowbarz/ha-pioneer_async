SHELL := /bin/bash
VERSION_PYTHON := $(shell egrep '^VERSION = ' custom_components/pioneer_async/const.py | cut -d\  -f3 | tr -d \" )
VERSION_MANIFEST := $(shell jq < custom_components/pioneer_async/manifest.json .version --raw-output  )
VERSION := $(VERSION_MANIFEST)

.PHONY: sdist
default: usage

usage:
	@echo "usage: make [ check | main ]"

check:
	@echo Python version $(VERSION_PYTHON)
	@echo Manifest version $(VERSION_MANIFEST)
	@[ "$(VERSION_PYTHON)" == "$(VERSION_MANIFEST)" ] || { echo "ERROR: versions don't match, aborting" ; exit 1 ; }

main: check
	@echo Merging dev to main for version $(VERSION)
	git checkout main
	git merge --ff-only dev
	git push origin main
	git push local main
	git checkout dev

local: check
	@echo Pushing dev and main to local for version $(VERSION)
	git push local dev
	git push local main
