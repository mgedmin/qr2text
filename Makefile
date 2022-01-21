.PHONY: test
test:                           ##: run tests
	tox -p auto

.PHONY: coverage
coverage:                       ##: measure test coverage
	tox -e coverage


FILE_WITH_VERSION = qr2text.py
check_recipe = TOX_SKIP_ENV=check-manifest tox -p auto
include release.mk
