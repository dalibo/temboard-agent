all: buster stretch jessie wheezy

buster stretch jessie wheezy:
	mkdir -p ../../dist/
	docker-compose run --rm $@
	$(MAKE) changes-$@

changes-%:
	./mkchanges.sh $(shell readlink -e ../../dist/last_build.deb) $*

push:
	version=$$(dpkg-deb -f ../../dist/last_build.deb  Version | grep -Po '.*(?=-0dlb.*)'); \
	find ../../dist/ -name "temboard-agent_$${version}-0dlb*.changes" | xargs -rt dput labs
