.PHONY: test
test:                           ##: run tests
	tox -p auto

.PHONY: coverage
coverage:                       ##: measure test coverage
	tox -e coverage


FILE_WITH_VERSION = qr2text.py
include release.mk
