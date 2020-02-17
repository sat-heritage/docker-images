
DOCKER_NS=satex

TESTS_DIR=tests

YEARS=$(shell jq -r '.|join(" ")' index.json)

BASES=$(wildcard base/*)

get-solvers = $(shell jq -r 'keys|join(" ")' $(1)/solvers.json)
image-name = $(DOCKER_NS)/$(basename $1)
get-year = $(subst .,,$(suffix $(subst :,.,$(basename $1))))
solver-id = $(basename $(subst :,.,$(basename $1)))
solver-name = $(shell cat solvers.json | jq -r '."$(1)".name')
get_setup_param = $(shell jq '."$(call solver-id,$2)"' $(call get-year,$2)/setup.json | jq .$1 - $(call get-year,$2)/setup.json | jq -r strings|head -n1)

build: $(BASES) $(addsuffix .build,$(YEARS))
FROM-update: $(addsuffix .FROM-update,$(BASES)) $(addsuffix .FROM-update,$(YEARS))
push: $(addsuffix .push,$(BASES)) $(addsuffix .push,$(YEARS))
test: $(addsuffix .test,$(YEARS))
list: $(addsuffix .list,$(YEARS))

.PHONY: $(YEARS)
$(YEARS):
	@make $@.build
$(addsuffix .build,$(YEARS)) $(addsuffix .test,$(YEARS)) $(addsuffix .list,$(YEARS)) $(addsuffix .push,$(YEARS)):
	@make $(addsuffix :$(basename $@)$(suffix $@),$(call get-solvers,$(basename $@)))

$(addsuffix .FROM-update,$(YEARS)):
	docker pull $(shell jq -r .builder_base $(basename $@)/setup.json)

%.build:
	@echo "####"
	@echo "#### $(call image-name,$@)"
	@echo "####"
	@IMAGE=$(call image-name,$@); \
	  Y=$(call get-year,$@); \
	  S=$$Y/setup.json; \
	  BASE_IMAGE=$(DOCKER_NS)/base:`jq -r .base_version $$S`;\
	  SOLVER_NAME=`jq -r '."$(call solver-id,$@)".name' $$Y/solvers.json`; \
	  RDEPENDS=`jq -r '."$(call solver-id,$@)".RDEPENDS' $$S`; \
	  generic_version=$(call get_setup_param,generic_version,$@); \
	  download_url="$(call get_setup_param,download_url,$@)";\
	  BUILDER_BASE=$(call get_setup_param,builder_base,$@);\
	  cfgfile=`tempfile -d $$Y -s .json` && \
	  jq '{ "$(call solver-id,$@)": ."$(call solver-id,$@)" }' $$Y/solvers.json > $$cfgfile  && \
	  cat $$cfgfile && \
	  set -ex;\
	  docker build -t $$IMAGE -f generic/$$generic_version/Dockerfile $$Y \
		--build-arg IMAGE_NAME=$$IMAGE \
		--build-arg BASE=$$BASE_IMAGE \
		--build-arg RDEPENDS="$${RDEPENDS/null/}" \
		--build-arg BUILDER_BASE="$$BUILDER_BASE" \
		--build-arg archive_baseurl=`jq -r .archive_baseurl $$S` \
		--build-arg download_url=$${download_url/SOLVER_NAME/$$SOLVER_NAME} \
		--build-arg dbjson=`basename $$cfgfile` \
		--build-arg solver_id=$(call solver-id,$@) \
		--build-arg solver=$$SOLVER_NAME; \
	rm $$cfgfile

%.push:
	docker push $(call image-name,$@)

%.test:
	@echo "########## $(call image-name,$@) #########"
	@set -x && cd $(TESTS_DIR) && \
	for cnf in *.gz; do \
		docker run --rm -v $$PWD:/data $(call image-name,$@) $$cnf; ret=$$?; \
		if [ $$ret -eq 0 ]; then true ; \
		elif [ $$ret -ge 10 -a $$ret -le 20 ]; then true; else exit 1; fi; \
	done
	@echo

%.list:
	@echo $(call image-name,$@)


.PHONY: base $(BASES)
base: $(BASES)
base.push: $(addsuffix .push,$(BASES))
$(BASES):
	docker build -t $(DOCKER_NS)/$(subst /,:,$@) $@
$(addsuffix .push,$(BASES)):
	docker push $(DOCKER_NS)/$(subst /,:,$(basename $@))
$(addsuffix .FROM-update,$(BASES)):
	docker pull $(shell grep '^FROM ' $(basename $@)/Dockerfile | cut -f2 -d' ')

clean:
	rm -f file*.json */file*.json

mrproper:
	docker images --format '{{.Repository}}:{{.Tag}}'|grep '^satex/'|xargs docker rmi
