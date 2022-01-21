.PHONY: test
test:                           ##: run tests
	tox -p auto

.PHONY: coverage
coverage:                       ##: measure test coverage
	tox -e coverage

.PHONY: update-readme
update-readme:                  ##: update --help text in README.rst
	tox -e cog -- -r


FILE_WITH_VERSION = qr2text.py
check_recipe = TOX_SKIP_ENV=check-manifest tox -p auto
include release.mk
