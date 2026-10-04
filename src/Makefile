# Code examples for the four use cases of the talk.
#
#   make          build and run everything that is meant to compile
#   make errors   show the compiler errors that the slides are about
#   make clean
#
# Example 4 runs a real Lua script and needs the Lua headers and library
# (dnf install lua-devel / apt install liblua5.4-dev).

# clang++ unless CXX is set: its concept errors are the ones on the slides
ifeq ($(origin CXX),default)
CXX = clang++
endif
CXXFLAGS ?= -std=c++20 -O2 -Wall -Wextra
LUA_CFLAGS := $(shell pkg-config --cflags lua)
LUA_LIBS   := $(shell pkg-config --libs lua)

PROGRAMS = 1_lua_metatable 2_serialization_enable_if 2_serialization_concepts \
           3_string_view_lookup 3_string_view_lookup_pre_cxx20 4_stateless_iterator

all: $(PROGRAMS)
	@for p in $(PROGRAMS); do echo "== $$p"; ./$$p; done

%: %.cc bufferlist.h
	$(CXX) $(CXXFLAGS) $< -o $@

3_string_view_lookup_pre_cxx20: 3_string_view_lookup.cc
	$(CXX) $(CXXFLAGS) -DPRE_CXX20 $< -o $@

4_stateless_iterator: 4_stateless_iterator.cc
	$(CXX) $(CXXFLAGS) $(LUA_CFLAGS) $< $(LUA_LIBS) -o $@

# every one of these is expected to fail to compile
ERROR = $(CXX) $(CXXFLAGS) -fsyntax-only
errors:
	@echo "== 1: missing function, without a concept"
	-@$(ERROR) -DFORGOT_PAIRS 1_lua_metatable.cc
	@echo "== 1: missing function, with a concept"
	-@$(ERROR) -DFORGOT_PAIRS -DUSE_CONCEPT 1_lua_metatable.cc
	@echo "== 2: enable_if, forgot one '!'"
	-@$(ERROR) -DFORGOT_NOT 2_serialization_enable_if.cc
	@echo "== 2: enable_if, a type that cannot be encoded"
	-@$(ERROR) -DNOT_ENCODABLE 2_serialization_enable_if.cc
	@echo "== 2: concepts, a type that cannot be encoded"
	-@$(ERROR) -DNOT_ENCODABLE 2_serialization_concepts.cc
	@echo "== 2: concepts, static_assert next to the type"
	-@$(ERROR) -DASSERT 2_serialization_concepts.cc
	@echo "== 4: multimap with the unique_keys concept"
	-@$(ERROR) $(LUA_CFLAGS) -DUNIQUE_KEYS 4_stateless_iterator.cc

clean:
	$(RM) $(PROGRAMS)

.PHONY: all errors clean
