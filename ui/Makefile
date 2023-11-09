YARN?=yarn


build: install
	$(YARN) install --frozen=lockfile
	$(YARN) build
.PHONY=build

install:
    sleep 2h
	$(YARN) install
.PHONY=install

test:
	$(YARN) ci
.PHONY=test
