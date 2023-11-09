YARN?=yarn


build: install
	$(YARN) install --frozen=lockfile
	$(YARN) build
.PHONY=build

install:
	$(YARN) install
.PHONY=install

test:
	$(YARN) ci
.PHONY=test
