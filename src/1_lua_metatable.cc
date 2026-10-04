// Use case 1: a readable error message.
//
// create_metatable() needs four static functions from its template argument.
//
//   (default)                      everything is in place: compiles and runs
//   -DFORGOT_PAIRS                 the error without a concept
//   -DFORGOT_PAIRS -DUSE_CONCEPT   the error with a concept

#include <concepts>
#include <cstdio>

// --- mock: all we need from Lua is a state, and a way to register a function
struct lua_State {};
void set_handler(lua_State*, const char* event, int (*)(lua_State*)) {
  std::printf("registered %s\n", event);
}

// --- the library
#ifdef USE_CONCEPT
template <typename T>
concept lua_metatable = requires(lua_State* L) {
  { T::IndexClosure(L) }    -> std::same_as<int>;
  { T::NewIndexClosure(L) } -> std::same_as<int>;
  { T::PairsClosure(L) }    -> std::same_as<int>;
  { T::LenClosure(L) }      -> std::same_as<int>;
};

template <lua_metatable MetaTable>
#else
// MetaTable is expected to be a class with the following members:
//   IndexClosure, NewIndexClosure, PairsClosure, LenClosure
//   (static functions that accept "lua_State*" and return "int")
template <typename MetaTable>
#endif
void create_metatable(lua_State* L) {
  set_handler(L, "__index",    MetaTable::IndexClosure);
  set_handler(L, "__newindex", MetaTable::NewIndexClosure);
  set_handler(L, "__pairs",    MetaTable::PairsClosure);
  set_handler(L, "__len",      MetaTable::LenClosure);
}

// --- the user of the library
struct HTTPRequestHeadersMetaTable {
  static int IndexClosure(lua_State*) { return 0; }
  static int NewIndexClosure(lua_State*) { return 0; }
  static int LenClosure(lua_State*) { return 0; }
#ifndef FORGOT_PAIRS
  static int PairsClosure(lua_State*) { return 0; }
#endif
};

int main() {
  lua_State L;
  create_metatable<HTTPRequestHeadersMetaTable>(&L);
}
